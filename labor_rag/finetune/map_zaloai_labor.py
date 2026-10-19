"""Map ZaloAI2021_LTR articles to the Lao dong Bo Phap Dien projection.

The mapping is intentionally deterministic:
    ZaloAI law_id + article_id
        -> (document_id, article_key)
        -> chunk_id(s) and mapc from chunks.jsonl

Only questions with at least one relevant article in the current Lao dong
dataset are exported. Unmatched candidates are counted in the report but are
never assigned a guessed legal identifier.

Usage:
    python -m labor_rag.finetune.map_zaloai_labor
    python -m labor_rag.finetune.map_zaloai_labor --report-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from labor_rag.config import LAO_DONG_DIR, finetune_raw_dir, finetune_source_dir
from labor_rag.ingest.chunk_schema import article_key, citation, make_document_id

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DEFAULT_INPUT = finetune_raw_dir("zalo") / "train_data_model.json"
DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_OUTPUT = finetune_source_dir("zalo") / "zaloai_ltr_lao_dong.json"
DEFAULT_REPORT = finetune_source_dir("zalo") / "zaloai_ltr_lao_dong_mapping_report.json"


def load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"Expected an object at {path}:{line_number}")
                yield value


def normalize_law_id(value: Any) -> str:
    """Normalize a ZaloAI law_id without changing its legal components."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", "", value.strip()).replace("Ð", "Đ")


def build_article_index(chunks_path: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], set[str]]:
    """Index all Lao dong chunks, grouping split parts under one article."""
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    documents: set[str] = set()
    for chunk in load_jsonl(chunks_path):
        document_id = str(chunk.get("document_id") or "").strip()
        meta_dieu = chunk.get("meta_dieu")
        if not document_id or meta_dieu is None:
            continue
        key = (document_id, article_key(str(meta_dieu)))
        documents.add(document_id)
        entry = grouped.setdefault(
            key,
            {
                "document_id": document_id,
                "meta_dieu": str(meta_dieu),
                "mapc": chunk.get("mapc"),
                "chunk_ids": [],
                "chunks": [],
                "representative": chunk,
            },
        )
        chunk_id = chunk.get("chunk_id")
        if chunk_id and chunk_id not in entry["chunk_ids"]:
            entry["chunk_ids"].append(chunk_id)
        entry["chunks"].append(chunk)
        if chunk.get("mapc") and not entry["mapc"]:
            entry["mapc"] = chunk["mapc"]
    for entry in grouped.values():
        entry["chunk_ids"].sort()
    return grouped, documents


def map_article(article: Any, index: dict[tuple[str, str], dict[str, Any]], documents: set[str]) -> dict[str, Any]:
    """Return an article with mapping metadata and an explicit status."""
    if not isinstance(article, dict):
        return {"mapping_status": "invalid_article"}

    law_id = normalize_law_id(article.get("law_id"))
    article_id = str(article.get("article_id") or "").strip()
    mapped = dict(article)
    mapped["mapping_status"] = "unmapped"
    if not law_id or not article_id:
        mapped["mapping_status"] = "invalid_identifier"
        return mapped

    document_id = make_document_id(law_id)
    mapped["document_id"] = document_id
    mapped["normalized_article_id"] = article_key(article_id)[1:]
    key = (document_id, article_key(article_id))
    if document_id not in documents:
        mapped["mapping_status"] = "missing_document"
        return mapped
    entry = index.get(key)
    if entry is None:
        mapped["mapping_status"] = "missing_article"
        return mapped

    representative = entry["representative"]
    mapped.update(
        {
            "mapping_status": "mapped",
            "chunk_id": entry["chunk_ids"][0],
            "chunk_ids": entry["chunk_ids"],
            "mapc": entry["mapc"],
            "citation": citation(representative),
        }
    )
    return mapped


def map_dataset(
    input_path: Path = DEFAULT_INPUT,
    chunks_path: Path = DEFAULT_CHUNKS,
    output_path: Path = DEFAULT_OUTPUT,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    index, documents = build_article_index(chunks_path)
    output_records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    list_status_counts: dict[str, Counter[str]] = {
        "relevant_articles": Counter(),
        "non_relevant_articles": Counter(),
    }
    input_questions = 0
    questions_with_labor_relevant = 0
    total_relevant = 0
    total_non_relevant = 0

    with input_path.open("r", encoding="utf-8") as handle:
        source = json.load(handle)
    if not isinstance(source, list):
        raise ValueError(f"Expected a JSON array in {input_path}")

    for record in source:
        input_questions += 1
        relevant = [
            map_article(article, index, documents)
            for article in record.get("relevant_articles", [])
        ]
        non_relevant = [
            map_article(article, index, documents)
            for article in record.get("non_relevant_articles", [])
        ]
        for article in relevant:
            status = article["mapping_status"]
            status_counts[status] += 1
            list_status_counts["relevant_articles"][status] += 1
        for article in non_relevant:
            status = article["mapping_status"]
            status_counts[status] += 1
            list_status_counts["non_relevant_articles"][status] += 1

        mapped_relevant = [a for a in relevant if a["mapping_status"] == "mapped"]
        if not mapped_relevant:
            continue
        questions_with_labor_relevant += 1
        total_relevant += len(mapped_relevant)
        mapped_non_relevant = [a for a in non_relevant if a["mapping_status"] == "mapped"]
        total_non_relevant += len(mapped_non_relevant)
        output_records.append(
            {
                "question_id": record.get("question_id"),
                "question": record.get("question", ""),
                "relevant_articles": mapped_relevant,
                "non_relevant_articles": mapped_non_relevant,
                "source_relevant_article_count": len(relevant),
                "source_non_relevant_article_count": len(non_relevant),
            }
        )

    report = {
        "source": str(input_path),
        "chunks": str(chunks_path),
        "scope": "Lao dong topic in the current lao_dong_v5 projection",
        "input_questions": input_questions,
        "output_questions": questions_with_labor_relevant,
        "input_relevant_articles": list_status_counts["relevant_articles"].total(),
        "input_non_relevant_articles": list_status_counts["non_relevant_articles"].total(),
        "mapped_relevant_articles": total_relevant,
        "mapped_non_relevant_articles": total_non_relevant,
        "mapped_relevant_question_rate": (
            questions_with_labor_relevant / input_questions if input_questions else 0.0
        ),
        "status_counts": dict(status_counts),
        "relevant_status_counts": dict(list_status_counts["relevant_articles"]),
        "non_relevant_status_counts": dict(list_status_counts["non_relevant_articles"]),
        "labor_documents": len(documents),
        "labor_articles": len(index),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--report-only", action="store_true", help="Print the report after mapping.")
    args = parser.parse_args()

    report = map_dataset(args.input, args.chunks, args.output, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report_only:
        args.output.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
