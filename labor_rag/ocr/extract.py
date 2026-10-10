"""File -> page texts. Entry point for user uploads.

PDF pages with a text layer are read by PyMuPDF; scanned pages are rendered
at OCR_DPI and read by VietOCR. Images (photos, scans, screenshots,
multi-page TIFF) always go through OCR.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pymupdf
from PIL import Image, ImageOps, ImageSequence

from labor_rag.ocr import settings
from labor_rag.ocr.classifier import PageType, classify_document
from labor_rag.ocr.cleaner import clean_and_merge
from labor_rag.ocr.engine import ocr_image
from labor_rag.ocr.pdf_text import extract_page_text
from labor_rag.ocr.quality import quality_report

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
# Images narrower than this are upscaled to roughly A4 at 300 DPI, the scale
# the line segmentation is tuned for.
_MIN_IMAGE_WIDTH = 1600
_TARGET_IMAGE_WIDTH = 2480

# progress(message, percent 0-100). Raise inside it to cancel the job.
ProgressFn = Callable[[str, float], None]


@dataclass
class PageText:
    page_number: int  # 0-based
    text: str
    method: str  # "text" | "ocr" | "empty" | "skipped" (scan with OCR off)
    confidence: float | None = None  # VietOCR confidence, OCR pages only


@dataclass
class ExtractionResult:
    source_name: str
    pages: list[PageText]
    warnings: list[str] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def scanned_pages(self) -> list[int]:
        return [p.page_number for p in self.pages if p.method == "ocr"]

    @property
    def method(self) -> str:
        """text / ocr / mixed / none."""
        used = {p.method for p in self.pages} & {"text", "ocr"}
        if len(used) == 2:
            return "mixed"
        return used.pop() if used else "none"

    @property
    def raw_text(self) -> str:
        return "\n".join(p.text for p in self.pages if p.text)

    @property
    def ocr_confidence(self) -> float | None:
        values = [p.confidence for p in self.pages if p.confidence is not None]
        return sum(values) / len(values) if values else None

    def clean_text(self) -> str:
        """Pages merged, with headers/footers, page numbers and broken lines fixed."""
        return clean_and_merge([p.text for p in self.pages if p.text])

    def ocr_quality(self) -> dict | None:
        """Heuristic quality report over the OCR'd pages, None if nothing was OCR'd."""
        text = "\n".join(p.text for p in self.pages if p.method == "ocr")
        return quality_report(text) if text else None


def render_page(page: pymupdf.Page, dpi: int | None = None) -> Image.Image:
    pixmap = page.get_pixmap(dpi=dpi or settings.OCR_DPI)
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def _prepare_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")  # phone photos carry rotation in EXIF
    if image.width < _MIN_IMAGE_WIDTH:
        scale = _TARGET_IMAGE_WIDTH / image.width
        image = image.resize((_TARGET_IMAGE_WIDTH, round(image.height * scale)), Image.LANCZOS)
    return image


def _report(progress: ProgressFn | None, message: str, percent: float) -> None:
    logger.info("%s (%.0f%%)", message, percent)
    if progress:
        progress(message, percent)


def _extract_pdf(doc: pymupdf.Document, name: str, use_ocr: bool, progress: ProgressFn | None) -> ExtractionResult:
    if doc.needs_pass:
        raise ValueError(f"{name}: PDF is password-protected")
    classes = classify_document(doc)
    n_scanned = sum(1 for c in classes if c.page_type is PageType.SCANNED)
    result = ExtractionResult(source_name=name, pages=[])

    done = 0
    for c in classes:
        page = doc[c.page_number]
        if c.page_type is PageType.TEXT:
            result.pages.append(PageText(c.page_number, extract_page_text(page), "text"))
        elif c.page_type is PageType.EMPTY:
            result.pages.append(PageText(c.page_number, "", "empty"))
        elif not use_ocr:
            result.pages.append(PageText(c.page_number, "", "skipped"))
        else:
            _report(progress, f"OCR trang {c.page_number + 1}/{len(classes)}", 100 * done / n_scanned)
            ocr = ocr_image(render_page(page))
            result.pages.append(PageText(c.page_number, ocr.text, "ocr", ocr.confidence))
            done += 1

    if n_scanned and not use_ocr:
        result.warnings.append(f"Skipped {n_scanned} scanned page(s): OCR is off")
    if n_scanned and use_ocr:
        _report(progress, "OCR xong", 100)
    return result


def _extract_image(image: Image.Image, name: str, progress: ProgressFn | None) -> ExtractionResult:
    frames = [frame.copy() for frame in ImageSequence.Iterator(image)]  # multi-page TIFF
    result = ExtractionResult(source_name=name, pages=[])
    for i, frame in enumerate(frames):
        _report(progress, f"OCR ảnh {i + 1}/{len(frames)}", 100 * i / len(frames))
        ocr = ocr_image(_prepare_image(frame))
        result.pages.append(PageText(i, ocr.text, "ocr", ocr.confidence))
    _report(progress, "OCR xong", 100)
    return result


def extract_text(
    source: str | Path | bytes,
    *,
    filename: str | None = None,
    use_ocr: bool = True,
    progress: ProgressFn | None = None,
) -> ExtractionResult:
    """Extract the text of a PDF or image, page by page.

    Args:
        source: a file path, or the raw bytes of an upload.
        filename: display name for bytes input (the type is sniffed from the content).
        use_ocr: when False, scanned PDF pages are skipped instead of OCR'd.
        progress: called as progress(message, percent) before each OCR'd page.

    Raises:
        OCRUnavailableError: a page needs OCR but VietOCR cannot be loaded.
        ValueError: unsupported or password-protected file.
    """
    if isinstance(source, bytes):
        name = filename or "upload"
        if source.startswith(b"%PDF"):
            with pymupdf.open(stream=source, filetype="pdf") as doc:
                return _extract_pdf(doc, name, use_ocr, progress)
        try:
            image = Image.open(io.BytesIO(source))
        except Exception as e:
            raise ValueError(f"{name}: neither a PDF nor a readable image") from e
        return _extract_image(image, name, progress)

    path = Path(source)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        with pymupdf.open(path) as doc:
            return _extract_pdf(doc, path.name, use_ocr, progress)
    if suffix in IMAGE_SUFFIXES:
        with Image.open(path) as image:
            return _extract_image(image, path.name, progress)
    raise ValueError(f"{path.name}: unsupported file type {suffix!r} (PDF or {sorted(IMAGE_SUFFIXES)})")
