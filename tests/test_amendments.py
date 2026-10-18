"""Unit tests for article-level amendments: the Phap dien citation
(build_abox -> ontology_to_jsonl amended_by / version_date), amending
documents (amending, pdf_to_chunks), the amended_by update of embed_and_index
and the retrieval side. No data files, OCR model, tokenizer or Qdrant are used.

Run from the repository root:
  python tests/test_amendments.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.ingest.amending import actions_in, amended_by_updates, merge_amended_by, parse_targets
from labor_rag.ingest.build_abox import INST, VLD, AboxBuilder
from labor_rag.ingest.ontology_to_jsonl import amendments, version_date
from labor_rag.ingest.pdf_to_chunks import KgIndex, document_to_chunks
from labor_rag.ocr.structure import extract_metadata, parse_structure
from labor_rag.retrieval.hybrid_retrieve import Evidence, amending_parts, pending_amendments

CITATION = (
    "( Điều 3 Nghị định số 152/2020/NĐ-CP, có hiệu lực thi hành kể từ ngày 15/02/2021, "
    "có nội dung được sửa đổi, có nội dung được bổ sung bởi Điều 1 Nghị định số 70/2023/NĐ-CP "
    "có hiệu lực thi hành kể từ ngày 18/09/2023)"
)


def test_actions_in():
    assert actions_in(", có nội dung được sửa đổi, có nội dung bị bãi bỏ bởi ") == ["sua_doi", "bai_bo"]
    assert actions_in(", ") == []


def test_sources_keep_amending_article_and_actions():
    codified, amending = AboxBuilder().sources(CITATION)
    assert (codified.article, codified.effective, codified.actions) == ("3", "2021-02-15", [])
    assert (amending.article, amending.effective, amending.actions) == ("1", "2023-09-18", ["sua_doi", "bo_sung"])


def projection(citation: str):
    builder = AboxBuilder()
    sources = builder.sources(citation)
    source_uri = builder.add_source_mapping(INST["Article_x"], sources[0].document, sources[0].article, "body")
    for amending in sources[1:]:
        builder.add_amendment(source_uri, sources[0].document, amending)
    # The document nodes ontology_to_jsonl would build: only document_number is read.
    nodes = {
        str(doc): {"uri": str(doc), "document_number": str(so_hieu)}
        for doc, so_hieu in builder.graph.subject_objects(VLD.documentNumber)
    }
    return amendments(builder.graph, nodes)


def test_amended_by_per_article():
    amended_by, amends = projection(CITATION)
    entries = amended_by["152-2020-nd-cp:d3"]
    assert [entry["action"] for entry in entries] == ["sua_doi", "bo_sung"]
    assert {(entry["by"], entry["scope"], entry["date"]) for entry in entries} == {("70-2023-nd-cp:d1", None, "2023-09-18")}
    assert [entry["target"] for entry in amends["70-2023-nd-cp:d1"]] == ["152-2020-nd-cp:d3", "152-2020-nd-cp:d3"]


def test_version_date_only_from_own_amendments():
    document = {"effective_date": "2021-02-15"}
    assert version_date(document, []) == "2021-02-15"
    assert version_date(document, [{"date": "2023-09-18"}]) == "2023-09-18"


AMENDING_DECREE = """CHÍNH PHỦ
Số: 70/2023/NĐ-CP
NGHỊ ĐỊNH
Sửa đổi, bổ sung một số điều của Nghị định số 152/2020/NĐ-CP
Điều 1. Sửa đổi, bổ sung một số điều của Nghị định số 152/2020/NĐ-CP
1. Sửa đổi, bổ sung khoản 2 Điều 3 như sau:
“2. Người lao động nước ngoài làm việc tại Việt Nam theo hình thức sau.”
2. Bãi bỏ điểm b khoản 3 Điều 10.
3. Bổ sung Điều 7a vào sau Điều 7 như sau:
“Điều 7a. Báo cáo
Người sử dụng lao động báo cáo hằng năm.”
Điều 2. Hiệu lực thi hành
Nghị định này có hiệu lực thi hành từ ngày 18 tháng 9 năm 2023.
"""


def test_parse_targets():
    default = "145-2020-nd-cp"
    (target,) = parse_targets("Sửa đổi, bổ sung khoản 2 Điều 35 như sau: “2. ... theo Điều 36”", default)
    assert (target.article, target.scope, target.actions) == ("145-2020-nd-cp:d35", "khoản 2", ["sua_doi", "bo_sung"])
    (target,) = parse_targets("Bổ sung Điều 35a vào sau Điều 35 như sau:", default)
    assert (target.article, target.scope) == ("145-2020-nd-cp:d35", "Điều 35a")
    (target,) = parse_targets("Thay thế cụm từ “Điều 5” bằng cụm từ “Điều 6” tại khoản 1 Điều 9.", default)
    assert (target.article, target.scope, target.actions) == ("145-2020-nd-cp:d9", "khoản 1", ["thay_cum_tu"])
    first, second = parse_targets("Sửa đổi khoản 1, khoản 2 Điều 5 và điểm a khoản 3 Điều 7 Nghị định số 152/2020/NĐ-CP", default)
    assert (first.article, first.scope) == ("152-2020-nd-cp:d5", "khoản 1, khoản 2")
    assert (second.article, second.scope) == ("152-2020-nd-cp:d7", "điểm a khoản 3")
    assert parse_targets("Sửa đổi tên Chương II như sau:", default) == []


def amending_chunks():
    doc = parse_structure(AMENDING_DECREE)
    doc.metadata = extract_metadata(AMENDING_DECREE, doc.title)
    doc.document_id = "70-2023-nd-cp"
    kg = KgIndex(
        {},
        {"152-2020-nd-cp": {"ten": "Nghị định số 152/2020/NĐ-CP"}},
        {("152-2020-nd-cp", "3"): "Hình thức làm việc"},
    )
    chunks, warnings = document_to_chunks(doc, kg)
    assert not warnings
    return {chunk["chunk_id"]: chunk for chunk in chunks}


def test_amending_dieu_is_cut_per_khoan():
    chunks = amending_chunks()
    assert list(chunks) == ["70-2023-nd-cp:d1:p1", "70-2023-nd-cp:d1:p2", "70-2023-nd-cp:d1:p3", "70-2023-nd-cp:d2"]
    first = chunks["70-2023-nd-cp:d1:p1"]
    assert first["meta_khoan"] == "1"
    assert first["text"].splitlines()[2] == (
        "Sửa đổi, bổ sung khoản 2 Điều 3 Nghị định số 152/2020/NĐ-CP (Điều 3. Hình thức làm việc)"
    )
    date = first["effective_from_date"]
    assert first["amends"] == [
        {"target": "152-2020-nd-cp:d3", "scope": "khoản 2", "action": "sua_doi", "date": date},
        {"target": "152-2020-nd-cp:d3", "scope": "khoản 2", "action": "bo_sung", "date": date},
    ]
    assert chunks["70-2023-nd-cp:d1:p3"]["amends"][0]["target"] == "152-2020-nd-cp:d7"
    assert chunks["70-2023-nd-cp:d2"]["amends"] == []


def test_amended_by_updates_and_merge():
    updates = amended_by_updates(list(amending_chunks().values()))
    assert sorted(updates) == ["152-2020-nd-cp:d10", "152-2020-nd-cp:d3", "152-2020-nd-cp:d7"]
    entries = updates["152-2020-nd-cp:d10"]
    assert [(e["by"], e["scope"], e["action"]) for e in entries] == [("70-2023-nd-cp:d1", "điểm b khoản 3", "bai_bo")]
    phap_dien = {"by": "35-2022-nd-cp:d73", "scope": None, "action": "sua_doi", "date": "2022-07-15"}
    stale = {**entries[0], "date": "2000-01-01"}
    assert merge_amended_by([phap_dien, stale], entries) == [phap_dien, *entries]


def test_retrieval_attaches_only_pending_amendments():
    consolidated = {"by": "35-2022-nd-cp:d73", "scope": None, "action": "sua_doi", "date": "2022-07-15"}
    pending = {"by": "70-2023-nd-cp:d1", "scope": "khoản 2", "action": "sua_doi", "date": "2023-09-18"}
    evidence = Evidence("152-2020-nd-cp:d3", None, "", "", "vector", version_date="2022-07-15", amended_by=[consolidated, pending])
    assert pending_amendments(evidence) == ["70-2023-nd-cp:d1"]
    parts = amending_parts(list(amending_chunks().values()), "70-2023-nd-cp:d1", "152-2020-nd-cp:d3")
    assert [part["chunk_id"] for part in parts] == ["70-2023-nd-cp:d1:p1"]


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
