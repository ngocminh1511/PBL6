"""Document OCR for user uploads: PDF (text layer or scan) and photos of
Vietnamese legal documents -> clean text -> Phần/Chương/Mục/Điều/Khoản/Điểm
structure -> flat records.

App-facing API:

    from labor_rag.ocr import extract_text, process_document

    result = extract_text(upload_bytes, filename="hop_dong.jpg")
    result.clean_text()       # merged, cleaned text
    result.ocr_confidence     # mean VietOCR confidence, None if nothing was OCR'd

    processed = process_document("nghi_dinh.pdf")
    processed.document        # LegalDocument tree
    processed.records         # FlatRecord list (one per Điểm/Khoản/Điều)

The VietOCR model loads lazily on the first OCR'd page; call
labor_rag.ocr.engine.get_predictor() at app startup to load it eagerly.
"""
from labor_rag.ocr.engine import OCRUnavailableError
from labor_rag.ocr.extract import ExtractionResult, PageText, extract_text
from labor_rag.ocr.pipeline import ProcessedDocument, process_document
from labor_rag.ocr.quality import quality_report

__all__ = [
    "ExtractionResult",
    "OCRUnavailableError",
    "PageText",
    "ProcessedDocument",
    "extract_text",
    "process_document",
    "quality_report",
]
