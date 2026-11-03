"""Optional cloud cache. Failure disables caching, never changes persistence."""
import json

class Cache:
    def __init__(self, settings):
        self.client = None
        self.status = "disabled" if not settings.REDIS_ENABLED else "not_configured"
        if settings.REDIS_ENABLED and settings.REDIS_URL:
            try:
                import redis
                self.client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True,
                    socket_connect_timeout=2, socket_timeout=2)
                self.client.ping()
                self.status = "connected"
            except Exception:
                self.status = "unavailable"
                if self.client:
                    self.client.close()
                self.client = None

    def get(self, key):
        if self.client:
            try:
                value = self.client.get("pbl6:" + key)
                return json.loads(value) if value is not None else None
            except Exception:
                self.status = "unavailable"
        return None

    def set(self, key, value, ttl):
        if self.client:
            try:
                self.client.setex("pbl6:" + key, ttl, json.dumps(value))
            except Exception:
                self.status = "unavailable"

    def flush(self):
        if not self.client:
            return 0
        count = 0
        for key in self.client.scan_iter(match="pbl6:*", count=100):
            count += self.client.delete(key)
        return count

    def close(self):
        if self.client:
            self.client.close()
