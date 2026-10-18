"""Unit tests for article-level amendments: parsing the pGhiChu citation
(build_abox) and projecting it to amended_by / version_date
(ontology_to_jsonl). No data files are read.

Run from the repository root:
  python tests/test_amendments.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.ingest.build_abox import INST, VLD, AboxBuilder, amendment_actions
from labor_rag.ingest.ontology_to_jsonl import amendments, version_date

CITATION = (
    "( Điều 3 Nghị định số 152/2020/NĐ-CP, có hiệu lực thi hành kể từ ngày 15/02/2021, "
    "có nội dung được sửa đổi, có nội dung được bổ sung bởi Điều 1 Nghị định số 70/2023/NĐ-CP "
    "có hiệu lực thi hành kể từ ngày 18/09/2023)"
)


def test_amendment_actions():
    assert amendment_actions(", có nội dung được sửa đổi, có nội dung bị bãi bỏ bởi ") == ["sua_doi", "bai_bo"]
    assert amendment_actions(", ") == []


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
