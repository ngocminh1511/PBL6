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


@pytest.fixture(autouse=True)
def mock_intent_llm(monkeypatch):
    import labor_rag.generation.intent as intent
    monkeypatch.setattr(intent, "complete", lambda *args, **kwargs: "LEGAL")


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


@pytest.mark.parametrize("status, message", [(429, "hạn mức"), (413, "vượt giới hạn"), (401, "xác thực")])
def test_chat_reports_safe_provider_failure_without_saving_an_answer(tmp_path, monkeypatch, caplog, status, message):
    from labor_rag.services.chat import ChatPipeline
    import labor_rag.generation.answer as generation
    import labor_rag.generation.intent as intent

    cause = RuntimeError("private-provider-key-and-prompt")
    cause.status_code = status

    def fail_generation(*args, **kwargs):
        raise cause

    monkeypatch.setattr(intent, "is_legal_query", lambda *args: True)
    monkeypatch.setattr(generation, "generate_answer", fail_generation)
    app = create_app(settings=config(tmp_path))
    retriever = SimpleNamespace(retrieve=lambda *args, **kwargs: [], graph_warning=None)
    monkeypatch.setattr(app.state.runtime, "chat",
        lambda: ChatPipeline(retriever, app.state.runtime.catalog, app.state.runtime.settings))

    with TestClient(app) as client:
        response = client.post("/api/chat/ask", json={"question": "Người dưới 15 tuổi không được làm gì?"})
        assert response.status_code == 503
        assert "generation" in response.json()["detail"] and message in response.json()["detail"]
        assert "private-provider-key-and-prompt" not in response.text + caplog.text
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
    assert {"attachments", "warnings", "token_usage"} <= {c["name"] for c in inspect(engine).get_columns("chat_messages")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT content FROM chat_messages WHERE id='old'")).scalar() == "keep me"
        assert connection.execute(text("SELECT count(*) FROM app_schema_versions")).scalar() == 2


def test_token_usage_migration_upgrades_an_already_versioned_database():
    from src.backend.app.migrations import upgrade
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE app_schema_versions (revision VARCHAR(100) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO app_schema_versions VALUES ('001_unified_backend')"))
        connection.execute(text("CREATE TABLE chat_messages (id VARCHAR(36) PRIMARY KEY, content TEXT)"))
        connection.execute(text("INSERT INTO chat_messages VALUES ('old', 'keep me')"))
    upgrade(engine)
    upgrade(engine)
    with engine.connect() as connection:
        old = connection.execute(text("SELECT content, token_usage FROM chat_messages WHERE id='old'")).one()
        assert old == ("keep me", None)
        assert connection.execute(text("SELECT count(*) FROM app_schema_versions")).scalar() == 2


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


def test_upload_pdf_other_domain_ocr_storage_and_listing(tmp_path, monkeypatch):
    import labor_rag.ingest.chunk_schema as chunk_schema
    import labor_rag.ocr.pipeline as ocr_pipeline
    import labor_rag.services.ingestion as ingestion
    from labor_rag.ocr.schemas import Article, Chapter, Clause, DocumentMetadata, LegalDocument, Point

    seen_progress = []
    doc = LegalDocument(
        document_id="91-2015-qh13",
        title="Bộ luật Dân sự 2015",
        full_text="TOÀN VĂN DÀI KHÔNG ĐƯỢC HIỂN THỊ Ở ROOT",
        metadata=DocumentMetadata(so_hieu="91/2015/QH13", loai_van_ban="Bộ luật", ngay_hieu_luc="2017-01-01"),
        chapters=[
            Chapter(
                chapter_id="chuong_1",
                chapter_number="Chương I",
                chapter_title="NHỮNG QUY ĐỊNH CHUNG",
                articles=[
                    Article(
                        article_id="dieu_1",
                        article_number="Điều 1",
                        article_title="Phạm vi điều chỉnh",
                        clauses=[
                            Clause(
                                clause_id="dieu_1_khoan_1",
                                clause_number="Khoản 1",
                                text="Bộ luật này quy định địa vị pháp lý.",
                                points=[Point(point_id="dieu_1_khoan_1_diem_a", point_label="a", text="Quyền nhân thân.")],
                            )
                        ],
                    )
                ],
            )
        ],
    )

    def fake_process_document(path, settings=None, progress=None, **kwargs):
        if progress:
            progress("OCR trang 1/1", 100.0)
        return SimpleNamespace(document=doc)

    monkeypatch.setattr(ocr_pipeline, "process_document", fake_process_document)
    monkeypatch.setattr(chunk_schema, "TokenCounter", lambda *args, **kwargs: (lambda text: len(text.split())))
    monkeypatch.setattr(ingestion, "store_artifact", lambda p, store, role: {
        "artifact_id": f"art-{role}", "file_name": p.name, "format": p.suffix.lstrip("."),
    })
    def fake_index(self, chunks, projection, progress, cancel_check=None):
        seen_progress.append(len(chunks))
        assert chunks[0]["domain"] == "khac"
        return {"warnings": [], "embedded_chunks": len(chunks)}
    monkeypatch.setattr(ingestion.IngestionPipeline, "index", fake_index)

    app = create_app(settings=config(tmp_path), storage_factory=lambda: SimpleNamespace(close=lambda: None))
    with TestClient(app) as client:
        bad = client.post("/api/documents/upload", data={"document_type": "phap_dien_html", "domain": "khac"},
                          files={"file": ("item.html", b"<html></html>", "text/html")})
        assert bad.status_code == 422

        response = client.post("/api/documents/upload", data={"document_type": "pdf", "domain": "khac", "pause_for_review": "false"},
                               files={"file": ("blds.pdf", b"%PDF-1.4 test", "application/pdf")})
        assert response.status_code == 202
        app.state.ingestion.executor.shutdown(wait=True)
        task = client.get("/api/documents/tasks/" + response.json()["task_id"] + "/progress").json()
        assert task["status"] == "completed"
        assert task["document_id"] == "91-2015-qh13"
        assert seen_progress == [1]

        assert (tmp_path / "interim" / "pdf_chunks" / "91-2015-qh13_hierarchical.jsonl").exists()
        assert (tmp_path / "interim" / "pdf_chunks" / "91-2015-qh13_chunks.jsonl").exists()

        listing = client.get("/api/documents/list?domain=khac")
        assert listing.status_code == 200
        items = listing.json()["items"]
        assert any(i["id"] == "91-2015-qh13" and i["domain"] == "khac" and i["articles_count"] == 1
                   and i["clauses_count"] == 1 and i["points_count"] == 1 for i in items)

        ast = client.get("/api/documents/91-2015-qh13/ast")
        assert ast.status_code == 200
        tree = ast.json()["ast_tree"]
        assert not tree.get("text")
        assert tree["children"][0]["type"] == "chapter"
        assert tree["children"][0]["children"][0]["article_number"] == "1"


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


def test_realtime_ocr_page_callback_and_preview_endpoints(tmp_path, monkeypatch):
    import labor_rag.ocr.extract as ocr_extract
    import labor_rag.ocr.pipeline as ocr_pipeline
    import labor_rag.ingest.chunk_schema as chunk_schema
    import labor_rag.services.ingestion as ingestion
    from labor_rag.ocr.classifier import PageClass, PageType
    from labor_rag.ocr.extract import ExtractionResult, PageText
    from labor_rag.ocr.schemas import Article, DocumentMetadata, LegalDocument

    # 1. _extract_pdf invokes page_callback for both text and scanned OCR pages
    class FakeDoc:
        needs_pass = False
        def __getitem__(self, idx):
            return SimpleNamespace(idx=idx)

    seen_callbacks = []
    monkeypatch.setattr(
        ocr_extract,
        "classify_document",
        lambda doc: [PageClass(0, PageType.TEXT, 100), PageClass(1, PageType.SCANNED, 0)],
    )
    monkeypatch.setattr(ocr_extract, "extract_page_text", lambda page: "QUỐC HỘI\nĐiều 1. Phạm vi")
    monkeypatch.setattr(ocr_extract, "render_page", lambda page: SimpleNamespace())
    monkeypatch.setattr(ocr_extract, "ocr_image", lambda img: SimpleNamespace(text="Điều 2. Đối tượng áp dụng", confidence=0.91))

    extracted = ocr_extract._extract_pdf(
        FakeDoc(),
        "demo.pdf",
        use_ocr=True,
        progress=None,
        page_callback=lambda pt, total: seen_callbacks.append((pt.page_number, pt.method, pt.confidence, total, pt.text)),
    )
    assert len(extracted.pages) == 2
    assert seen_callbacks == [
        (0, "text", None, 2, "QUỐC HỘI\nĐiều 1. Phạm vi"),
        (1, "ocr", 0.91, 2, "Điều 2. Đối tượng áp dụng"),
    ]

    # 2. Upload flow populates realtime ocr_preview + /ocr-page/{n} + supports mid-OCR cancel
    doc = LegalDocument(
        document_id="12-2026-qh15",
        title="Luật thử nghiệm OCR",
        metadata=DocumentMetadata(so_hieu="12/2026/QH15", loai_van_ban="Luật", ngay_hieu_luc="2026-07-01"),
        articles=[Article(article_id="dieu_1", article_number="Điều 1", article_title="Phạm vi", full_text="Nội dung.")],
    )
    mid_page_checked = Event()
    release_ocr = Event()

    def fake_process_document(path, settings=None, progress=None, page_callback=None, **kwargs):
        p1 = PageText(0, "Trang một có chữ dài " + ("abc " * 200), "text")
        if page_callback:
            page_callback(p1, 2)
        if progress:
            progress("OCR trang 2/2", 50.0)
        mid_page_checked.set()
        assert release_ocr.wait(timeout=5)
        p2 = PageText(1, "Điều 1. Phạm vi áp dụng OCR.", "ocr", 0.92)
        if page_callback:
            page_callback(p2, 2)
        if progress:
            progress("OCR xong", 100.0)
        return SimpleNamespace(
            document=doc,
            extraction=ExtractionResult(source_name="ocr.pdf", pages=[p1, p2], warnings=[]),
            ocr_quality={"heuristic_score": 88.5},
        )

    monkeypatch.setattr(ocr_pipeline, "process_document", fake_process_document)
    monkeypatch.setattr(chunk_schema, "TokenCounter", lambda *args, **kwargs: (lambda text: len(text.split())))
    monkeypatch.setattr(ingestion, "store_artifact", lambda p, store, role: {
        "artifact_id": f"art-{role}", "file_name": p.name, "format": p.suffix.lstrip("."),
    })
    monkeypatch.setattr(
        ingestion.IngestionPipeline,
        "index",
        lambda self, chunks, projection, progress, cancel_check=None: {"warnings": [], "embedded_chunks": len(chunks)},
    )

    app = create_app(settings=config(tmp_path), storage_factory=lambda: SimpleNamespace(close=lambda: None))
    with TestClient(app) as client:
        res = client.post(
            "/api/documents/upload",
            data={"document_type": "pdf", "domain": "khac", "pause_for_review": "false"},
            files={"file": ("ocr.pdf", b"%PDF-1.4 demo", "application/pdf")},
        )
        assert res.status_code == 202
        task_id = res.json()["task_id"]
        assert mid_page_checked.wait(timeout=5)

        mid_progress = client.get(f"/api/documents/tasks/{task_id}/progress").json()
        assert mid_progress["ocr_preview"]["total_pages"] == 2
        assert mid_progress["ocr_preview"]["processed_pages"] == 1
        assert mid_progress["ocr_preview"]["text_pages"] == 1
        assert mid_progress["ocr_preview"]["recent_pages"][0]["page_number"] == 1
        assert len(mid_progress["ocr_preview"]["recent_pages"][0]["preview_text"]) <= 600

        full_p1 = client.get(f"/api/documents/tasks/{task_id}/ocr-page/1")
        assert full_p1.status_code == 200
        assert len(full_p1.json()["text"]) > 600

        release_ocr.set()
        app.state.ingestion.executor.shutdown(wait=True)

        done_progress = client.get(f"/api/documents/tasks/{task_id}/progress").json()
        assert done_progress["status"] == "completed"
        assert done_progress["ocr_preview"]["processed_pages"] == 2
        assert done_progress["ocr_preview"]["ocr_pages"] == 1
        assert done_progress["ocr_preview"]["avg_confidence"] == pytest.approx(0.92, abs=1e-4)
        assert done_progress["ocr_preview"]["heuristic_score"] == pytest.approx(88.5, abs=1e-2)
        assert done_progress["ocr_preview"]["articles_count"] == 1
        assert client.get(f"/api/documents/tasks/{task_id}/ocr-page/2").json()["text"] == "Điều 1. Phạm vi áp dụng OCR."


def test_two_phase_ocr_review_edit_confirm_and_pdf_image(tmp_path, monkeypatch):
    import time
    import pymupdf
    import labor_rag.ingest.chunk_schema as chunk_schema
    import labor_rag.ingest.ontology_to_jsonl as projection
    import labor_rag.ocr.extract as ocr_extract
    import labor_rag.services.ingestion as ingestion
    from labor_rag.ocr.extract import ExtractionResult, PageText

    # Build a tiny real 2-page PDF so PyMuPDF image rendering is tested end-to-end.
    pdf_doc = pymupdf.open()
    for page_idx in range(2):
        page = pdf_doc.new_page()
        page.insert_text((72, 72), f"Page {page_idx + 1}")
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    def fake_extract_text(source, filename=None, use_ocr=True, progress=None, page_callback=None):
        p1 = PageText(0, "LUẬT THỬ NGHIỆM\nSố: 88/2026/QH15\nĐiều 1. Phạm vi\nNội dung sai chinh ta.", "ocr", 0.72)
        p2 = PageText(1, "Điều 2. Hiệu lực thi hành\nCó hiệu lực từ 01/01/2027.", "text")
        if page_callback:
            page_callback(p1, 2)
            page_callback(p2, 2)
        if progress:
            progress("OCR xong", 100.0)
        return ExtractionResult(source_name=filename or "review.pdf", pages=[p1, p2], warnings=[])

    monkeypatch.setattr("labor_rag.ocr.pipeline.extract_text", fake_extract_text)
    monkeypatch.setattr(chunk_schema, "TokenCounter", lambda *args, **kwargs: (lambda text: len(text.split())))
    monkeypatch.setattr(projection, "TokenCounter", lambda *args, **kwargs: (lambda text: len(text.split())))
    monkeypatch.setattr(ingestion, "store_artifact", lambda p, store, role: {
        "artifact_id": f"art-{role}", "file_name": p.name, "format": p.suffix.lstrip("."),
    })
    indexed_chunks = []
    def fake_index(self, chunks, proj_dir, progress, cancel_check=None):
        indexed_chunks.extend(chunks)
        return {"warnings": [], "embedded_chunks": len(chunks)}
    monkeypatch.setattr(ingestion.IngestionPipeline, "index", fake_index)

    app = create_app(settings=config(tmp_path), storage_factory=lambda: SimpleNamespace(close=lambda: None))
    with TestClient(app) as client:
        # Task 1: default pause_for_review=True -> stops at awaiting_review -> edit -> confirm
        up = client.post(
            "/api/documents/upload",
            data={"document_type": "pdf", "domain": "khac"},
            files={"file": ("review.pdf", pdf_bytes, "application/pdf")},
        )
        assert up.status_code == 202
        task_id = up.json()["task_id"]

        for _ in range(50):
            prog = client.get(f"/api/documents/tasks/{task_id}/progress").json()
            if prog["status"] == "awaiting_review":
                break
            time.sleep(0.05)
        assert prog["status"] == "awaiting_review"
        assert indexed_chunks == []  # Phase 2 has NOT run yet

        # Confirm while in awaiting_review cannot edit when wrong page or non-review, and PDF image renders
        img1 = client.get(f"/api/documents/tasks/{task_id}/pdf-page/1")
        assert img1.status_code == 200
        assert img1.headers["content-type"] == "image/png"
        assert img1.content.startswith(b"\x89PNG")
        assert client.get(f"/api/documents/tasks/{task_id}/pdf-page/3").status_code == 404

        # Manual edit page 1
        edited_text = "LUẬT THỬ NGHIỆM\nSố: 88/2026/QH15\nĐiều 1. Phạm vi\nNội dung đã sửa chính tả chuẩn."
        put_res = client.put(
            f"/api/documents/tasks/{task_id}/ocr-page/1",
            json={"text": edited_text},
        )
        assert put_res.status_code == 200
        assert put_res.json()["text"] == edited_text
        assert client.get(f"/api/documents/tasks/{task_id}/ocr-page/1").json()["text"] == edited_text

        # Confirm -> triggers Phase 2 with the edited text
        conf_res = client.post(f"/api/documents/tasks/{task_id}/confirm")
        assert conf_res.status_code == 200
        assert conf_res.json()["status"] == "chunking"

        for _ in range(80):
            done = client.get(f"/api/documents/tasks/{task_id}/progress").json()
            if done["status"] in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert done["status"] == "completed", done
        assert done["document_id"] == "88-2026-qh15"
        assert any("Nội dung đã sửa chính tả chuẩn." in c["text"] for c in indexed_chunks)

        ast = client.get("/api/documents/88-2026-qh15/ast").json()
        assert "Nội dung đã sửa chính tả chuẩn." in str(ast["ast_tree"])

        # Task 2: cancel cleanly while awaiting_review
        up2 = client.post(
            "/api/documents/upload",
            data={"document_type": "pdf", "domain": "khac"},
            files={"file": ("cancel_me.pdf", pdf_bytes, "application/pdf")},
        )
        task2_id = up2.json()["task_id"]
        for _ in range(50):
            if client.get(f"/api/documents/tasks/{task2_id}/progress").json()["status"] == "awaiting_review":
                break
            time.sleep(0.05)
        cancel_res = client.post(f"/api/documents/tasks/{task2_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"


