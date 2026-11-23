"""The change preview of a reviewed PDF: per-Dieu merge decision and amended
targets, read from an in-memory vector store and never written to it."""
import json
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from labor_rag.ingest.chunk_schema import point_id
from labor_rag.ocr.schemas import Article, Clause, DocumentMetadata, LegalDocument
from labor_rag.services.changes import preview_changes
from labor_rag.settings import Settings

DOC = "12-2022-nd-cp"


def article(number, title, text, clauses=()):
    return Article(article_id=f"dieu_{number}", article_number=f"Điều {number}", article_title=title,
                   full_text=text, clauses=[Clause(clause_id=f"k{i}", clause_number=f"Khoản {i}", text=t)
                                            for i, t in enumerate(clauses, 1)])


@pytest.fixture
def reviewed(tmp_path, monkeypatch):
    import labor_rag.ingest.chunk_schema as schema
    import labor_rag.ocr.pipeline as ocr
    document = LegalDocument(document_id=DOC, title="Nghị định 12/2022/NĐ-CP",
        metadata=DocumentMetadata(so_hieu="12/2022/NĐ-CP", loai_van_ban="Nghị định", version_date="2025-01-01"),
        articles=[
            article(1, "Phạm vi điều chỉnh", "Nội dung Điều 1 giữ nguyên."),
            article(2, "Sửa đổi, bổ sung một số điều của Nghị định số 145/2020/NĐ-CP", "",
                    ["Sửa đổi khoản 2 Điều 35 như sau: nội dung mới.", "Bãi bỏ Điều 40."]),
            article(3, "Đối tượng áp dụng", "Nội dung mới của Điều 3."),
        ])
    monkeypatch.setattr(ocr, "build_processed_document", lambda extraction: SimpleNamespace(document=document))
    monkeypatch.setattr(schema, "TokenCounter", lambda *args: lambda value: len(value.split()))
    work = tmp_path / "interim" / "ingestion" / "task"
    work.mkdir(parents=True)
    (work / "ocr_pages.jsonl").write_text(json.dumps({"page_number": 1, "text": "x", "method": "text"}) + "\n",
                                         encoding="utf-8")
    settings = Settings(_env_file=None, QDRANT_COLLECTION="test", QDRANT_URL="https://test",
                        INTERIM_DIR=tmp_path / "interim", UPLOAD_DIR=tmp_path / "uploads")
    return settings, tmp_path / "source.pdf"


def store_with(*payloads):
    store = QdrantClient(":memory:")
    store.create_collection("test", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    store.upsert("test", points=[PointStruct(id=point_id(p["chunk_id"]), vector=[1.0, 0.0], payload=p)
                                 for p in payloads])
    return store


def test_each_dieu_gets_the_merge_decision_and_amended_targets_are_listed(reviewed):
    from labor_rag.services.changes import build_reviewed_chunks
    settings, path = reviewed
    _, chunks = build_reviewed_chunks(settings, "task", path, "khac")
    same = next(c for c in chunks if c["chunk_id"] == f"{DOC}:d1")
    store = store_with(
        {**same},
        {"chunk_id": f"{DOC}:d3", "document_id": DOC, "text": "Nội dung cũ của Điều 3.", "source": "pdf",
         "version_date": "2020-01-01", "meta_dieu": "3", "ten": "Đối tượng áp dụng"},
        {"chunk_id": f"{DOC}:d9", "document_id": DOC, "text": "Điều chỉ có trong kho.", "source": "pdf",
         "version_date": "2020-01-01", "meta_dieu": "9", "ten": ""},
        {"chunk_id": "145-2020-nd-cp:d35", "document_id": "145-2020-nd-cp", "text": "Điều 35 hiện hành.",
         "source": "phap_dien", "version_date": "2021-02-01", "meta_dieu": "35", "ten": ""},
    )
    before = store.count("test", exact=True).count
    result = preview_changes(settings, "task", path, "khac", client=store_with())  # empty store first
    assert {a["label"]: a["status"] for a in result["articles"]} == {"Điều 1": "new", "Điều 2": "new", "Điều 3": "new"}

    result = preview_changes(settings, "task", path, "khac", client=store)
    status = {a["label"]: a["status"] for a in result["articles"]}
    assert status == {"Điều 1": "unchanged", "Điều 2": "new", "Điều 3": "replaced", "Điều 9": "missing"}
    replaced = next(a for a in result["articles"] if a["label"] == "Điều 3")
    assert replaced["old_text"] == "Nội dung cũ của Điều 3." and "Nội dung mới" in replaced["new_text"]
    targets = {(a["target_article"], tuple(a["actions"])): a for a in result["amendments"]}
    assert targets[("Điều 35", ("Sửa đổi",))]["current_text"] == "Điều 35 hiện hành."
    assert targets[("Điều 35", ("Sửa đổi",))]["scope"] == "khoản 2"
    assert targets[("Điều 40", ("Bãi bỏ",))]["target_indexed"] is False
    assert store.count("test", exact=True).count == before  # read only


def test_an_unreadable_store_is_reported_not_guessed(reviewed):
    settings, path = reviewed

    class Down:
        def scroll(self, *args, **kwargs):
            raise ConnectionError("store down")

        def close(self):
            pass

    result = preview_changes(settings, "task", path, "khac", client=Down())
    assert result["store"] == "unavailable" and "store down" in result["store_error"]
    assert result["articles"] and all(a["status"] is None for a in result["articles"])
    assert all(a["target_indexed"] is None for a in result["amendments"])
