"""Map ViLegalExpert single-context records to the Lao dong projection.

Mapping is exact on source document number and article number. Records whose
source document is outside the current Lao dong projection are counted but
not emitted in the mapped dataset. Missing article numbers may be recovered
from a unique citation in the answer, but ambiguous citations remain in the
review output.

Usage:
    python -m labor_rag.finetune.map_vilegal_labor
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from labor_rag.config import LAO_DONG_DIR, finetune_raw_dir, finetune_source_dir
from labor_rag.ingest.chunk_schema import article_key, citation, make_document_id

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DEFAULT_INPUT = finetune_raw_dir("vilegal") / "train_data.json"
DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_OUTPUT = finetune_source_dir("vilegal") / "vilegal_labor_mapped.json"
DEFAULT_REVIEW = finetune_source_dir("vilegal") / "vilegal_labor_review.json"
DEFAULT_REPORT = finetune_source_dir("vilegal") / "vilegal_labor_mapping_report.json"

ARTICLE_CITATION_RE = re.compile(r"\bđiều\s+([0-9]+[a-zđ]?)\b", re.IGNORECASE)


def fold(value: Any) -> str:
    text = str(value or "").replace("Ð", "Đ").replace("ð", "đ")
    text = text.replace("Đ", "D").replace("đ", "d")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def normalize_article(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(value).strip())


def source_number(context: dict[str, Any]) -> str:
    for key, value in context.items():
        if fold(key).startswith("so hieu") and isinstance(value, str):
            return value.strip()
    return ""


def source_article(context: dict[str, Any]) -> str:
    for key, value in context.items():
        if fold(key) == "dieu" and value is not None:
            return str(value).strip()
    return ""


def load_chunks(path: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], set[str]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    documents: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            document_id = str(chunk.get("document_id") or "").strip()
            article = str(chunk.get("meta_dieu") or "").strip()
            if not document_id or not article:
                continue
            documents.add(document_id)
            key = (document_id, article_key(article))
            entry = grouped.setdefault(
                key,
                {
                    "document_id": document_id,
                    "meta_dieu": article,
                    "mapc": chunk.get("mapc"),
                    "chunk_ids": [],
                    "representative": chunk,
                },
            )
            if chunk.get("mapc") and not entry["mapc"]:
                entry["mapc"] = chunk["mapc"]
            if chunk.get("chunk_id") not in entry["chunk_ids"]:
                entry["chunk_ids"].append(chunk["chunk_id"])
    for entry in grouped.values():
        entry["chunk_ids"].sort()
    return grouped, documents


def unique_answer_article(answer: Any, document_id: str, index: dict[tuple[str, str], dict[str, Any]]) -> tuple[str | None, str]:
    candidates = {
        normalize_article(match)
        for match in ARTICLE_CITATION_RE.findall(str(answer or ""))
        if (document_id, article_key(match)) in index
    }
    if len(candidates) == 1:
        return next(iter(candidates)), "recovered_from_unique_answer_citation"
    if len(candidates) > 1:
        return None, "ambiguous_answer_citation"
    return None, "missing_article_id"


def map_context(
    record: dict[str, Any],
    context: dict[str, Any],
    index: dict[tuple[str, str], dict[str, Any]],
    documents: set[str],
) -> tuple[dict[str, Any], str]:
    mapped = dict(context)
    raw_number = source_number(context)
    raw_article = source_article(context)
    document_id = make_document_id(raw_number) if raw_number else ""
    mapped["document_id"] = document_id or None
    mapped["source_article_id"] = raw_article or None

    if not document_id:
        mapped["mapping_status"] = "invalid_identifier"
        return mapped, "invalid_identifier"
    if document_id not in documents:
        mapped["mapping_status"] = "missing_document"
        return mapped, "missing_document"

    recovery_status = ""
    article = normalize_article(raw_article)
    if not article:
        article, recovery_status = unique_answer_article(record.get("answer"), document_id, index)
        if not article:
            mapped["mapping_status"] = recovery_status
            return mapped, recovery_status

    key = (document_id, article_key(article))
    entry = index.get(key)
    if entry is None:
        mapped["mapping_status"] = "missing_article"
        return mapped, "missing_article"

    representative = entry["representative"]
    mapped.update(
        {
            "mapping_status": "mapped",
            "article_id": entry["meta_dieu"],
            "mapc": entry["mapc"],
            "chunk_id": entry["chunk_ids"][0],
            "chunk_ids": entry["chunk_ids"],
            "citation": citation(representative),
        }
    )
    if recovery_status:
        mapped["article_recovery"] = recovery_status
    return mapped, "mapped"


def map_dataset(
    input_path: Path = DEFAULT_INPUT,
    chunks_path: Path = DEFAULT_CHUNKS,
    output_path: Path = DEFAULT_OUTPUT,
    review_path: Path = DEFAULT_REVIEW,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    index, documents = load_chunks(chunks_path)
    source = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError(f"Expected an object keyed by record id in {input_path}")

    mapped_records: list[dict[str, Any]] = []
    review_records: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    document_stats: dict[str, Counter[str]] = defaultdict(Counter)
    mapped_pairs: Counter[tuple[str, str]] = Counter()

    for record_id, record in source.items():
        if not isinstance(record, dict):
            statuses["invalid_record"] += 1
            continue
        contexts = record.get("contexts")
        context = next(iter(contexts.values()), {}) if isinstance(contexts, dict) else {}
        if not isinstance(context, dict):
            context = {}
        mapped_context, status = map_context(record, context, index, documents)
        statuses[status] += 1
        document_id = mapped_context.get("document_id")
        if document_id:
            document_stats[document_id][status] += 1

        result = {
            "record_id": record_id,
            "question": record.get("question", ""),
            "answer": record.get("answer", ""),
            "link": record.get("link"),
            "most_common_doc_type": record.get("most_common_doc_type"),
            "context": mapped_context,
        }
        if status == "mapped":
            mapped_records.append(result)
            mapped_pairs[(document_id, mapped_context["article_id"])] += 1
        elif status != "missing_document":
            review_records.append(result)

    report = {
        "source": str(input_path),
        "chunks": str(chunks_path),
        "scope": "Lao dong topic in the current lao_dong_v5 projection",
        "input_records": len(source),
        "mapped_records": len(mapped_records),
        "review_records": len(review_records),
        "labor_documents": len(documents),
        "labor_articles": len(index),
        "status_counts": dict(statuses),
        "mapped_document_counts": dict(
            sorted(
                (
                    document_id,
                    sum(stats.values()),
                )
                for document_id, stats in document_stats.items()
                if stats["mapped"]
            )
        ),
        "mapped_article_pairs": [
            {"document_id": doc, "article_id": article, "records": count}
            for (doc, article), count in sorted(mapped_pairs.items())
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(mapped_records, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path.write_text(json.dumps(review_records, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    print(json.dumps(map_dataset(args.input, args.chunks, args.output, args.review, args.report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
