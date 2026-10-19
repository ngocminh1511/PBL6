"""Unit tests for labor_rag.ingest.pdf_to_chunks (OCR tree -> chunk v5) and
labor_rag.ingest.merge (which version of a Dieu to keep). No OCR model,
tokenizer or Qdrant is used; tokens are counted as words.

Needs the OCR dependencies (requirements-ocr.txt). Run from the repository root:
  python tests/test_pdf_to_chunks.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.ingest.merge import plan_upsert
from labor_rag.ingest.pdf_to_chunks import KgIndex, article_body, document_to_chunks
from labor_rag.ocr.structure import extract_metadata, parse_structure

SAMPLE_LAW = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
QUỐC HỘI
Số: 45/2019/QH14
BỘ LUẬT LAO ĐỘNG
Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;
Chương I. NHỮNG QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Bộ luật này quy định như sau:
1. Bộ luật này quy định tiêu chuẩn lao động.
2. Người lao động có các quyền sau đây:
a) Làm việc, tự do lựa chọn việc làm;
b) Hưởng lương phù hợp với trình độ;
Chương II. VIỆC LÀM
Mục 1. Quy định chung
Điều 3. Quyền làm việc
1. Mọi người đều có quyền làm việc.
Điều 3a. Việc làm bền vững
Nhà nước khuyến khích việc làm bền vững.
Điều 220. Hiệu lực thi hành
Bộ luật này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021.
"""


def words(text: str) -> int:
    return len(text.split()) + 2


def sample_document():
    doc = parse_structure(SAMPLE_LAW)
    doc.metadata = extract_metadata(SAMPLE_LAW, doc.title)
    doc.document_id = "45-2019-qh14"
    return doc


KG = KgIndex(
    {("45-2019-qh14", "1"): "20.2.LQ.1", ("45-2019-qh14", "3"): "20.2.LQ.3"},
    {"45-2019-qh14": {"ten": "Bộ luật số 45/2019/QH14", "effective_date": "2021-01-01"}},
)


def by_id(chunks):
    return {chunk["chunk_id"]: chunk for chunk in chunks}


def test_article_body_restores_markers():
    article = next(sample_document().iter_articles())
    assert article_body(article).split("\n") == [
        "Bộ luật này quy định như sau:",
        "1. Bộ luật này quy định tiêu chuẩn lao động.",
        "2. Người lao động có các quyền sau đây:",
        "a) Làm việc, tự do lựa chọn việc làm;",
        "b) Hưởng lương phù hợp với trình độ;",
    ]


def test_document_to_chunks_fields():
    chunks, warnings = document_to_chunks(sample_document(), KG)
    assert not warnings
    chunks = by_id(chunks)
    assert list(chunks) == ["45-2019-qh14:d1", "45-2019-qh14:d3", "45-2019-qh14:d3a", "45-2019-qh14:d220"]
    first = chunks["45-2019-qh14:d1"]
    assert first["source"] == "pdf" and first["mapc"] == "20.2.LQ.1"
    assert first["meta_de_muc"] == "Bộ luật số 45/2019/QH14"  # the Phap dien title, so both sources match
    assert first["meta_chuong"] == "I" and first["meta_muc"] is None and first["pd_chuong"] is None
    assert first["text"].split("\n")[:3] == [
        "Bộ luật số 45/2019/QH14 > Chương I. NHỮNG QUY ĐỊNH CHUNG",
        "Điều 1. Phạm vi điều chỉnh",
        "Bộ luật này quy định như sau:",
    ]
    assert first["effective_from_date"] == "2021-01-01" and first["version_date"] == "2021-01-01"
    third = chunks["45-2019-qh14:d3"]
    assert third["meta_chuong"] == "II" and third["meta_muc"] == "1"
    assert "Chương II. VIỆC LÀM > Mục 1. Quy định chung" in third["text"]
    assert chunks["45-2019-qh14:d3a"]["mapc"] is None  # not in Phap dien


def test_without_kg_uses_own_metadata():
    chunks, _ = document_to_chunks(sample_document())
    first = chunks[0]
    assert first["meta_de_muc"] == "Bộ luật số 45/2019/QH14"
    assert first["mapc"] is None and first["effective_from_date"] == "2021-01-01"


