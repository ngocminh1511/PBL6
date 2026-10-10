"""Per-page PDF classification: text layer, scan, or empty.

A page is read from its text layer when it has enough characters; otherwise
a page covered by an image is sent to OCR. This handles hybrid PDFs (a typed
body with scanned signature pages, or a scan with a thin OCR layer).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pymupdf

from labor_rag.ocr import settings


class PageType(Enum):
    TEXT = "text"
    SCANNED = "scanned"
    EMPTY = "empty"


@dataclass
class PageClassification:
    page_number: int  # 0-based
    page_type: PageType
    text_length: int
    image_coverage: float  # 0.0 - 1.0


def _image_coverage(page: pymupdf.Page) -> float:
    """Share of the page covered by its largest image."""
    page_area = abs(page.rect)
    if page_area == 0:
        return 0.0
    coverage = 0.0
    for info in page.get_image_info():
        visible = pymupdf.Rect(info["bbox"]) & page.rect
        coverage = max(coverage, abs(visible) / page_area)
    return coverage


def classify_page(page: pymupdf.Page) -> PageClassification:
    text_length = len(page.get_text().strip())
    coverage = _image_coverage(page)

    if text_length < 10 and coverage < 0.1:
        page_type = PageType.EMPTY
    elif text_length >= settings.MIN_TEXT_CHARS:
        page_type = PageType.TEXT
    elif coverage > settings.SCAN_IMAGE_COVERAGE:
        # Little text over a large image: a scan, possibly with a thin OCR layer.
        page_type = PageType.SCANNED
    else:
        # A nearly blank page with a few typed lines.
        page_type = PageType.TEXT if text_length > 0 else PageType.EMPTY

    return PageClassification(page.number, page_type, text_length, coverage)


def classify_document(doc: pymupdf.Document) -> list[PageClassification]:
    return [classify_page(page) for page in doc]
