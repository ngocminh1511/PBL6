"""Tests for deterministic ZaloAI -> Lao dong article mapping."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labor_rag.finetune.map_zaloai_labor import (
    build_article_index,
    map_article,
    map_dataset,
    normalize_law_id,
)


def chunk(document_id: str, article: str, mapc: str, chunk_id: str | None = None) -> dict:
    return {
        "document_id": document_id,
        "meta_dieu": article,
        "mapc": mapc,
        "chunk_id": chunk_id or f"{document_id}:d{article}",
        "meta_de_muc": f"Luật số {document_id}",
    }


def test_normalize_law_id():
    assert normalize_law_id(" 38 / 2013 / qh13 ") == "38/2013/qh13"
    assert normalize_law_id("145/2020/NÐ-CP") == "145/2020/NĐ-CP"
    assert normalize_law_id(None) == ""


def test_mapping_groups_split_article_parts():
    index, documents = build_article_index_from_records(
        [
            chunk("38-2013-qh13", "50", "20.4.LQ.50"),
            chunk("38-2013-qh13", "50", "20.4.LQ.50", "38-2013-qh13:d50:p2"),
        ]
    )
    mapped = map_article({"law_id": "38/2013/qh13", "article_id": "50"}, index, documents)
    assert mapped["mapping_status"] == "mapped"
    assert mapped["mapc"] == "20.4.LQ.50"
    assert mapped["chunk_ids"] == ["38-2013-qh13:d50", "38-2013-qh13:d50:p2"]


def test_mapping_distinguishes_missing_document_and_article():
    index, documents = build_article_index_from_records(
        [chunk("38-2013-qh13", "50", "20.4.LQ.50")]
    )
    assert map_article({"law_id": "99/2020/QH14", "article_id": "1"}, index, documents)["mapping_status"] == "missing_document"
    assert map_article({"law_id": "38/2013/QH13", "article_id": "51"}, index, documents)["mapping_status"] == "missing_article"


def test_map_dataset_filters_to_questions_with_labor_relevant():
    with tempfile.TemporaryDirectory() as directory:
        tmp_path = Path(directory)
        chunks_path = tmp_path / "chunks.jsonl"
        chunks_path.write_text(
            "\n".join(
                json.dumps(item, ensure_ascii=False)
                for item in [chunk("38-2013-qh13", "50", "20.4.LQ.50")]
            )
            + "\n",
            encoding="utf-8",
        )
        input_path = tmp_path / "zalo.json"
        input_path.write_text(
            json.dumps(
                [
                    {
                        "question_id": "q1",
                        "question": "trợ cấp thất nghiệp",
                        "relevant_articles": [{"law_id": "38/2013/qh13", "article_id": "50"}],
                        "non_relevant_articles": [{"law_id": "99/2020/qh14", "article_id": "1"}],
                    },
                    {
                        "question_id": "q2",
                        "question": "ngoài lao động",
                        "relevant_articles": [{"law_id": "99/2020/qh14", "article_id": "1"}],
                        "non_relevant_articles": [],
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output_path = tmp_path / "mapped.json"
        report_path = tmp_path / "report.json"
        report = map_dataset(input_path, chunks_path, output_path, report_path)
        result = json.loads(output_path.read_text(encoding="utf-8"))
        assert [item["question_id"] for item in result] == ["q1"]
        assert result[0]["relevant_articles"][0]["mapc"] == "20.4.LQ.50"
        assert result[0]["non_relevant_articles"] == []
        assert report["input_questions"] == 2
        assert report["output_questions"] == 1
        assert report["relevant_status_counts"]["mapped"] == 1


def build_article_index_from_records(records: list[dict]):
    """Build the same index as the file loader without filesystem fixtures."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        path = Path(handle.name)
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    try:
        return build_article_index(path)
    finally:
        path.unlink()


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
