from typing import List, Optional
import os
import numpy as np
from src.backend.app.config import settings
from src.backend.app.repositories.redis import redis_repo

class EmbeddingService:
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.backend = settings.EMBEDDING_BACKEND
        self._local_model = None

    def _get_local_model(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            print(f"[EmbeddingService] Loading SentenceTransformer: {self.model_name}")
            self._local_model = SentenceTransformer(self.model_name)
        return self._local_model

    def embed_query(self, query: str) -> List[float]:
        """Embeds single query text with Redis cache check."""
        cached = redis_repo.get_embedding_cache(query)
        if cached:
            return cached

        if self.backend == "modal":
            try:
                import modal
                embedder = modal.Cls.from_name(settings.MODAL_APP_NAME, "Embedder")(model_name=self.model_name)
                res = embedder.embed.remote([query], 8192, 1)
                vec = np.frombuffer(res["vectors"], dtype=np.float32).reshape(1, res["dim"])[0].tolist()
                redis_repo.set_embedding_cache(query, vec)
                return vec
            except Exception as e:
                print(f"[EmbeddingService] Modal embedding failed ({e}), falling back to local.")

        model = self._get_local_model()
        vec = model.encode(query, normalize_embeddings=True).tolist()
        redis_repo.set_embedding_cache(query, vec)
        return vec

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embeds batch of texts."""
        if not texts:
            return []

        if self.backend == "modal":
            try:
                import modal
                embedder = modal.Cls.from_name(settings.MODAL_APP_NAME, "Embedder")(model_name=self.model_name)
                res = embedder.embed.remote(texts, 32768, batch_size)
                vectors = np.frombuffer(res["vectors"], dtype=np.float32).reshape(len(texts), res["dim"]).tolist()
                return vectors
            except Exception as e:
                print(f"[EmbeddingService] Modal batch embed failed ({e}), falling back to local.")

        model = self._get_local_model()
        return model.encode(texts, batch_size=batch_size, normalize_embeddings=True).tolist()

embedding_service = EmbeddingService()

