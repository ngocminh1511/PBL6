"""JSONL export of a parsed document.

  hierarchical  one line holding the whole tree (rendering a document view)
  flat          one line per FlatRecord with its hierarchy path (indexing / RAG)
  training      instruction-style {"instruction", "input", "output"} lines
"""
from __future__ import annotations

import json
from pathlib import Path

from labor_rag.ocr.schemas import FlatRecord, LegalDocument

EXPORT_FORMATS = ("hierarchical", "flat", "training")


def _write_lines(path: Path, lines) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


def export_hierarchical(document: LegalDocument, path: Path) -> Path:
    return _write_lines(path, [document.model_dump(exclude_none=True)])


def export_flat(records: list[FlatRecord], path: Path) -> Path:
    return _write_lines(path, (r.model_dump() for r in records))


def export_training(records: list[FlatRecord], path: Path) -> Path:
    return _write_lines(path, (
        {
            "instruction": f"Trích dẫn nội dung {r.hierarchy}",
            "input": r.document_title,
            "output": r.text,
            "metadata": {"document_id": r.document_id, "level": r.level, "hierarchy": r.hierarchy},
        }
        for r in records if r.text.strip()
    ))


def export_document(
    document: LegalDocument,
    records: list[FlatRecord],
    output_dir: Path,
    formats: tuple[str, ...] = ("flat",),
) -> dict[str, Path]:
    """Write the requested formats as <document_id>_<format>.jsonl."""
    unknown = set(formats) - set(EXPORT_FORMATS)
    if unknown:
        raise ValueError(f"Unknown export format(s) {sorted(unknown)}; choose from {EXPORT_FORMATS}")
    output_dir = Path(output_dir)
    stem = document.document_id
    writers = {
        "hierarchical": lambda p: export_hierarchical(document, p),
        "flat": lambda p: export_flat(records, p),
        "training": lambda p: export_training(records, p),
    }
    return {fmt: writers[fmt](output_dir / f"{stem}_{fmt}.jsonl") for fmt in formats}
