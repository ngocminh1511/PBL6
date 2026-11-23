"""Application resources and transactional, versioned runtime configuration."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextlib import contextmanager, nullcontext, closing
from datetime import datetime, timezone
from threading import RLock

from fastapi import HTTPException, Request
from .configuration import (EDITABLE, SECRETS, GROUP_FIELDS, check_service, cipher,
                            decode_overrides, encode_overrides, public_url, validate_urls)


class Runtime:
    def __init__(self, settings, database, catalog, *, storage_factory=None, retrieval_factory=None):
        self.base = self.settings = settings
        self.database, self.catalog = database, catalog
        self.storage_factory, self.retrieval_factory = storage_factory, retrieval_factory
        self.lock, self.operation_lock = RLock(), RLock()
        self.active, self.version = 0, 1
        self._retriever = self._inspector = self._storage = self._cache = self._llm = None
        self.overrides = {}
        self.llm_profiles = []
        self.active_llm_profile_id = None
        self.configuration_error = None
        self._checks = ThreadPoolExecutor(max_workers=2, thread_name_prefix="configuration-check")
        self.collection_models = self.bindings(settings)

    def bindings(self, config):
        return {self.base.QDRANT_COLLECTION: self.base.EMBEDDING_MODEL, **config.COLLECTION_MODELS}

    def ensure_ready(self):
        if self.configuration_error:
            raise HTTPException(503, self.configuration_error)

    @contextmanager
    def operation(self, *, serialized=True):
        with self.lock:
            self.ensure_ready()
            self.active += 1
        try:
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
            if not row:
                return
            self.version = row.value.get("version", 1)
            try:
                values = decode_overrides(row.value, self.base.CONFIG_ENCRYPTION_KEY)
                if "collection_models" not in values and row.value.get("collection_models"):
                    values["collection_models"] = row.value["collection_models"]
                candidate = self.make_settings(values)
                from .llm_profiles import decode_profiles, profile_from_settings, secret_field
                profiles = decode_profiles(row.value.get("llm_profiles", []), self.base.CONFIG_ENCRYPTION_KEY)
                active_id = row.value.get("active_llm_profile_id")
                if active_id and not any(p["id"] == active_id for p in profiles):
                    raise ValueError("Missing active profile")
                if not active_id and set(values) & GROUP_FIELDS["llm"]:
                    source = "custom" if secret_field(candidate.LLM_PROVIDER) in values else "environment"
                    legacy = profile_from_settings(candidate, identity="legacy", source=source, name="Cấu hình đã lưu trước đây")
                    profiles = [p for p in profiles if p["id"] != "legacy"] + [legacy]
                    active_id = "legacy"
            except (ValueError, TypeError):
                self.configuration_error = "Không tải được cấu hình đã lưu; kiểm tra CONFIG_ENCRYPTION_KEY và cấu hình trong PostgreSQL."
                return
            self.overrides = values
            self.llm_profiles, self.active_llm_profile_id = profiles, active_id
            self.settings = candidate
            self.collection_models = self.bindings(candidate)

    def make_settings(self, overrides):
        try:
            candidate = type(self.base).model_validate({**self.base.model_dump(),
                **{k.upper(): v for k, v in overrides.items() if k in EDITABLE}})
            validate_urls(candidate, set(overrides))
            return candidate
        except (ValueError, TypeError):
            raise ValueError("Cấu hình chưa hợp lệ; kiểm tra URL, lựa chọn và giới hạn các trường.") from None

    def candidate(self, changes, reset_fields=()):
        self.ensure_ready()
        unknown = set(reset_fields) - EDITABLE
        if unknown:
            raise HTTPException(422, "Có trường không thể khôi phục từ môi trường.")
        values = {k: v for k, v in self.overrides.items() if k not in reset_fields}
        values.update({k: v for k, v in changes.items() if k in EDITABLE and v is not None})
        try:
            return self.make_settings(values), values
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    def cache(self):
        with self.lock:
            self.ensure_ready()
            if self._cache is None:
                from src.backend.app.repositories.redis import Cache
                self._cache = Cache(self.settings)
            return self._cache

    def retriever(self):
        self.ensure_ready()
        if self._retriever is None:
            from labor_rag.retrieval.hybrid_retrieve import HybridRetriever
            from labor_rag.services.embedding import EmbeddingProvider
            model = EmbeddingProvider(self.settings, backend=self.settings.query_backend,
                                      cache=self.cache(), namespace=str(self.version))
            self._retriever = HybridRetriever(settings=self.settings, model=model)
        return self._retriever

    def inspector(self):
        self.ensure_ready()
        if self._inspector is None:
            if self.retrieval_factory:
                self._inspector = self.retrieval_factory()
            else:
                from labor_rag.retrieval.inspect import RetrievalInspector
                self._inspector = RetrievalInspector(self.catalog, self.retriever(), settings=self.settings)
        return self._inspector

    def storage(self):
        with self.lock:
            self.ensure_ready()
            if self._storage is None:
                from labor_rag.appendices.object_storage import R2Store, StorageConfig
                self._storage = self.storage_factory() if self.storage_factory else R2Store(StorageConfig.from_settings(self.settings))
            return self._storage

    def chat(self):
        self.ensure_ready()
        from labor_rag.services.chat import ChatPipeline
        from labor_rag.generation.llm_client import LLMClient
        if self._llm is None:
            self._llm = LLMClient(self.settings)
        return ChatPipeline(self.retriever(), self.catalog, self.settings, llm=self._llm)

    def config(self):
        with self.lock:
            url_fields = {"qdrant_url", "neo4j_uri", "local_llm_base_url", "object_storage_endpoint_url",
                          "openrouter_base_url", "groq_base_url", "qwen_base_url"}
            result = {k: getattr(self.settings, k.upper()) for k in EDITABLE - SECRETS}
            for key in url_fields:
                result[key] = public_url(result[key])
            try:
                cipher(self.base.CONFIG_ENCRYPTION_KEY)
                encryption_ready = True
            except ValueError:
                encryption_ready = False
            result.update(query_embedding_backend=self.settings.query_backend, vector_db="qdrant",
                dataset_id=self.settings.DATASET_ID, config_version=self.version, demo_mode=self.settings.DEMO_MODE,
                active_llm_profile_id=self.active_llm_profile_id,
                available_collections=self.collection_models,
                sources={k: "saved" if k in self.overrides else
                    "environment" if k.upper() in self.base.model_fields_set else "default" for k in EDITABLE},
                environment_values={k: public_url(getattr(self.base, k.upper())) if k in url_fields
                    else self.base.query_backend if k == "query_embedding_backend" else getattr(self.base, k.upper())
                    for k in EDITABLE - SECRETS},
                environment_secret_configured={k: bool(getattr(self.base, k.upper())) for k in SECRETS},
                environment_sources={k: "environment" if k.upper() in self.base.model_fields_set else "default" for k in EDITABLE},
                query_embedding_inherits=self.settings.QUERY_EMBEDDING_BACKEND is None,
                environment_query_embedding_inherits=self.base.QUERY_EMBEDDING_BACKEND is None,
                secret_configured={k: bool(getattr(self.settings, k.upper())) for k in SECRETS},
                can_save=self.database.available and not self.configuration_error,
                encryption_ready=encryption_ready, configuration_error=self.configuration_error,
                postgres_status="connected" if self.database.available else "unavailable",
                postgres_endpoint=public_url(self.base.DATABASE_URL), redis_endpoint=public_url(self.settings.REDIS_URL),
                startup={"upload_dir": str(self.base.UPLOAD_DIR), "interim_dir": str(self.base.INTERIM_DIR),
                         "cors_origins": self.base.CORS_ORIGINS, "api_prefix": self.base.API_V1_PREFIX})
            return result

    def check_group(self, group, config):
        timeout = 60 if group in {"llm", "embedding", "ocr"} else 10
        future = self._checks.submit(check_service, group, config)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            future.cancel()
            return {"service": group, "status": "failed", "message": "Kiểm tra quá thời gian cho phép.",
                    "details": {"error": "timeout"}, "latency_ms": timeout * 1000,
                    "checked_at": datetime.now(timezone.utc).isoformat()}

    def check(self, group, changes, reset_fields=()):
        with self.lock:
            config, _ = self.candidate(changes, reset_fields)
        return self.check_group(group, config)

    def models(self, changes, reset_fields=()):
        with self.lock:
            config, _ = self.candidate(changes, reset_fields)
        return self.list_models(config)

    def list_models(self, config):
        def fetch():
            from labor_rag.generation.llm_client import LLMClient
            with closing(LLMClient(config)) as client:
                return client.models()
        future = self._checks.submit(fetch)
        try:
            return {"models": future.result(timeout=60), "provider": config.LLM_PROVIDER}
        except Exception as exc:
            future.cancel()
            from .configuration import failure_message
            _, message = failure_message(exc)
            raise HTTPException(503, message) from None

    def validate_candidate(self, candidate):
        changed = {k for k in EDITABLE if getattr(candidate, k.upper()) != getattr(self.settings, k.upper())}
        checks = {}
        for group, fields in GROUP_FIELDS.items():
            if fields & changed:
                checks[group] = self.check_group(group, candidate)
                if checks[group]["status"] not in {"passed", "disabled"}:
                    raise HTTPException(503, f"{group}: {checks[group]['message']}")
        if changed & {"embedding_model", "embedding_backend", "query_embedding_backend", "qdrant_collection", "collection_models", "qdrant_url"}:
            if self.bindings(candidate).get(candidate.QDRANT_COLLECTION) != candidate.EMBEDDING_MODEL:
                raise HTTPException(422, "Collection chưa được đăng ký cho model đã chọn.")
            for group in ("embedding", "qdrant"):
                if group not in checks:
                    checks[group] = self.check_group(group, candidate)
                if checks[group]["status"] != "passed":
                    raise HTTPException(503, f"{group}: {checks[group]['message']}")
            if checks["embedding"]["details"]["dimensions"] != checks["qdrant"]["details"]["dimensions"]:
                raise HTTPException(422, "Số chiều embedding không khớp collection đã chọn.")

    def update(self, changes, expected_version=None, reset_fields=()):
        if not self.lock.acquire(blocking=False):
            raise HTTPException(409, "Đang xử lý tác vụ; thử lưu lại sau.")
        try:
            self.check_write(expected_version)
            candidate, values = self.candidate(changes, reset_fields)
            profiles, active_id = self.llm_profiles, self.active_llm_profile_id
            if (set(changes) | set(reset_fields)) & GROUP_FIELDS["llm"]:
                from .llm_profiles import profile_from_settings, secret_field
                profiles = [p for p in profiles if p["id"] != "legacy"]
                active_id = None
                if set(values) & GROUP_FIELDS["llm"]:
                    source = "custom" if secret_field(candidate.LLM_PROVIDER) in values else "environment"
                    profiles = profiles + [profile_from_settings(candidate, identity="legacy", source=source, name="Cấu hình đã lưu trước đây")]
                    active_id = "legacy"
            # Reject missing encryption keys before the network validation.
            try:
                encode_overrides(values, self.base.CONFIG_ENCRYPTION_KEY)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            self.validate_candidate(candidate)
            self.commit_configuration(candidate, values, profiles=profiles, active_profile_id=active_id)
            return self.config()
        finally:
            self.lock.release()

    def check_write(self, expected_version=None):
        self.ensure_ready()
        if self.active:
            raise HTTPException(409, f"Đang có {self.active} tác vụ chạy (hỏi đáp, tải tài liệu hoặc kiểm tra dịch vụ); "
                                     "chờ tác vụ hoàn tất rồi lưu lại.")
        if expected_version is not None and expected_version != self.version:
            raise HTTPException(409, "Cấu hình đã được thay đổi ở nơi khác; tải lại trang rồi thử lại.")
        if not self.database.available:
            raise HTTPException(503, "Cần cấu hình DATABASE_URL PostgreSQL trong môi trường và khởi động lại backend để lưu.")

    def commit_configuration(self, candidate, values, *, profiles, active_profile_id):
        from src.backend.app.models.database import SystemConfig
        from .llm_profiles import encode_profiles
        try:
            public, encrypted = encode_overrides(values, self.base.CONFIG_ENCRYPTION_KEY)
            encoded_profiles = encode_profiles(profiles, self.base.CONFIG_ENCRYPTION_KEY)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        with self.database.session() as db:
            row = db.query(SystemConfig).filter_by(key="runtime").first()
            if row and row.value.get("version", 1) != self.version:
                raise HTTPException(409, "Cấu hình đã thay đổi; tải lại và thử sau.")
            value = {"format_version": 3, "version": self.version + 1,
                     "overrides": public, "encrypted_secrets": encrypted,
                     "llm_profiles": encoded_profiles, "active_llm_profile_id": active_profile_id}
            if row:
                row.value = value
            else:
                db.add(SystemConfig(key="runtime", value=value))
            db.commit()
        if candidate != self.settings:
            self.close_resources()
        self.settings, self.overrides = candidate, values
        self.llm_profiles, self.active_llm_profile_id = profiles, active_profile_id
        self.collection_models = self.bindings(candidate)
        self.version += 1

    def close_resources(self, *, shutdown=False):
        resources = [self._inspector, self._retriever, self._storage, self._cache, self._llm]
        if self._inspector and getattr(self._inspector, "retriever", None) is self._retriever:
            resources[1] = None
        for resource in resources:
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
        self._retriever = self._inspector = self._storage = self._cache = self._llm = None
        if shutdown:
            self._checks.shutdown(wait=False, cancel_futures=True)


def get_runtime(request: Request):
    return request.app.state.runtime
