"""Unit tests for labor_rag.ingest.references (cross-references in the text
of a Dieu, down to the khoan). Lines are taken from the Phap dien data.

Run from the repository root:
  python tests/test_references.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.ingest.references import DocumentIndex, read_article, read_line

BLLD = "45-2019-qh14"
ND145 = "145-2020-nd-cp"


def index() -> DocumentIndex:
    names = DocumentIndex()
    names.add("Bộ luật", "45/2019/QH14", "Bộ Luật lao động ngày 20/11/2019 của Quốc hội", "2021-01-01")
    names.add("Luật", "38/2013/QH13", "Việc làm ngày 16/11/2013 của Quốc hội", "2015-01-01")
    names.articles = {(BLLD, n) for n in ("14", "16", "35", "36", "42", "143", "145", "146", "147", "162")}
    names.articles |= {(ND145, n) for n in ("5", "7", "14", "24", "42")}
    return names


def targets(refs) -> list[tuple]:
    return [(t.document_id, t.dieu, t.khoan, t.diem) for ref in refs for t in ref.targets]


def test_list_lead_names_the_document_and_marks_implements():
    paragraphs = [
        "Thông tư này quy định chi tiết và hướng dẫn thi hành một số điều, khoản sau đây của Bộ luật Lao động "
        "về lao động chưa thành niên:",
        "1. Sử dụng người chưa đủ 15 tuổi làm việc theo quy định tại khoản 4 Điều 145.",
        "4. Danh mục công việc, nơi làm việc gây tổn hại theo quy định khoản 3 Điều 147.",
    ]
    found = read_article(paragraphs, "09-2020-tt-bldtbxh", "1", index())
    assert [(khoan, targets([ref])) for khoan, ref in found] == [
        ("1", [(BLLD, "145", "4", None)]),
        ("4", [(BLLD, "147", "3", None)]),
    ]
    assert all(ref.implements for _, ref in found)


def test_document_after_the_reference():
    names = index()
    assert targets(read_line("theo Điều 24 Nghị định này", ND145, "25", None, names)) == [(ND145, "24", None, None)]
    assert targets(read_line("tại khoản 6 Điều 42 Bộ luật Lao động.", "x", "7", None, names)) == [(BLLD, "42", "6", None)]
    assert targets(read_line("tại Điều 45 Luật Việc làm.", ND145, "1", None, names)) == [("38-2013-qh13", "45", None, None)]
    assert targets(read_line("tại Khoản 2 Điều 11 Nghị định số 61/2015/NĐ-CP", "x", "1", None, names)) == [
        ("61-2015-nd-cp", "11", "2", None)
    ]
    # The number stops at the last capital: "QH13đang" (missing space in the source).
    assert targets(read_line("Khoản 4 Điều 2 Luật bảo hiểm xã hội số 58/2014/QH13đang", "x", "1", None, names)) == [
        ("58-2014-qh13", "2", "4", None)
    ]
    # A law not in the data, without a number: no document_id, the title is kept.
    (ref,) = read_line("tại Điều 90 và Điều 91 của Luật bảo hiểm xã hội;", "x", "1", None, names)
    assert targets([ref]) == [(None, "90", None, None), (None, "91", None, None)]
    assert ref.document_name.lower().startswith("luật bảo hiểm xã hội")


def test_lists_of_diem_khoan_dieu():
    names = index()
    line = "theo quy định tại các điểm a, b, c khoản 2 Điều 185 của Bộ luật Lao động"
    assert targets(read_line(line, ND145, "99", None, names)) == [(BLLD, "185", "2", "a, b, c")]
    line = "Điểm a và Điểm b Khoản 1 Điều này;"
    assert targets(read_line(line, ND145, "3", "4", names)) == [(ND145, "3", "1", "a, b")]
    line = "quy định tại các khoản 1, 2, 3 và 4 Điều 1 Nghị định này"
    assert targets(read_line(line, ND145, "14", None, names)) == [(ND145, "1", k, None) for k in "1234"]
    line = "các điều 17, 18 và 19 của Luật này"
    assert [t[1] for t in targets(read_line(line, "x", "26", None, names))] == ["17", "18", "19"]


def test_document_named_at_the_end_of_a_chain():
    names = index()
    line = "quy định tại điểm d khoản 1 Điều 35 và điểm d khoản 2 Điều 36 của Bộ luật Lao động như sau:"
    assert targets(read_line(line, ND145, "7", None, names)) == [(BLLD, "35", "1", "d"), (BLLD, "36", "2", "d")]
    line = "theo Điều 14 và khoản 1 Điều 162; nghĩa vụ theo Điều 16 của Bộ luật Lao động"
    assert {t[0] for t in targets(read_line(line, ND145, "89", None, names))} == {BLLD}
    # The line names its own document: unnamed references stay there.
    line = "theo Điều 24 Nghị định này và Điều 42"
    assert targets(read_line(line, ND145, "25", None, names)) == [(ND145, "24", None, None), (ND145, "42", None, None)]


def test_bare_khoan_is_this_dieu_unless_a_chain_names_one():
    names = index()
    assert targets(read_line("quy định tại khoản 2 thì", ND145, "7", "3", names)) == [(ND145, "7", "2", None)]
    line = "theo quy định tại Điểm b Khoản 1 và Điểm b Khoản 2 Điều 8 của Thông tư này"
    assert sorted(targets(read_line(line, "x", "17", "1", names))) == [("x", "8", "1", "b"), ("x", "8", "2", "b")]
    # "tại khoản 1, khoản 2 Điều 123" is one reference, not a khoan of this Dieu too.
    line = "quy định tại khoản 1, khoản 2 Điều 123 của Bộ luật Lao động"
    assert targets(read_line(line, ND145, "70", "2", names)) == [(BLLD, "123", "1", None), (BLLD, "123", "2", None)]


def test_abox_clauses_and_khoan_level_edges():
    from labor_rag.ingest.build_abox import INST, VLD, VLR, AboxBuilder

    builder = AboxBuilder()
    blld = builder.document("Bộ luật", "45/2019/QH14", None, "2021-01-01")
    builder.index.add("Bộ luật", "45/2019/QH14", "Bộ Luật lao động ngày 20/11/2019", "2021-01-01")
    circular = builder.document("Thông tư", "09/2020/TT-BLĐTBXH", None, "2021-03-15")
    source = builder.source_article(circular, "1")
    paragraphs = [
        "Thông tư này quy định chi tiết và hướng dẫn thi hành một số điều, khoản sau đây của Bộ luật Lao động:",
        "1. Sử dụng người chưa đủ 15 tuổi làm việc theo quy định tại khoản 4 Điều 145.",
        "2. Danh mục theo quy định tại điểm a, b khoản 3 Điều 143 và khoản 1 Điều này.",
    ]
    stats = builder.add_clauses_and_references(source, circular, "1", paragraphs)
    graph = builder.graph
    k1 = INST["SourceClause_Circular_09_2020_TT_BLDTBXH_D1_K1"]
    assert str(graph.value(k1, VLD.contentText)).startswith("1. Sử dụng người")
    assert (k1, VLR.implementsComponent, INST["SourceClause_Law_45_2019_QH14_D145_K4"]) in graph
    k2 = INST["SourceClause_Circular_09_2020_TT_BLDTBXH_D1_K2"]
    points = set(graph.objects(k2, VLR.implementsComponent))
    assert INST["SourcePoint_Law_45_2019_QH14_D143_K3_Pa"] in points and INST["SourcePoint_Law_45_2019_QH14_D143_K3_Pb"] in points
    assert (k2, VLR.citesComponent, k1) not in graph  # "khoản 1 Điều này" is listed under the lead: implements
    assert (k2, VLR.implementsComponent, k1) in graph
    assert graph.value(INST["SourcePoint_Law_45_2019_QH14_D143_K3_Pa"], VLD.locatedInDocument) == blld
    assert stats["clauses"] == 2 and stats["references"] == 4


def test_pdf_references_resolve_against_the_graph():
    from labor_rag.ingest.build_abox import INST, VLR
    from labor_rag.ingest.pdf_abox import document_abox
    from labor_rag.ingest.pdf_to_chunks import KgIndex
    from labor_rag.ocr.structure import extract_metadata, parse_structure

    text = """BỘ LAO ĐỘNG - THƯƠNG BINH VÀ XÃ HỘI
