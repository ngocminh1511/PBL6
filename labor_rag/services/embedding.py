"""One embedding implementation for uploads, retrieval and CLI services."""
import hashlib
import json


class EmbeddingProvider:
    def __init__(self, settings, *, backend=None, cache=None, namespace=""):
        self.settings = settings
        self.backend = backend or settings.EMBEDDING_BACKEND
        self.model_name = settings.EMBEDDING_MODEL
        self.cache = cache
        self.namespace = namespace
        self._model = None

    def encode(self, texts, normalize_embeddings=True, batch_size=32, **kwargs):
        import numpy as np
        single = isinstance(texts, str)
        values = [texts] if single else texts
        if not values:
            return np.empty((0, 0), dtype=np.float32)
        key = "embedding:" + hashlib.sha256(
            json.dumps([self.model_name, self.backend, self.settings.QDRANT_COLLECTION,
                        self.namespace, values], ensure_ascii=False).encode()
        ).hexdigest()
        cached = self.cache.get(key) if self.cache else None
        if cached is not None:
            result = np.asarray(cached, dtype=np.float32)
            return result[0] if single else result
        if self.backend == "modal":
            import modal
            embedder = modal.Cls.from_name(self.settings.MODAL_APP_NAME, "Embedder")(
                model_name=self.model_name,
            )
            response = embedder.embed.remote(values, 32768, batch_size)
            result = np.frombuffer(response["vectors"], dtype=np.float32).reshape(
                len(values), response["dim"],
            ).copy()
        else:
            from sentence_transformers import SentenceTransformer
            if self._model is None:
                self._model = SentenceTransformer(self.model_name)
            result = self._model.encode(
                values, normalize_embeddings=normalize_embeddings, batch_size=batch_size,
            )
        if self.cache:
            self.cache.set(key, result.tolist(), self.settings.EMBEDDING_CACHE_TTL)
        return result[0] if single else result

    def close(self):
        self._model = None
