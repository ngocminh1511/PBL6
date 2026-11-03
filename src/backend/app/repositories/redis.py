import json
import hashlib
from typing import Optional, List, Dict, Any
try:
    import redis
except ImportError:
    redis = None
from src.backend.app.config import settings

class RedisRepository:
    def __init__(self):
        self.enabled = settings.REDIS_ENABLED and redis is not None
        self.client = None
        self._memory_cache = {}  # In-memory fallback if Redis is unreachable or module not installed
        
        if self.enabled and redis is not None:
            try:
                self.client = redis.Redis.from_url(
                    settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
                )
                self.client.ping()
            except Exception:
                # Fallback to local memory cache
                self.client = None

    def is_healthy(self) -> bool:
        if not self.client:
            return False
        try:
            return self.client.ping()
        except Exception:
            return False

    def get_embedding_cache(self, text: str) -> Optional[List[float]]:
        key = f"embed:{hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()}"
        if self.client:
            try:
                val = self.client.get(key)
                if val:
                    return json.loads(val)
            except Exception:
                pass
        return self._memory_cache.get(key)

    def set_embedding_cache(self, text: str, vector: List[float]):
        key = f"embed:{hashlib.sha256(text.strip().lower().encode('utf-8')).hexdigest()}"
        if self.client:
            try:
                self.client.setex(key, settings.EMBEDDING_CACHE_TTL, json.dumps(vector))
                return
            except Exception:
                pass
        self._memory_cache[key] = vector

    def get_session_context(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        key = f"session_ctx:{session_id}"
        if self.client:
            try:
                val = self.client.get(key)
                if val:
                    return json.loads(val)
            except Exception:
                pass
        return self._memory_cache.get(key)

    def set_session_context(self, session_id: str, history: List[Dict[str, str]]):
        key = f"session_ctx:{session_id}"
        if self.client:
            try:
                self.client.setex(key, settings.SESSION_CACHE_TTL, json.dumps(history))
                return
            except Exception:
                pass
        self._memory_cache[key] = history

    def flush_cache(self):
        if self.client:
            try:
                self.client.flushdb()
            except Exception:
                pass
        self._memory_cache.clear()

redis_repo = RedisRepository()
