"""Tests for ViLegalExpert -> Lao dong article mapping."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labor_rag.finetune.map_vilegal_labor import (
    load_chunks,
    map_context,
    map_dataset,
    normalize_article,
)


def chunk(document_id: str, article: str, mapc: str, chunk_id: str | None = None) -> dict:
    return {
        "document_id": document_id,
        "meta_dieu": article,
        "mapc": mapc,
        "chunk_id": chunk_id or f"{document_id}:d{article}",
        "meta_de_muc": "Bộ luật Lao động 2019",
    }


def make_index(records: list[dict]) -> tuple[dict, set[str]]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        path = Path(handle.name)
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    try:
        return load_chunks(path)
    finally:
        path.unlink()


def test_normalize_article():
    assert normalize_article("35đ") == "35d"
    assert normalize_article(" 48 ") == "48"


def test_map_context_exact_and_preserves_clause():
    index, documents = make_index([chunk("45-2019-qh14", "48", "20.2.LQ.48")])
    context = {"điều": "48", "khoản": "1", "Số hiệu:": "45/2019/QH14"}
    mapped, status = map_context({"answer": ""}, context, index, documents)
    assert status == "mapped"
    assert mapped["mapc"] == "20.2.LQ.48"
    assert mapped["article_id"] == "48"
    assert mapped["khoản"] == "1"


def test_map_context_recovers_unique_answer_citation():
    index, documents = make_index([chunk("84-2015-qh13", "46", "20.5.LQ.46")])
    record = {"answer": "Căn cứ khoản 2 Điều 46 Luật An toàn, vệ sinh lao động."}
    mapped, status = map_context(
        record,
        {"Số hiệu:": "84/2015/QH13"},
        index,
        documents,
    )
    assert status == "mapped"
    assert mapped["article_id"] == "46"
    assert mapped["article_recovery"] == "recovered_from_unique_answer_citation"


def test_map_context_rejects_ambiguous_answer_citations():
    index, documents = make_index(
        [
            chunk("45-2019-qh14", "36", "20.2.LQ.36"),
            chunk("45-2019-qh14", "41", "20.2.LQ.41"),
        ]
    )
    mapped, status = map_context(
        {"answer": "Theo Điều 36 và Điều 41 Bộ luật Lao động."},
        {"Số hiệu:": "45/2019/QH14"},
        index,
        documents,
    )
    assert status == "ambiguous_answer_citation"
    assert mapped["mapping_status"] == "ambiguous_answer_citation"


def test_map_dataset_writes_mapped_and_review_outputs():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        chunks_path = root / "chunks.jsonl"
        chunks_path.write_text(
            "\n".join(
                json.dumps(item, ensure_ascii=False)
                for item in [
                    chunk("45-2019-qh14", "36", "20.2.LQ.36"),
                    chunk("45-2019-qh14", "41", "20.2.LQ.41"),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        input_path = root / "train.json"
        input_path.write_text(
            json.dumps(
                {
                    "mapped": {
                        "question": "Khi nào được chấm dứt hợp đồng?",
                        "answer": "Theo Điều 36.",
                        "link": "x",
                        "contexts": {
                            "0": {
                                "điều": "36",
                                "Số hiệu:": "45/2019/QH14",
                            }
                        },
                    },
                    "review": {
                        "question": "Thiếu điều",
                        "answer": "Theo Điều 36 và Điều 41.",
                        "contexts": {"0": {"Số hiệu:": "45/2019/QH14"}},
                    },
                    "outside": {
                        "question": "Ngoài phạm vi",
                        "answer": "",
                        "contexts": {"0": {"điều": "1", "Số hiệu:": "99/2020/QH14"}},
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = root / "mapped.json"
        review = root / "review.json"
        report = root / "report.json"
        result = map_dataset(input_path, chunks_path, output, review, report)
        mapped = json.loads(output.read_text(encoding="utf-8"))
        reviewed = json.loads(review.read_text(encoding="utf-8"))
        assert result["mapped_records"] == 1
        assert result["status_counts"]["ambiguous_answer_citation"] == 1
        assert [item["record_id"] for item in mapped] == ["mapped"]
        assert [item["record_id"] for item in reviewed] == ["review"]


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
