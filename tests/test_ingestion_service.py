"""Exercise real upload parsing/projection/merge with isolated vector and file stores."""
import hashlib
from types import SimpleNamespace

import numpy as np
import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from labor_rag.settings import Settings
from labor_rag.services.ingestion import IngestionPipeline, IngestionInputError
from labor_rag.ocr.schemas import LegalDocument, DocumentMetadata, Article


class Store:
    def __init__(self):
        self.objects = {}

    def upload_verified(self, path, digest, *, filename):
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest
        self.objects.setdefault(digest, payload)
        return {"bucket": "test", "key": digest, "verified_at": "2026-11-03", "sha256": digest}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    import qdrant_client
    import labor_rag.ingest.chunk_schema as schema
    import labor_rag.ingest.ontology_to_jsonl as projection
    import labor_rag.ingest.load_neo4j as loader
    store = QdrantClient(":memory:")
    store.create_collection("test", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    class Borrowed:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return store
        def __exit__(self, *args):
            pass
        def __getattr__(self, name):
            return getattr(store, name)
        def close(self):
            pass
    monkeypatch.setattr(qdrant_client, "QdrantClient", Borrowed)
    monkeypatch.setattr(schema, "TokenCounter", lambda *args: lambda value: len(value.split()))
    monkeypatch.setattr(projection, "TokenCounter", lambda *args: lambda value: len(value.split()))
    graph_calls = []
    monkeypatch.setattr(loader, "load_projection", lambda args: graph_calls.append(args))
    monkeypatch.setattr(store, "create_payload_index", lambda *args, **kwargs: None)
    config = Settings(_env_file=None, QDRANT_COLLECTION="test", QDRANT_URL="https://test",
        NEO4J_URI="neo4j+s://test", INTERIM_DIR=tmp_path / "interim", UPLOAD_DIR=tmp_path / "uploads")
    files = Store()
    embedded = []
    def encode(values, **kwargs):
        embedded.extend(values)
        return np.asarray([[1.0, 0.0] for _ in values])
    pipeline = IngestionPipeline(config, files, embedder=SimpleNamespace(encode=encode))
    yield pipeline, files, store, graph_calls, embedded
    store.close()


def test_pdf_upload_uses_real_abox_ids_and_is_idempotent(tmp_path, monkeypatch, isolated):
    import labor_rag.ocr.pipeline as ocr
    pipeline, files, vector, graphs, embedded = isolated
    document = LegalDocument(document_id="45-2019-qh14", title="Bộ luật Lao động",
        metadata=DocumentMetadata(so_hieu="45/2019/QH14", loai_van_ban="Bộ luật",
            ngay_hieu_luc="2021-01-01", version_date="2025-01-01"),
        articles=[Article(article_id="dieu_35", article_number="Điều 35",
            article_title="Hợp đồng lao động", full_text="Nội dung thử nghiệm đủ điều kiện.")])
    monkeypatch.setattr(ocr, "process_document", lambda path: SimpleNamespace(document=document))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4 test input")
    first = pipeline.run(source, "task-one", "pdf")
    assert first["document_ids"] == ["45-2019-qh14"]
    assert first["documents"][0]["chunks_count"] == 1
    assert first["documents"][0]["ast_tree_json"]["children"][0]["type"] == "article"
    points, _ = vector.scroll("test", with_payload=True)
    assert points[0].payload["chunk_id"] == "45-2019-qh14:d35"
    assert points[0].payload["version_date"] == "2025-01-01"
    assert graphs and graphs[0].replace_dataset is False
    assert len(files.objects) == 3  # original, ABox and hierarchy
    before = len(embedded)
    pipeline.run(source, "task-two", "pdf")
    assert len(embedded) == before
    assert vector.count("test", exact=True).count == 1


def test_embedding_failure_does_not_delete_old_points_or_write_graph(tmp_path, isolated):
    from qdrant_client.models import PointStruct
    from labor_rag.ingest.chunk_schema import point_id
    pipeline, _, vector, graphs, _ = isolated
    old = {"chunk_id": "law:d1", "document_id": "law", "text": "old", "source": "pdf",
           "version_date": "2020-01-01"}
    vector.upsert("test", points=[PointStruct(id=point_id("law:d1"), vector=[1.0, 0.0], payload=old)])
    def unavailable(*args, **kwargs):
        raise RuntimeError("embedding unavailable")
    pipeline.embedder = SimpleNamespace(encode=unavailable)
    newer = {**old, "text": "new", "version_date": "2025-01-01"}
    with pytest.raises(RuntimeError):
        pipeline.index([newer], tmp_path, lambda *args, **kwargs: None)
    assert not graphs
    assert vector.retrieve("test", ids=[point_id("law:d1")])[0].payload["text"] == "old"


def test_older_document_is_rejected_before_any_index_write(tmp_path, isolated):
    from qdrant_client.models import PointStruct
    from labor_rag.ingest.chunk_schema import point_id
    pipeline, _, vector, graphs, embedded = isolated
    current = {"chunk_id": "law:d1", "document_id": "law", "text": "current", "source": "pdf",
               "version_date": "2025-01-01"}
    vector.upsert("test", points=[PointStruct(id=point_id("law:d1"), vector=[1.0, 0.0], payload=current)])
    older = {**current, "text": "old", "version_date": "2020-01-01"}
    with pytest.raises(IngestionInputError):
        pipeline.index([older], tmp_path, lambda *args, **kwargs: None)
    assert not graphs and not embedded


def test_html_requires_known_labor_topic_without_interim_metadata(tmp_path, monkeypatch, isolated):
    import labor_rag.ingest.parse_demuc_html as parser
    pipeline, _, _, graphs, embedded = isolated
    monkeypatch.setattr(parser, "parse_demuc_nodes", lambda path: {
        "de_muc_id": "arbitrary-filename", "de_muc_so": "99.1", "children": [],
    })
    source = tmp_path / "unknown.html"
    source.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(IngestionInputError):
        pipeline.run(source, "invalid-html", "phap_dien_html")
    assert not graphs and not embedded


def test_html_builds_ontology_and_chunks_from_versioned_topic_metadata(tmp_path, monkeypatch, isolated):
    import labor_rag.ingest.parse_demuc_html as parser
    pipeline, files, vector, graphs, _ = isolated
    monkeypatch.setattr(parser, "parse_demuc_nodes", lambda path: {
        "de_muc_id": "uploaded-name", "de_muc_so": "20.2", "children": [{
            "kind": "dieu", "so_hieu": "20.2.BL.1.35", "mapc": "20.2.BL.1.35",
            "ten": "Hợp đồng lao động", "tieu_de": "Hợp đồng lao động",
            "citation": "( Điều 35 Bộ luật số 45/2019/QH14, có hiệu lực thi hành kể từ ngày 01/01/2021)",
            "paragraphs": ["Người lao động thực hiện quyền theo quy định."], "references": [],
        }],
    })
    source = tmp_path / "labor.html"
    source.write_text("<html>test</html>", encoding="utf-8")
    result = pipeline.run(source, "html-task", "phap_dien_html")
    assert result["document_ids"] == ["45-2019-qh14"]
    points, _ = vector.scroll("test", with_payload=True)
    assert points[0].payload["chunk_id"] == "45-2019-qh14:d35"
    assert points[0].payload["source"] == "phap_dien"
    assert graphs and len(files.objects) == 2
