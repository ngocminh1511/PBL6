"""Owns application resources and publishes validated configuration atomically."""
from contextlib import contextmanager, nullcontext
from threading import RLock

from fastapi import HTTPException, Request

EDITABLE = {
    "embedding_model", "embedding_backend", "query_embedding_backend", "qdrant_url",
    "qdrant_collection", "neo4j_uri", "llm_provider", "gemini_model",
    "anthropic_model", "openai_model", "modal_app_name", "redis_enabled",
}


class Runtime:
    def __init__(self, settings, database, catalog, *, storage_factory=None, retrieval_factory=None):
        self.settings = settings
        self.database = database
        self.catalog = catalog
        self.storage_factory = storage_factory
        self.retrieval_factory = retrieval_factory
        self.lock = RLock()
        self.operation_lock = RLock()
        self.active = 0
        self.version = 1
        self._retriever = self._inspector = self._storage = self._cache = None
        self.collection_models = {settings.QDRANT_COLLECTION: settings.EMBEDDING_MODEL, **settings.COLLECTION_MODELS}

    @contextmanager
    def operation(self, *, serialized=True):
        with self.lock:
            self.active += 1
        try:
            # The legacy retriever/catalog carry mutable stage state. Serialize
            # pipeline calls until all of those algorithms are stateless.
            with self.operation_lock if serialized else nullcontext():
                yield self
        finally:
            with self.lock:
                self.active -= 1

    def load_config(self):
        if not self.database.available:
            return
        from src.backend.app.models.database import SystemConfig
        with self.database.session() as db:
            row = db.query(SystemConfig).filter_by(key="runtime").first()
            if row:
                data = row.value
                changes = {k.upper(): v for k, v in data.get("overrides", {}).items() if k in EDITABLE}
                self.settings = type(self.settings).model_validate({**self.settings.model_dump(), **changes})
                self.version = data.get("version", 1)
                self.collection_models.update(data.get("collection_models", {}))

    def cache(self):
        with self.lock:
            return self._cache_client()

    def _cache_client(self):
        if self._cache is None:
            from src.backend.app.repositories.redis import Cache
            self._cache = Cache(self.settings)
        return self._cache

    def retriever(self):
        if self._retriever is None:
            from labor_rag.retrieval.hybrid_retrieve import HybridRetriever
            from labor_rag.services.embedding import EmbeddingProvider
            model = EmbeddingProvider(self.settings, backend=self.settings.query_backend,
                                      cache=self.cache(), namespace=str(self.version))
            self._retriever = HybridRetriever(settings=self.settings, model=model)
        return self._retriever

    def inspector(self):
        if self._inspector is None:
            if self.retrieval_factory:
                self._inspector = self.retrieval_factory()
            else:
                from labor_rag.retrieval.inspect import RetrievalInspector
                self._inspector = RetrievalInspector(self.catalog, self.retriever(), settings=self.settings)
        return self._inspector

    def storage(self):
        with self.lock:
            return self._storage_client()

    def _storage_client(self):
        if self._storage is None:
            from labor_rag.appendices.object_storage import R2Store
            self._storage = self.storage_factory() if self.storage_factory else R2Store()
        return self._storage

    def chat(self):
        from labor_rag.services.chat import ChatPipeline
        return ChatPipeline(self.retriever(), self.catalog, self.settings)

    def config(self):
        with self.lock:
            return self._config()

    def _config(self):
        config = {k: getattr(self.settings, k.upper()) for k in EDITABLE}
        config.update(
            query_embedding_backend=self.settings.query_backend, vector_db="qdrant",
            dataset_id=self.settings.DATASET_ID, config_version=self.version,
            demo_mode=self.settings.DEMO_MODE,
            available_collections=self.collection_models,
        )
        # URLs with credentials/userinfo/querystrings must never reach the UI.
        from urllib.parse import urlsplit, urlunsplit
        for key in ("qdrant_url", "neo4j_uri"):
            url = urlsplit(config[key])
            if url.hostname:
                host = url.hostname + (f":{url.port}" if url.port else "")
                config[key] = urlunsplit((url.scheme, host, url.path, "", ""))
        return config

    def validate_candidate(self, candidate):
        from labor_rag.retrieval.hybrid_retrieve import HybridRetriever
        from urllib.parse import urlsplit
        for value in (candidate.QDRANT_URL, candidate.NEO4J_URI):
            url = urlsplit(value)
            if url.username or url.password or url.query or url.fragment:
                raise HTTPException(422, "Thông tin xác thực phải đặt trong biến môi trường, không đặt trong URL quản trị.")
        if self.collection_models.get(candidate.QDRANT_COLLECTION) != candidate.EMBEDDING_MODEL:
            raise HTTPException(422, "Collection chưa được đăng ký cho model này; index và đăng ký trước khi chọn.")
        probe = None
        try:
            probe = HybridRetriever(settings=candidate)
            info = probe.qdrant.get_collection(candidate.QDRANT_COLLECTION)
            vector = probe.model.encode("Kiểm tra cấu hình")
            params = info.config.params.vectors
            if not hasattr(params, "size") or params.size != len(vector):
                raise HTTPException(422, "Số chiều embedding không khớp collection.")
            probe.neo4j.verify_connectivity()
            # This verifies selection/credentials without generating a paid answer.
            key = getattr(candidate, candidate.LLM_PROVIDER.upper() + "_API_KEY")
            if not key:
                raise HTTPException(422, "Chưa cấu hình API key cho LLM đã chọn.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, f"Không áp dụng cấu hình ({type(exc).__name__}).") from None
        finally:
            if probe:
                probe.close()

    def update(self, changes, expected_version=None):
        # Do not wait for a long OCR/chat request before reporting a busy runtime.
        if not self.lock.acquire(blocking=False):
            raise HTTPException(409, "Đang xử lý tác vụ; thử lưu lại sau.")
        try:
            if self.active or (expected_version is not None and expected_version != self.version):
                raise HTTPException(409, "Có tác vụ đang chạy hoặc cấu hình đã thay đổi; tải lại và thử sau.")
            if not self.database.available:
                raise HTTPException(503, "Cần DATABASE_URL PostgreSQL để lưu cấu hình.")
            changes = {k: v for k, v in changes.items() if k in EDITABLE and v is not None}
            try:
                candidate = type(self.settings).model_validate({
                    **self.settings.model_dump(), **{k.upper(): v for k, v in changes.items()},
                })
            except ValueError:
                raise HTTPException(422, "Cấu hình không hợp lệ.") from None
            self.validate_candidate(candidate)
            from src.backend.app.models.database import SystemConfig
            with self.database.session() as db:
                row = db.query(SystemConfig).filter_by(key="runtime").first()
                previous = row.value.get("overrides", {}) if row else {}
                value = {"version": self.version + 1, "overrides": {**previous, **changes},
                         "collection_models": self.collection_models}
                if row:
                    row.value = value
                else:
                    db.add(SystemConfig(key="runtime", value=value))
                db.commit()
            self.close_resources()
            self.settings = candidate
            self.version += 1
            return self.config()
        finally:
            self.lock.release()

    def close_resources(self):
        resources = [self._inspector, self._retriever, self._storage, self._cache]
        # An inspector normally owns the same retriever; close that client once.
        if self._inspector and getattr(self._inspector, "retriever", None) is self._retriever:
            resources[1] = None
        for resource in resources:
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass  # Already retired; a close failure must not undo a committed configuration.
        self._retriever = self._inspector = self._storage = self._cache = None


def get_runtime(request: Request):
    return request.app.state.runtime
