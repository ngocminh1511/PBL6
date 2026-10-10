"""Clean page texts and merge them into one document text.

Per page: drop repeated headers/footers, duplicate pages and page numbers,
normalise Unicode, whitespace and punctuation. On the merged text: rejoin
lines that the PDF/OCR broke mid-sentence, without joining across the start
of a new Phan/Chuong/Muc/Dieu/Khoan/Diem.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from difflib import SequenceMatcher

from labor_rag.ocr import settings
from labor_rag.ocr.normalize import full_normalize

logger = logging.getLogger(__name__)


# ============================================================
# Headers / footers, page numbers, duplicate pages
# ============================================================

def detect_headers_footers(pages_text: list[str]) -> tuple[set[str], set[str]]:
    """Lines that recur in the first/last few lines of most pages."""
    if len(pages_text) < 3:
        return set(), set()

    header_counter: Counter = Counter()
    footer_counter: Counter = Counter()
    for page_text in pages_text:
        lines = [line.strip() for line in page_text.split("\n") if line.strip()]
        if not lines:
            continue
        n_zone = max(1, min(3, len(lines) // 5))
        header_counter.update(line for line in lines[:n_zone] if len(line) > 2)
        footer_counter.update(line for line in lines[-n_zone:] if len(line) > 2)

    threshold = len(pages_text) * settings.HEADER_FOOTER_FREQ_THRESHOLD
    headers = {line for line, count in header_counter.items() if count >= threshold}
    footers = {line for line, count in footer_counter.items() if count >= threshold}
    if headers or footers:
        logger.info("Header/footer patterns: %d header, %d footer", len(headers), len(footers))
    return headers, footers


def remove_lines(page_text: str, patterns: set[str]) -> str:
    if not patterns:
        return page_text
    return "\n".join(line for line in page_text.split("\n") if line.strip() not in patterns)


_PAGE_NUMBER_PATTERNS = [
    re.compile(r"^\s*\d{1,4}\s*$"),  # 42
    re.compile(r"^\s*-\s*\d{1,4}\s*-\s*$"),  # - 42 -
    re.compile(r"^\s*Trang\s+\d{1,4}\s*$", re.I),  # Trang 42
    re.compile(r"^\s*Page\s+\d{1,4}\s*$", re.I),  # Page 42
    re.compile(r"^\s*\d{1,4}\s*/\s*\d{1,4}\s*$"),  # 42/120
]


def remove_page_numbers(text: str) -> str:
    return "\n".join(
        line for line in text.split("\n")
        if not any(p.match(line.strip()) for p in _PAGE_NUMBER_PATTERNS)
    )


def detect_duplicate_pages(pages_text: list[str]) -> set[int]:
    """Indices of pages that repeat an earlier page (the first copy is kept)."""
    threshold = settings.DUPLICATE_PAGE_SIMILARITY
    stripped = [p.strip() for p in pages_text]
    duplicates: set[int] = set()
    for i in range(len(stripped) - 1):
        if i in duplicates or not stripped[i]:
            continue
        for j in range(i + 1, len(stripped)):
            if j in duplicates or not stripped[j]:
                continue
            matcher = SequenceMatcher(None, stripped[i], stripped[j])
            # real_quick_ratio/quick_ratio are cheap upper bounds of ratio().
            if (
                matcher.real_quick_ratio() >= threshold
                and matcher.quick_ratio() >= threshold
                and matcher.ratio() >= threshold
            ):
                duplicates.add(j)
                logger.info("Page %d duplicates page %d", j, i)
    return duplicates


# ============================================================
# Line breaks, whitespace, punctuation
# ============================================================

# Start of a new structural unit: never joined to the previous line.
_STRUCTURE_START = re.compile(
    r"^("
    r"Phần\s+|Chương\s+|Mục\s+|Tiểu mục\s+|[ĐD]i[eêèéềếểễệ]u\s+\d+"  # incl. OCR variants of Điều
    r"|\d+[.,]\s+"  # Khoan
    r"|[a-zđ]\)\s+"  # Diem
    r"|PHỤ LỤC|CỘNG HÒA|Căn cứ"
    r")",
    re.IGNORECASE | re.UNICODE,
)
_NATURAL_LINE_END = re.compile(r'[.;:!?"]$')


def fix_line_breaks(text: str) -> str:
    """Join a line to the next one unless it ends a sentence, is an
    all-caps title, or the next line starts a new structural unit."""
    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        current = lines[i].rstrip()
        if not current:
            result.append("")
            i += 1
            continue
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if (
                not next_line
                or _NATURAL_LINE_END.search(current)
                or _STRUCTURE_START.match(next_line)
                or (current.isupper() and len(current) > 5)
            ):
                break
            current = current + " " + next_line
            i += 1
        result.append(current)
        i += 1
    return "\n".join(result)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\t", " ")
    text = re.sub(r" {2,}", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_punctuation(text: str) -> str:
    text = re.sub(r"\s+([.,:;!?)\]])", r"\1", text)  # no space before punctuation
    text = re.sub(r"([.,:;!?)])([A-ZÀ-Ỹa-zà-ỹ])", r"\1 \2", text)  # a space after it
    text = re.sub(r"([\[(])\s+", r"\1", text)  # none after an opening bracket
    return text


# ============================================================
# Pipeline
# ============================================================

def clean_pages(pages_text: list[str]) -> list[str]:
    headers, footers = detect_headers_footers(pages_text)
    duplicates = detect_duplicate_pages(pages_text)

    cleaned = []
    for i, page_text in enumerate(pages_text):
        if i in duplicates:
            continue
        text = remove_lines(page_text, headers | footers)
        text = remove_page_numbers(text)
        text = full_normalize(text)
        text = normalize_whitespace(text)
        text = normalize_punctuation(text)
        if text.strip():
            cleaned.append(text)
    return cleaned


def clean_and_merge(pages_text: list[str]) -> str:
    full_text = "\n".join(clean_pages(pages_text))
    full_text = fix_line_breaks(full_text)
    return normalize_whitespace(full_text)
