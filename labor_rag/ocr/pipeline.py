"""Full document pipeline: PDF/image -> page texts (text layer or VietOCR) ->
clean -> Phần/Chương/Mục/Điều/Khoản/Điểm tree -> flat records -> JSONL.

Usage (from the repository root):
  python -m labor_rag.ocr --input path/to/file.pdf
  python -m labor_rag.ocr --input folder/ --format flat hierarchical
  python -m labor_rag.ocr --input photo.jpg --no-export
Output goes to data/interim/ocr/ unless --output is given.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from labor_rag.config import OCR_OUTPUT_DIR
from labor_rag.ocr.chunking import chunk_long_records, flatten_document
from labor_rag.ocr.export import EXPORT_FORMATS, export_document
from labor_rag.ocr.extract import IMAGE_SUFFIXES, ExtractionResult, ProgressFn, extract_text
from labor_rag.ocr.schemas import FlatRecord, LegalDocument
from labor_rag.ocr.structure import extract_metadata, parse_structure

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    extraction: ExtractionResult
    document: LegalDocument
    records: list[FlatRecord]
    # Heuristic OCR quality (see quality.py); None when no page was OCR'd.
    ocr_quality: dict | None = None
    outputs: dict[str, Path] = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "file": self.extraction.source_name,
            "document_id": self.document.document_id,
            "title": self.document.title,
            "total_pages": self.extraction.total_pages,
            "method": self.extraction.method,
            "scanned_pages": len(self.extraction.scanned_pages),
            "ocr_confidence": self.extraction.ocr_confidence,
            "ocr_quality_score": self.ocr_quality["heuristic_score"] if self.ocr_quality else None,
            "articles": sum(1 for _ in self.document.iter_articles()),
            "records": len(self.records),
            "warnings": self.extraction.warnings,
            "outputs": {k: str(v) for k, v in self.outputs.items()},
        }


def _document_id(name: str) -> str:
    return Path(name).stem.lower().replace(" ", "_")


def process_document(
    source: str | Path | bytes,
    *,
    filename: str | None = None,
    output_dir: Path | None = None,
    formats: tuple[str, ...] = (),
    use_ocr: bool = True,
    progress: ProgressFn | None = None,
) -> ProcessedDocument:
    """Run the whole pipeline on one PDF or image.

    JSONL files are written only when both output_dir and formats are given;
    otherwise everything stays in memory (the usual case for an app upload).
    """
    extraction = extract_text(source, filename=filename, use_ocr=use_ocr, progress=progress)
    text = extraction.clean_text()
    if not text:
        raise ValueError(f"{extraction.source_name}: no text could be extracted")

    document = parse_structure(text, document_id=_document_id(extraction.source_name))
    metadata = extract_metadata(text, document.title, extraction.source_name, extraction.total_pages)
    metadata.extraction_method = extraction.method
    metadata.scanned_pages = extraction.scanned_pages
    document.metadata = metadata

    records = chunk_long_records(flatten_document(document))
    result = ProcessedDocument(extraction, document, records, ocr_quality=extraction.ocr_quality())
    if output_dir and formats:
        result.outputs = export_document(document, records, output_dir, formats)
    return result


# ============================================================
# CLI
# ============================================================

def _collect_inputs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    suffixes = IMAGE_SUFFIXES | {".pdf"}
    return sorted(p for p in path.iterdir() if p.suffix.lower() in suffixes)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="PDF/ảnh văn bản pháp luật -> JSONL (text layer + VietOCR)")
    parser.add_argument("--input", "-i", type=Path, required=True, help="File PDF/ảnh hoặc thư mục")
    parser.add_argument("--output", "-o", type=Path, default=OCR_OUTPUT_DIR)
    parser.add_argument(
        "--format", "-f", nargs="+", default=["flat"], choices=[*EXPORT_FORMATS, "all"],
        help="Định dạng JSONL (mặc định: flat)",
    )
    parser.add_argument("--no-ocr", action="store_true", help="Bỏ qua trang scan thay vì OCR")
    parser.add_argument("--no-export", action="store_true", help="Chỉ in tóm tắt, không ghi JSONL")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if not args.input.exists():
        logger.error("Not found: %s", args.input)
        return 1
    inputs = _collect_inputs(args.input)
    if not inputs:
        logger.error("No PDF/image in %s", args.input)
        return 1

    formats = EXPORT_FORMATS if "all" in args.format else tuple(args.format)
    report = []
    for i, path in enumerate(inputs, 1):
        logger.info("[%d/%d] %s", i, len(inputs), path.name)
        start = time.time()
        try:
            result = process_document(
                path,
                output_dir=None if args.no_export else args.output,
                formats=formats,
                use_ocr=not args.no_ocr,
            )
            entry = {"status": "success", **result.summary()}
        except Exception as e:
            logger.exception("Failed: %s", path.name)
            entry = {"status": "error", "file": path.name, "error": str(e)}
        entry["elapsed_seconds"] = round(time.time() - start, 2)
        report.append(entry)
        print(json.dumps(entry, ensure_ascii=False, indent=2))

    if not args.no_export:
        args.output.mkdir(parents=True, exist_ok=True)
        report_path = args.output / "processing_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Report: %s", report_path)
    return 0 if all(r["status"] == "success" for r in report) else 1
