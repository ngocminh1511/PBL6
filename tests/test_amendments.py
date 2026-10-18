"""Unit tests for article-level amendments and replacements: the Phap dien
citation (build_abox, ontology_to_jsonl version_date), amending / replacing
PDFs (amending, pdf_to_chunks, pdf_abox) and the retrieval side. No data
files, OCR model, tokenizer, Qdrant or Neo4j are used.

Run from the repository root:
  python tests/test_amendments.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.ingest.amending import DocumentRef, actions_in, parse_targets, replaced_documents
from labor_rag.ingest.build_abox import INST, VLPD, VLR, VLT, AboxBuilder
from labor_rag.ingest.ontology_to_jsonl import version_date
from labor_rag.ingest.pdf_abox import document_abox
from labor_rag.ingest.pdf_to_chunks import KgIndex, document_to_chunks
from labor_rag.ocr.structure import extract_metadata, parse_structure
from labor_rag.retrieval.hybrid_retrieve import amending_parts, change_text, in_force

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
    default = DocumentRef("Nghị định", "145/2020/NĐ-CP")
    (target,) = parse_targets("Sửa đổi, bổ sung khoản 2 Điều 35 như sau: “2. ... theo Điều 36”", default)
    assert (target.article, target.scope, target.actions) == ("145-2020-nd-cp:d35", "khoản 2", ["sua_doi", "bo_sung"])
    (target,) = parse_targets("Bổ sung Điều 35a vào sau Điều 35 như sau:", default)
    assert (target.article, target.scope) == ("145-2020-nd-cp:d35", "Điều 35a")
    (target,) = parse_targets("Thay thế cụm từ “Điều 5” bằng cụm từ “Điều 6” tại khoản 1 Điều 9.", default)
    assert (target.article, target.scope, target.actions) == ("145-2020-nd-cp:d9", "khoản 1", ["thay_cum_tu"])
    first, second = parse_targets("Sửa đổi khoản 1, khoản 2 Điều 5 và điểm a khoản 3 Điều 7 Nghị định số 152/2020/NĐ-CP", default)
    assert (first.article, first.scope, first.document) == ("152-2020-nd-cp:d5", "khoản 1, khoản 2", DocumentRef("Nghị định", "152/2020/NĐ-CP"))
    assert (second.article, second.scope) == ("152-2020-nd-cp:d7", "điểm a khoản 3")
    assert parse_targets("Sửa đổi tên Chương II như sau:", default) == []


KG = KgIndex(
    {},
    {"152-2020-nd-cp": {"ten": "Nghị định số 152/2020/NĐ-CP", "effective_date": "2021-02-15"}},
    {("152-2020-nd-cp", "3"): "Hình thức làm việc"},
)


def amending_decree():
    doc = parse_structure(AMENDING_DECREE)
    doc.metadata = extract_metadata(AMENDING_DECREE, doc.title)
    doc.document_id = "70-2023-nd-cp"
    return doc


def amending_chunks():
    chunks, warnings = document_to_chunks(amending_decree(), KG)
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
    # What the document changes is in its ABox, not in the chunks.
    assert not {"amends", "amended_by", "replaces"} & set(first)


def test_pdf_abox_holds_amendments_per_khoan_and_replacements():
    builder, stats = document_abox(amending_decree(), KG)
    graph = builder.graph
    assert stats == {"articles": 2, "amendments": 3, "replaces": 1}
    amended = INST["SourceArticle_Decree_152_2020_ND_CP_D3"]
    (event,) = graph.objects(amended, VLR.hasAmendment)
    assert graph.value(event, VLR.amendingComponent) == INST["SourceClause_Decree_70_2023_ND_CP_D1_K1"]
    assert sorted(str(a) for a in graph.objects(event, VLR.amendmentAction)) == ["bo_sung", "sua_doi"]
    assert str(graph.value(event, VLR.amendmentScope)) == "khoản 2"
    assert str(graph.value(event, VLT.amendsAt)) == "2023-09-18"
    # Not in the Phap dien text of Dieu 3, so it does not date it.
    assert graph.value(event, VLPD.consolidatedInCodification) is None
    assert version_date(graph, amended, {"effective_date": "2021-02-15"}) == "2021-02-15"
    # "Bổ sung Điều 7a vào sau Điều 7" hangs off Dieu 7.
    (inserted,) = graph.objects(INST["SourceArticle_Decree_152_2020_ND_CP_D7"], VLR.hasAmendment)
    assert str(graph.value(inserted, VLR.amendmentScope)) == "Điều 7a"
    # Replaced document: in force until this one takes effect.
    old = INST["Doc_Decree_11_2016_ND_CP"]
    assert (INST["Doc_Decree_70_2023_ND_CP"], VLR.replaces, old) in graph
    interval = graph.value(old, VLT.hasValidityInterval)
    assert str(graph.value(interval, VLT.validTo)) == "2023-09-18"


def test_retrieval_picks_the_amending_khoan():
    payloads = list(amending_chunks().values())
    parts = amending_parts(payloads, "70-2023-nd-cp", "1", "1")
    assert [part["chunk_id"] for part in parts] == ["70-2023-nd-cp:d1:p1"]
    # No khoan in the graph (a Phap dien citation): the whole amending Dieu.
    assert len(amending_parts(payloads, "70-2023-nd-cp", "1", None)) == 3
    assert change_text(["sua_doi", "bo_sung"], "khoản 2") == "sửa đổi, bổ sung khoản 2"


def test_replaced_documents():
    text = "Nghị định này thay thế Nghị định số 05/2015/NĐ-CP và Nghị định số 148/2018/NĐ-CP."
    found = replaced_documents("Hiệu lực thi hành", text, "145-2020-nd-cp")
    assert [ref.document_id for ref in found] == ["05-2015-nd-cp", "148-2018-nd-cp"]
    text = "Thông tư số 10/2020/TT-BLĐTBXH hết hiệu lực kể từ ngày Thông tư này có hiệu lực."
    assert replaced_documents("Điều khoản thi hành", text) == [DocumentRef("Thông tư", "10/2020/TT-BLĐTBXH")]
    # "thay thế" outside an effect Dieu is ordinary wording.
    assert replaced_documents("Thay thế người lao động", "Nghị định số 05/2015/NĐ-CP thay thế") == []


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
