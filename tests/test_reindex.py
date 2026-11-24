"""Re-indexing a corrected review: only changed Dieu are embedded, the
confirmed missing ones (PDF parts only) are deleted, and the previous graph
writes are undone before the new projection loads. Stores are in memory or faked."""
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from labor_rag.ingest.chunk_schema import article_id, point_id

DOC = "45-2019-qh14"


def chunk(n, text, source="pdf", document_id=DOC, **extra):
    return {"chunk_id": f"{document_id}:d{n}", "document_id": document_id, "text": text, "source": source,
            "version_date": "2026-01-01", "meta_dieu": str(n), "ten": "", **extra}


class Store:
    """An in-memory collection that survives the pipeline closing its client."""

    def __init__(self, payloads):
        self.inner = QdrantClient(":memory:")
        self.inner.create_collection("test", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
        self.inner.upsert("test", points=[PointStruct(id=point_id(p["chunk_id"]), vector=[0.0, 1.0], payload=p)
                                          for p in payloads])

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def close(self):
        pass

    def payloads(self):
        points, _ = self.inner.scroll("test", limit=100, with_payload=True, with_vectors=True)
        return {p.payload["chunk_id"]: (p.payload, p.vector) for p in points}


class Embedder:
    def __init__(self):
        self.seen = []

    def encode(self, texts, batch_size=16):
        self.seen.extend(texts)
        import numpy as np
        return [np.array([1.0, 0.0]) for _ in texts]


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    import labor_rag.ingest.load_neo4j as load_neo4j
    import labor_rag.services.neo4j as neo4j
    import labor_rag.services.removal as removal
    import qdrant_client
    from labor_rag.services.ingestion import IngestionPipeline

    store = Store([chunk(1, "Điều 1 cũ."), chunk(2, "Điều 2 giữ nguyên."), chunk(3, "Điều 3 giả do OCR."),
                   chunk(9, "Điều 9 Pháp điển.", source="phap_dien"),
                   chunk(1, "Văn bản bị thay thế.", document_id="10-2012-qh13", effective_to_date="2026-01-01")])
    events = []
    monkeypatch.setattr(qdrant_client, "QdrantClient", lambda **kwargs: store)
    monkeypatch.setattr(load_neo4j, "load_projection", lambda args: events.append("load"))
    monkeypatch.setattr(removal, "PhapDienBase", lambda: None)

    def fake_remove_graph(session, dataset_id, document_id, base):
        events.append(("remove_graph", document_id))
        return {"deleted_nodes": 2, "deleted_edges": 1, "reset_nodes": 1, "validity": {"10-2012-qh13": None}}
    monkeypatch.setattr(removal, "remove_graph", fake_remove_graph)

    class Driver:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def session(self, **kwargs):
            from contextlib import nullcontext
            return nullcontext(object())
    monkeypatch.setattr(neo4j, "create_neo4j_driver", lambda *args, **kwargs: Driver())

    settings = SimpleNamespace(QDRANT_URL="https://test", QDRANT_API_KEY="", QDRANT_TIMEOUT=5, QDRANT_COLLECTION="test",
                               DATASET_ID="ds", NEO4J_URI="neo4j://x", NEO4J_USER="u", NEO4J_PASSWORD="p",
                               NEO4J_DATABASE="neo4j")
    embedder = Embedder()
    return IngestionPipeline(settings, store=None, embedder=embedder), store, embedder, events, tmp_path


def test_reindex_embeds_changes_prunes_confirmed_pdf_dieu_and_redoes_the_graph(pipeline):
    pipe, store, embedder, events, tmp_path = pipeline
    new = [chunk(1, "Điều 1 đã sửa."), chunk(2, "Điều 2 giữ nguyên.")]
    prune = [article_id(f"{DOC}:d3"), article_id(f"{DOC}:d9")]  # d9 is Phap dien: never deleted
    result = pipe.index(new, tmp_path, lambda *a, **k: None, reindex={"prune": prune, "previous_document_id": DOC})

    left = store.payloads()
    assert embedder.seen == ["Điều 1 đã sửa."]  # the unchanged Dieu 2 is not embedded again
    assert left[f"{DOC}:d1"][0]["text"] == "Điều 1 đã sửa."
    assert f"{DOC}:d3" not in left and f"{DOC}:d9" in left and f"{DOC}:d2" in left
    assert result["pruned_chunks"] == 1
    assert events == [("remove_graph", DOC), "load"]  # previous graph writes undone first
    assert left["10-2012-qh13:d1"][0]["effective_to_date"] is None  # no longer replaced by this review


def test_first_index_keeps_missing_dieu_and_leaves_the_graph_alone(pipeline):
    pipe, store, embedder, events, tmp_path = pipeline
    pipe.index([chunk(1, "Điều 1 cũ."), chunk(2, "Điều 2 giữ nguyên.")], tmp_path, lambda *a, **k: None)
    left = store.payloads()
    assert f"{DOC}:d3" in left and embedder.seen == []
    assert events == ["load"]