Số: 99/2025/TT-BLĐTBXH
THÔNG TƯ
Điều 1. Danh mục công việc
1. Danh mục công việc quy định tại khoản 3 Điều 147 của Bộ luật Lao động gồm:
a) Công việc trong hầm mỏ;
2. Người sử dụng lao động thực hiện theo khoản 1 Điều này và Điều 2.
Điều 2. Hiệu lực thi hành
Thông tư này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2025.
"""
    doc = parse_structure(text)
    doc.metadata = extract_metadata(text, doc.title)
    doc.document_id = "99-2025-tt-bldtbxh"
    kg = KgIndex(
        {(BLLD, "147"): "20.2.LQ.147"},
        {BLLD: {"ten": "Bộ luật số 45/2019/QH14", "document_number": "45/2019/QH14", "short_title": "Bộ Luật lao động"}},
    )
    builder, stats = document_abox(doc, kg)
    graph = builder.graph
    k1 = INST["SourceClause_Circular_99_2025_TT_BLDTBXH_D1_K1"]
    k2 = INST["SourceClause_Circular_99_2025_TT_BLDTBXH_D1_K2"]
    assert (k1, VLR.citesComponent, INST["SourceClause_Law_45_2019_QH14_D147_K3"]) in graph
    assert (k2, VLR.citesComponent, k1) in graph
    assert (k2, VLR.citesComponent, INST["SourceArticle_Circular_99_2025_TT_BLDTBXH_D2"]) in graph
    assert stats["references"] == 3


def test_retrieval_adds_only_the_referenced_khoan():
    from labor_rag.retrieval.hybrid_retrieve import khoans_of, referenced_evidence

    assert khoans_of("1-4") == ["1", "2", "3", "4"] and khoans_of("3") == ["3"] and khoans_of(None) is None
    payloads = [
        {"chunk_id": f"{BLLD}:d147", "document_id": BLLD, "meta_dieu": "147", "ten": "Công việc cấm",
         "text": "Điều 147.\n1. ...\n3. Bộ trưởng quy định danh mục.", "meta_de_muc": "Bộ luật số 45/2019/QH14"},
    ]
    row = {"relation": "IMPLEMENTS_COMPONENT", "document_id": BLLD, "article_number": "147", "clause_number": "3",
           "point_number": None, "text": "3. Bộ trưởng quy định danh mục."}
    evidence = referenced_evidence(row, payloads)
    assert (evidence.chunk_id, evidence.meta_khoan, evidence.source) == (f"{BLLD}:d147", "3", "graph:IMPLEMENTS")
    assert evidence.text == "3. Bộ trưởng quy định danh mục."
    assert evidence.citation == "Điều 147 khoản 3 Bộ luật số 45/2019/QH14"
    # Not in force / not indexed: nothing.
    assert referenced_evidence({**row, "document_id": "x"}, payloads) is None


def test_quoted_text_is_ignored():
    line = "Sửa đổi khoản 2 Điều 5 như sau: “2. Theo quy định tại Điều 99 của Luật này.”"
    assert [t[1] for t in targets(read_line(line, "x", "1", None, index()))] == ["5"]


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