def test_long_article_is_split():
    clauses = "\n".join(f"{n}. " + " ".join(f"từ{n}_{i}" for i in range(30)) + "." for n in range(1, 7))
    doc = parse_structure(f"Chương I. CHUNG\nĐiều 1. Phạm vi điều chỉnh\nCác quy định sau đây:\n{clauses}")
    doc.document_id = "45-2019-qh14"
    chunks, _ = document_to_chunks(doc, KG, words, max_tokens=120)
    assert [c["chunk_id"] for c in chunks][:2] == ["45-2019-qh14:d1:p1", "45-2019-qh14:d1:p2"]
    assert all(words(c["text"]) <= 120 and c["mapc"] == "20.2.LQ.1" for c in chunks)
    assert all("Các quy định sau đây:" in c["text"] for c in chunks)
    assert len({c["content_hash"] for c in chunks}) == 1 and chunks[0]["meta_khoan"].startswith("1")


def test_repeated_article_number_is_reported():
    doc = parse_structure("Điều 1. A\nNội dung.\nĐiều 1. B\nNội dung khác.")
    doc.document_id = "x"
    chunks, warnings = document_to_chunks(doc)
    assert [c["chunk_id"] for c in chunks] == ["x:d1"] and len(warnings) == 1


def test_appendix_chunk():
    doc = parse_structure("Điều 1. A\nNội dung.\nPHỤ LỤC I\nMẫu số 01\nDanh sách lao động")
    doc.document_id = "x"
    chunks, _ = document_to_chunks(doc)
    appendix = by_id(chunks)["x:pl1"]
    assert appendix["meta_dieu"] is None and appendix["ten"] == "Phụ lục"
    assert "Mẫu số 01" in appendix["text"]


# --- merge.plan_upsert ---------------------------------------------------------


def chunk(chunk_id, source, version, text="t"):
    return {"chunk_id": chunk_id, "document_id": chunk_id.split(":")[0], "source": source, "version_date": version, "text": text}


def test_newer_pdf_replaces_every_phap_dien_part():
    old = [chunk("d:d35:p1", "phap_dien", "2021-01-01"), chunk("d:d35:p2", "phap_dien", "2021-01-01")]
    new = [chunk("d:d35", "pdf", "2026-07-01")]
    plan = plan_upsert(old, new)
    assert plan.delete == ["d:d35:p1", "d:d35:p2"] and [c["chunk_id"] for c in plan.upsert] == ["d:d35"]


def test_older_pdf_keeps_phap_dien():
    plan = plan_upsert([chunk("d:d35", "phap_dien", "2026-01-01")], [chunk("d:d35", "pdf", "2021-01-01", "old")])
    assert plan.kept == ["d:d35"] and not plan.upsert and not plan.delete


def test_tie_keeps_phap_dien_and_same_source_replaces():
    plan = plan_upsert([chunk("d:d1", "phap_dien", "2021-01-01")], [chunk("d:d1", "pdf", "2021-01-01", "x")])
    assert plan.kept == ["d:d1"]
    plan = plan_upsert([chunk("d:d1", "pdf", "2021-01-01")], [chunk("d:d1", "pdf", "2021-01-01", "fixed")])
    assert plan.delete == ["d:d1"] and len(plan.upsert) == 1
    plan = plan_upsert([chunk("d:d1", "pdf", "2021-01-01")], [chunk("d:d1", "pdf", "2021-01-01")])
    assert plan.unchanged == ["d:d1"] and not plan.upsert


def test_new_and_missing_articles():
    old = [chunk("d:d1", "phap_dien", "2021-01-01"), chunk("d:d2", "phap_dien", "2021-01-01")]
    new = [chunk("d:d1", "pdf", "2026-01-01", "new"), chunk("d:d3a", "pdf", "2026-01-01")]
    plan = plan_upsert(old, new)
    assert sorted(c["chunk_id"] for c in plan.upsert) == ["d:d1", "d:d3a"]
    assert plan.delete == ["d:d1"]
    assert len(plan.warnings) == 1 and plan.warnings[0].startswith("d:d2 ")



def test_same_text_new_metadata_is_refreshed_not_embedded():
    old = [{**chunk("d:d1", "phap_dien", "2022-07-15"), "amended_by": []}]
    new = [chunk("d:d1", "phap_dien", "2021-02-01")]
    plan = plan_upsert(old, new)
    assert plan.refresh == new and not plan.upsert and not plan.delete
    # Nothing changed: nothing to do.
    plan = plan_upsert([{**new[0], "dataset_id": "lao_dong_v5"}], new)
    assert plan.unchanged == ["d:d1"] and not plan.refresh


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
