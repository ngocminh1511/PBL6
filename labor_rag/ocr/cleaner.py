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
    r"|\d+[a-zđ]?[.,]\s+"  # Khoan, incl. an inserted "1a."
    r"|[a-zđ]\)\s+"  # Diem
    r"|PHỤ LỤC|CỘNG HÒA|Căn cứ"
    r")",
    re.IGNORECASE | re.UNICODE,
)
_NATURAL_LINE_END = re.compile(r'[.;:!?"]$')
# "Điều 1. Phạm vi điều chỉnh" has no closing punctuation; the line after it
# is the Dieu's first sentence unless it continues the title in lower case.
_ARTICLE_HEADING = re.compile(r"^(?:ĐIỀU|[ĐD]i[eêèéềếểễệ]u)\s+\d+[a-zđ]?[.,]?\s", re.UNICODE)
_STARTS_UPPER = re.compile(r"^[A-ZĐÀ-Ỹ0-9\"“(]")


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
                or (_ARTICLE_HEADING.match(current) and _STARTS_UPPER.match(next_line))
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
# Footnotes
# ============================================================

# "5 Khoản này được ..." / "12 Luật ..." -- a superscript read as a plain number.
_FOOTNOTE_START = re.compile(r"^(\d{1,3})\s+(?=\S)")
_CLAUSE_LIKE = re.compile(r"^\d+[a-zđ]?[.,]\s")
_FOOTNOTE_KEYWORDS = re.compile(
    r"sửa đổi|bổ sung|bãi bỏ|thay thế|hợp nhất|căn cứ ban hành|có hiệu lực",
    re.IGNORECASE | re.UNICODE,
)
_MAX_FOOTNOTE_LINES = 30
_BODY_START = re.compile(
    r"^(?:(?:ĐIỀU|[ĐD]i[eêèéềếểễệ]u)\s+\d|(?:CHƯƠNG|Chương|MỤC|Mục|PHẦN|Phần)\s|\d+[a-zđ]?[.,]\s|[a-zđ]\)\s)",
    re.UNICODE,
)


# ============================================================
# Pipeline
# ============================================================

def split_footnotes(page_text: str) -> tuple[str, list[dict]]:
    """(page body, [{number, text}]): the footnote block at the bottom of a
    page, as in a van ban hop nhat ("5 Khoản này được sửa đổi, bổ sung theo
    quy định tại ..."). The block is the longest run of lines at the end of
    the page whose numbered lines count up by one and that mentions an
    amendment or a legal basis; anything else is left in the body."""
    lines = page_text.split("\n")
    starts = [
        i for i, line in enumerate(lines)
        if _FOOTNOTE_START.match(line.strip()) and not _CLAUSE_LIKE.match(line.strip())
    ]
    block_start = None
    for start in reversed(starts):
        if len(lines) - start > _MAX_FOOTNOTE_LINES:
            break
        # Body text (a Dieu/Chuong heading, a khoan, a diem) never follows the
        # footnotes on a page; if it does, these numbered lines are not footnotes.
        if any(_BODY_START.match(line.strip()) for line in lines[start:]):
            break
        numbers = [int(_FOOTNOTE_START.match(lines[i].strip()).group(1)) for i in starts if i >= start]
        if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
            break
        if _FOOTNOTE_KEYWORDS.search("\n".join(lines[start:])):
            block_start = start
    if block_start is None:
        return page_text, []

    notes: list[dict] = []
    for line in lines[block_start:]:
        match = _FOOTNOTE_START.match(line.strip())
        if match and not _CLAUSE_LIKE.match(line.strip()):
            notes.append({"number": int(match.group(1)), "text": line.strip()[match.end():].strip()})
        elif line.strip():
            notes[-1]["text"] = f"{notes[-1]['text']} {line.strip()}"
    return "\n".join(lines[:block_start]), notes


def clean_pages(
    pages_text: list[str],
    footnotes: list[dict] | None = None,
    page_numbers: list[int] | None = None,
) -> list[str]:
    """Cleaned page texts. Footnotes cut from the page bottoms are appended
    to ``footnotes`` (with the page number) when a list is given."""
    headers, footers = detect_headers_footers(pages_text)
    duplicates = detect_duplicate_pages(pages_text)

    cleaned = []
    for i, page_text in enumerate(pages_text):
        if i in duplicates:
            continue
        text = remove_lines(page_text, headers | footers)
        text = remove_page_numbers(text)
        text, notes = split_footnotes(text)
        if footnotes is not None:
            page = page_numbers[i] if page_numbers else i
            footnotes += [{"page": page, **note} for note in notes]
        text = full_normalize(text)
        text = normalize_whitespace(text)
        text = normalize_punctuation(text)
        if text.strip():
            cleaned.append(text)
    return cleaned


def clean_and_merge(
    pages_text: list[str],
    footnotes: list[dict] | None = None,
    page_numbers: list[int] | None = None,
) -> str:
    full_text = "\n".join(clean_pages(pages_text, footnotes, page_numbers))
    full_text = fix_line_breaks(full_text)
    return normalize_whitespace(full_text)
