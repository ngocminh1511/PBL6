"""Contracts spanning the unified API, configuration, persistence and core."""
from dataclasses import fields
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from labor_rag.settings import Settings
from labor_rag.retrieval.hybrid_retrieve import Evidence
from src.backend.app.main import create_app
from src.backend.app.models.schemas import EvidenceItem
from src.backend.app.models.database import ChatMessage, IngestionTask


def config(tmp_path, **changes):
    return Settings(_env_file=None, DATABASE_URL="sqlite://", REDIS_URL="", REDIS_ENABLED=False,
        UPLOAD_DIR=tmp_path / "uploads", INTERIM_DIR=tmp_path / "interim",
        QDRANT_URL="https://vectors.example", NEO4J_URI="neo4j+s://graph.example",
        GEMINI_API_KEY="test-private-key", **changes)


def test_public_tools_without_application_database_or_llm(tmp_path, monkeypatch):
    settings = config(tmp_path).model_copy(update={"DATABASE_URL": "", "GEMINI_API_KEY": ""})
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/health").status_code == 200
        listing = client.get("/api/appendices")
        assert listing.status_code == 200 and "items" in listing.json()
        health = client.get("/api/health").json()
        assert health["postgres"]["connection"] == "unavailable"
        assert health["llm"]["status"] == "not_probed"
        assert "test-private-key" not in client.get("/api/admin/config").text
        assert client.get("/api/chat/sessions").status_code == 503
        assert client.put("/api/admin/config", json={"embedding_backend": "local"}).status_code == 503
        assert client.post("/api/retrieve", json={"question": " "}).status_code == 422


def test_complete_evidence_contract():
    assert {field.name for field in fields(Evidence)} <= EvidenceItem.model_fields.keys()


def test_main_pipeline_supplies_linked_appendix_to_answer_generation(tmp_path, monkeypatch):
    from labor_rag.appendices.runtime import AppendixCatalog
    from labor_rag.services.chat import ChatPipeline
    import labor_rag.generation.answer as generation
    import labor_rag.retrieval.rerank as ranking
    catalog = AppendixCatalog(tmp_path)
    identity = "09-2020-tt-bldtbxh:pl1"
    catalog.items = {identity: {
        "appendix_id": identity, "document_id": "09-2020-tt-bldtbxh",
        "document_number": "09/2020/TT-BLĐTBXH", "number": "I", "key": "1",
        "title": "Danh mục công việc", "text": "Nội dung đã rà soát.", "kind": "reference",
        "forms": [], "review_status": "reviewed", "still_valid": True,
        "artifact_ids": [], "article_ids": [{"document_id": "45-2019-qh14", "article_number": "147"}],
    }}
    catalog.chunks = {identity + ":p1": {
        "chunk_id": identity + ":p1", "appendix_id": identity, "appendix_number": "I",
        "document_id": "09-2020-tt-bldtbxh", "document_number": "09/2020/TT-BLĐTBXH",
        "chunk_type": "appendix", "text": "Danh mục công việc ảnh hưởng thể lực.",
    }}
    catalog.article_neighbors = {}
    catalog.references = []
    evidence = Evidence("45-2019-qh14:d147", "20.2.147", "Điều 147", "Dẫn chiếu danh mục.",
                        "vector", document_id="45-2019-qh14", meta_dieu="147")
    retriever = SimpleNamespace(retrieve=lambda *args, **kwargs: [evidence], graph_warning=None)
    seen = []
    def answer(query, items, **kwargs):
        seen.extend(items)
        return "Theo Phụ lục I Thông tư 09/2020/TT-BLĐTBXH."
    monkeypatch.setattr(generation, "generate_answer", answer)
    monkeypatch.setattr(ranking, "rerank", lambda query, items, **kwargs: items)
    result = ChatPipeline(retriever, catalog, config(tmp_path)).ask("Công việc ảnh hưởng thể lực")
    assert any(item.appendix_id == identity for item in seen)
    assert result["attachments"][0]["appendix_id"] == identity
    assert result["citation_check"]["all_verified"]
    assert catalog.last_attachments == []  # outputs belong to this request only


