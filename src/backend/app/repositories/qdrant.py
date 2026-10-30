from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, Distance, VectorParams
from src.backend.app.config import settings

class QdrantRepository:
    def __init__(self):
        self.url = settings.QDRANT_URL
        self.api_key = settings.QDRANT_API_KEY
        self.collection = settings.QDRANT_COLLECTION
        self.client = QdrantClient(url=self.url, api_key=self.api_key, timeout=10)

    def is_healthy(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def count_points(self, collection_name: Optional[str] = None) -> int:
        col = collection_name or self.collection
        try:
            if not self.client.collection_exists(col):
                return 0
            return self.client.count(collection_name=col, exact=True).count
        except Exception:
            return 0

    def query_points(self, vector: List[float], query_filter: Optional[Filter] = None, limit: int = 10, collection_name: Optional[str] = None):
        col = collection_name or self.collection
        return self.client.query_points(
            collection_name=col,
            query=vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        ).points

    def ensure_collection(self, collection_name: str, dim: int = 1024):
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

qdrant_repo = QdrantRepository()

