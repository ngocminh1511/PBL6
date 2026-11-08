"""Explicit retrieval scopes; old article payloads need no metadata migration."""
from qdrant_client.models import FieldCondition, Filter, MatchValue


def corpus_filter(scope: str = "extended") -> Filter:
    condition=FieldCondition(key="chunk_type",match=MatchValue(value="appendix"))
    if scope=="baseline":
        return Filter(must_not=[condition])
    if scope=="appendices":
        return Filter(must=[condition])
    if scope=="extended":
        return Filter()
    raise ValueError(f"Unknown corpus scope: {scope}")