def test_core_never_imports_application_or_cli_modules():
    import ast
    import os
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "labor_rag"
    forbidden = ("src.backend", "fastapi", "sqlalchemy", "scripts")
    paths = []
    for directory, children, files in os.walk(root):
        children[:] = [name for name in children if name not in {"venv", ".venv", "__pycache__"}]
        paths.extend(Path(directory) / name for name in files if name.endswith(".py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else [])
            assert not any(name == prefix or name.startswith(prefix + ".")
                           for name in modules for prefix in forbidden), str(path)


def test_chat_preserves_appendices_amendments_and_history(tmp_path, monkeypatch):
    import labor_rag.generation.answer as generation
    import labor_rag.retrieval.query_rewrite as rewrite
    import labor_rag.retrieval.rerank as ranking
    from labor_rag.services.chat import ChatPipeline
    amendment = Evidence("amend:d1", None, "Sửa đổi", "Văn bản sửa đổi", "amendment",
                         document_id="amend", meta_dieu="1", change="bổ sung")
    original = Evidence("law:d1", "20.2.1", "Điều 1", "Nội dung", "vector", 0.8,
                        document_id="law", meta_dieu="1", version_date="2021-01-01",
                        amendments=[amendment], appendix_id="missing:pl1",
                        artifact_ids=["source-1"], locator={"block_ids": ["b1"]})
    retriever = SimpleNamespace(retrieve=lambda *args, **kwargs: [original], graph_warning=None)
    seen_history = []
    monkeypatch.setattr(generation, "generate_answer", lambda *args, **kwargs: "Nội dung trả lời.")
    monkeypatch.setattr(ranking, "rerank", lambda query, items, **kwargs: items)
    monkeypatch.setattr(rewrite, "rewrite_query", lambda history, question: seen_history.append(list(history)) or question)
    app = create_app(settings=config(tmp_path))
    monkeypatch.setattr(app.state.runtime, "chat",
        lambda: ChatPipeline(retriever, app.state.runtime.catalog, app.state.runtime.settings))
    with TestClient(app) as client:
        first = client.post("/api/chat/ask", json={"question": "Câu hỏi đầu"}).json()
        assert "assistant_message" in first
        message = first["assistant_message"]
        evidence = message["legal_evidence"][0]
        assert evidence["version_date"] == "2021-01-01"
        assert evidence["artifact_ids"] == ["source-1"]
        assert evidence["locator"] == {"block_ids": ["b1"]}
        assert evidence["amendments"][0]["document_id"] == "amend"
        second = client.post("/api/chat/ask", json={
            "question": "Câu hỏi sau", "session_id": first["session_id"],
        })
        assert second.status_code == 200
        assert len(seen_history[0]) == 2
        stored = client.get("/api/chat/sessions/" + first["session_id"]).json()["messages"]
        assert len(stored) == 4 and stored[1]["legal_evidence"] == message["legal_evidence"]
        client.post("/api/chat/ask", json={"question": "Phiên riêng"})
        assert len(seen_history) == 1  # new session has no history to rewrite


def test_pipeline_failure_never_saves_fake_success(tmp_path, monkeypatch):
    app = create_app(settings=config(tmp_path))
    class Broken:
        def ask(self, *args, **kwargs):
            raise RuntimeError("secret-endpoint-token")
    monkeypatch.setattr(app.state.runtime, "chat", lambda: Broken())
    with TestClient(app) as client:
        response = client.post("/api/chat/ask", json={"question": "Hỏi"})
        assert response.status_code == 503
        assert "secret-endpoint-token" not in response.text
        with app.state.database.session() as db:
            assert db.query(ChatMessage).count() == 0


def test_config_persists_and_failed_or_busy_update_keeps_old_runtime(tmp_path, monkeypatch):
    database_url = "sqlite:///" + str(tmp_path / "application.db")
    settings = config(tmp_path).model_copy(update={"DATABASE_URL": database_url})
    app = create_app(settings=settings)
    runtime = app.state.runtime
    monkeypatch.setattr(runtime, "validate_candidate", lambda candidate: None)
    with TestClient(app) as client:
        saved = client.put("/api/admin/config", json={"config_version": 1,
            "embedding_backend": "local", "query_embedding_backend": "local"})
        assert saved.status_code == 200 and saved.json()["config_version"] == 2
        assert client.put("/api/admin/config", json={"config_version": 1}).status_code == 409
        def fail(candidate):
            from fastapi import HTTPException
            raise HTTPException(503, "Không kết nối được.")
        monkeypatch.setattr(runtime, "validate_candidate", fail)
        assert client.put("/api/admin/config", json={"embedding_backend": "modal"}).status_code == 503
        assert runtime.settings.EMBEDDING_BACKEND == "local" and runtime.version == 2
        ready, release = Event(), Event()
        def work():
            with runtime.operation():
                ready.set()
                release.wait(5)
        thread = Thread(target=work)
        thread.start()
        assert ready.wait(2)
        try:
            assert client.put("/api/admin/config", json={"embedding_backend": "modal"}).status_code == 409
        finally:
            release.set()
            thread.join()
    with TestClient(create_app(settings=settings)) as client:
        loaded = client.get("/api/admin/config").json()
        assert loaded["embedding_backend"] == "local" and loaded["config_version"] == 2


def test_versioned_migration_preserves_existing_content():
    from src.backend.app.migrations import upgrade
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE chat_messages (id VARCHAR(36) PRIMARY KEY, content TEXT)"))
        connection.execute(text("INSERT INTO chat_messages VALUES ('old', 'keep me')"))
    upgrade(engine)
    upgrade(engine)
    assert {"attachments", "warnings"} <= {c["name"] for c in inspect(engine).get_columns("chat_messages")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT content FROM chat_messages WHERE id='old'")).scalar() == "keep me"
        assert connection.execute(text("SELECT count(*) FROM app_schema_versions")).scalar() == 1


@pytest.mark.parametrize("fail", [False, True])
def test_upload_only_completes_after_shared_pipeline_returns(tmp_path, monkeypatch, fail):
    import labor_rag.services.ingestion as ingestion
    class Pipeline:
        def __init__(self, *args, **kwargs):
            pass
        def run(self, path, task_id, document_type, **kwargs):
            assert path.parent.name == task_id
            if fail:
                raise RuntimeError("private-storage-credential")
            return {"document_ids": ["law"], "documents": [{"id": "law", "title": "Luật thử nghiệm",
                "document_type": "pdf", "domain": "lao_dong", "status": "completed",
                "chunks_count": 2, "nodes_count": 3, "edges_count": 2}],
                "artifacts": [], "warnings": [], "total_chunks": 2}
    monkeypatch.setattr(ingestion, "IngestionPipeline", Pipeline)
    app = create_app(settings=config(tmp_path), storage_factory=lambda: SimpleNamespace(close=lambda: None))
    with TestClient(app) as client:
        response = client.post("/api/documents/upload", files={"file": ("source.pdf", b"%PDF-test", "application/pdf")})
        assert response.status_code == 202 and response.json()["document_id"] is None
        app.state.ingestion.executor.shutdown(wait=True)
        task = client.get("/api/documents/tasks/" + response.json()["task_id"] + "/progress").json()
        assert task["status"] == ("failed" if fail else "completed")
        assert "private-storage-credential" not in str(task)
        if not fail:
            assert task["result"]["document_ids"] == ["law"]
            assert task["total_chunks"] == 2


def test_demo_is_explicit_and_registration_cannot_grant_admin(tmp_path):
    app = create_app(settings=config(tmp_path).model_copy(update={"DEMO_MODE": False, "JWT_SECRET": "test-only-key"}))
    with TestClient(app) as client:
        assert client.get("/api/admin/config").status_code == 401
        assert client.get("/api/appendices").status_code == 200
        assert client.post("/api/auth/register", json={
            "username": "admin_override", "email": "test@example.org", "password": "password", "role": "admin",
        }).status_code == 422


def test_health_probe_uses_supported_qdrant_client_lifecycle(tmp_path):
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    from src.backend.app.services.health import _vector_probe
    client = QdrantClient(":memory:")
    client.create_collection("test", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    settings = config(tmp_path).model_copy(update={"QDRANT_COLLECTION": "test"})
    result = _vector_probe(settings, lambda **kwargs: client)
    assert result == {"points": 0, "dimensions": 2}


def test_uploaded_source_uses_registry_and_validates_local_fallback_root(tmp_path):
    from src.backend.app.models.database import FileArtifact
    class Storage:
        def download_url(self, *args, **kwargs):
            raise FileNotFoundError()
        def close(self):
            pass
    settings = config(tmp_path)
    settings.UPLOAD_DIR.mkdir()
    source = settings.UPLOAD_DIR / "source.pdf"
    source.write_bytes(b"%PDF-registry-test")
    app = create_app(settings=settings, storage_factory=Storage)
    with TestClient(app) as client:
        with app.state.database.session() as db:
            db.add(FileArtifact(id="uploaded", record={
                "artifact_id": "uploaded", "path": str(source), "file_name": "source.pdf",
                "format": "pdf", "storage_backend": "r2", "r2": {"verified_at": "today"},
            }))
            db.commit()
        response = client.get("/api/files/uploaded")
        assert response.status_code == 200 and response.content == source.read_bytes()
        assert response.headers["x-storage-backend"] == "local-fallback"
        with app.state.database.session() as db:
            record = db.get(FileArtifact, "uploaded")
            record.record = {**record.record, "path": str(tmp_path / "outside-upload-root.txt")}
            db.commit()
        assert client.get("/api/files/uploaded").status_code == 410
