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

from labor_rag.ingest.amending import (
    actions_in,
    amended_by_updates,
    merge_amended_by,
    parse_targets,
    replaced_by,
    replaced_documents,
)
from labor_rag.ingest.build_abox import INST, VLR, VLT, AboxBuilder
from labor_rag.ingest.ontology_to_jsonl import version_date
from labor_rag.ingest.pdf_to_chunks import KgIndex, document_to_chunks
from labor_rag.ocr.structure import extract_metadata, parse_structure
from labor_rag.retrieval.hybrid_retrieve import Evidence, amending_parts, in_force, pending_amendments

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


def phap_dien_graph(citation: str):
    """The ABox build_abox writes for one Phap dien Dieu with this citation."""
    builder = AboxBuilder()
    sources = builder.sources(citation)
    source_uri = builder.add_source_mapping(INST["Article_x"], sources[0].document, sources[0].article, "body")
    for amending in sources[1:]:
        amending_uri = builder.source_article(amending.document, amending.article)
        builder.add_amendment(
            source_uri, sources[0].document, amending_uri, amending.document, amending.actions, amending.effective,
            consolidated=True,
        )
    return builder, source_uri


def test_amendment_event_per_article():
    builder, source_uri = phap_dien_graph(CITATION)
    graph = builder.graph
    (event,) = graph.objects(source_uri, VLR.hasAmendment)
    assert str(source_uri).endswith("SourceArticle_Decree_152_2020_ND_CP_D3")
    assert str(event).endswith("Amendment_Decree_152_2020_ND_CP_D3_by_Decree_70_2023_ND_CP_D1")
    assert str(graph.value(event, VLR.amendingComponent)).endswith("SourceArticle_Decree_70_2023_ND_CP_D1")
    assert sorted(str(action) for action in graph.objects(event, VLR.amendmentAction)) == ["bo_sung", "sua_doi"]
    assert str(graph.value(event, VLT.amendsAt)) == "2023-09-18"


def test_version_date_counts_only_consolidated_amendments():
    builder, source_uri = phap_dien_graph(CITATION)
    document = {"effective_date": "2021-02-15"}
    assert version_date(builder.graph, source_uri, document) == "2023-09-18"
    # An amendment loaded later (from a PDF) is not in the Phap dien text.
    amended_doc = builder.document("Nghị định", "152/2020/NĐ-CP", None, None)
    later_doc = builder.document("Nghị định", "99/2025/NĐ-CP", None, "2025-07-01")
    later = builder.source_article(later_doc, "1")
    builder.add_amendment(source_uri, amended_doc, later, later_doc, ["sua_doi"], "2025-07-01")
    assert version_date(builder.graph, source_uri, document) == "2023-09-18"
    # Another Dieu of the amended document keeps its own date.
    other = builder.source_article(amended_doc, "4")
    assert version_date(builder.graph, other, document) == "2021-02-15"


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
1. Nghị định này có hiệu lực thi hành từ ngày 18 tháng 9 năm 2023.
2. Nghị định này thay thế Nghị định số 11/2016/NĐ-CP.
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


def test_replaced_documents():
    text = "Nghị định này thay thế Nghị định số 05/2015/NĐ-CP và Nghị định số 148/2018/NĐ-CP."
    assert replaced_documents("Hiệu lực thi hành", text, "145-2020-nd-cp") == ["05-2015-nd-cp", "148-2018-nd-cp"]
    text = "Thông tư số 10/2020/TT-BLĐTBXH hết hiệu lực kể từ ngày Thông tư này có hiệu lực."
    assert replaced_documents("Điều khoản thi hành", text) == ["10-2020-tt-bldtbxh"]
    # "thay thế" outside an effect Dieu is ordinary wording.
    assert replaced_documents("Thay thế người lao động", "Nghị định số 05/2015/NĐ-CP thay thế") == []


def test_effect_dieu_carries_replaces():
    chunks = amending_chunks()
    effect = chunks["70-2023-nd-cp:d2"]
    assert effect["replaces"] == ["11-2016-nd-cp"]
    assert replaced_by(list(chunks.values())) == {"11-2016-nd-cp": effect["effective_from_date"]}
    assert chunks["70-2023-nd-cp:d1:p1"]["replaces"] == []


def test_in_force_checks_effective_to_date():
    keys = {condition.key for clause in in_force().must[2:] for condition in clause.should if hasattr(condition, "key")}
    assert keys == {"effective_to_date"}


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
