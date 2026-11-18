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
    r"Phần\s+|Chương\s+|M[ụu]c\s*\d+|Tiểu mục\s+|(?:ĐIỀU|[ĐDđd]i[eêèéềếểễệ][unp])\s+\d+"  # incl. OCR variants of Mục, Điều
    r"|(?:[-*•]\s*)?\d+[a-zđ]?(?:\.(?!\d)\s*|[,/:)]\s+(?=[A-ZĐÀ-Ỹ]))"  # Khoan, incl. tolerant OCR delimiters
    r"|[a-zđ]\)\s+"  # Diem
    r"|PHỤ LỤC|CỘNG HÒA|Căn cứ"
    r")",
    re.IGNORECASE | re.UNICODE,
)
_NATURAL_LINE_END = re.compile(r'[.;:!?"]$')
# "Điều 1. Phạm vi điều chỉnh" has no closing punctuation; the line after it
# is the Dieu's first sentence unless it continues the title in lower case.
_ARTICLE_HEADING = re.compile(r"^(?:ĐIỀU|[ĐDđd]i[eêèéềếểễệ][unp])\s+\d+[a-zđ]?[.,:]?\s", re.UNICODE | re.IGNORECASE)
_STARTS_UPPER = re.compile(r"^[A-ZĐÀ-Ỹ0-9\"“(]")

_REF_PREFIX_RE = re.compile(
    r"\b(?:theo(?:\s+quy\s+đ[iì]nh)?\s+tại|tại|ở|khoản\s+\d+[a-zđ]?|điểm\s+[a-zđ]|các|và|hoặc|đến|của)\s+$",
    re.IGNORECASE | re.UNICODE,
)

_EMBEDDED_HEADING_RE = re.compile(
    r"(?<![a-zA-ZÀ-Ỹà-ỹ0-9])((?:ĐIỀU|[ĐDđd]i[eêèéềếểễệ][unp])\s+(\d+[a-zđ]?)(?:[.,:\s-]\s*|[.,]\s*)(?=[A-ZĐÀ-Ỹ]))",
    re.UNICODE,
)

_REF_BEFORE_CLAUSE = re.compile(
    r"(?:\b(?:khoản|điểm\s+[a-zđ](?:\s+khoản)?|điều|mục|chương|phần|ngày|tháng|năm|số|lần|thứ|từ|đến|trước|sau|tại|theo|của|và|hoặc|gồm)|[,/])\s*$",
    re.IGNORECASE | re.UNICODE,
)

_EMBEDDED_CLAUSE_RE = re.compile(
    r"(?<![\w.,/])([1-9]\d?[a-zđ]?[.,]\s+(?=[A-ZĐÀ-Ỹ]))",
    re.UNICODE,
)

_EMBEDDED_POINT_RE = re.compile(
    r"(?<=[;.:])\s+([a-zđ]\)\s+(?=[A-ZĐÀ-Ỹa-zđà-ỹ]))",
    re.UNICODE,
)

_ARTICLE_ALIAS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:quyền\s+)?liều\s+32/\s*Tr\S+\s+h[ơờởỡợ]p", re.IGNORECASE | re.UNICODE), "\nĐiều 37. Trường hợp"),
    (re.compile(r"đứt\s+điều\s+31,\s*Nghĩa\s+vụ", re.IGNORECASE | re.UNICODE), "đứt\nĐiều 41. Nghĩa vụ"),
    (re.compile(r"(?:ngàn\s+)?Diên,\s*54\.\s*Mở\s+r[oồ]ng", re.IGNORECASE | re.UNICODE), "\nĐiều 84. Mở rộng"),
    (re.compile(r"(?:Thỏa\s+)?Diêu\s+Số\s+a\s+Gia\s+nhập", re.IGNORECASE | re.UNICODE), "\nĐiều 85. Gia nhập"),
    (re.compile(r"Điều\s+135,\s*Quyền\s+đơn\s+phương\s+chấm\s+dứt,\s*tạm\s+hoãn", re.IGNORECASE | re.UNICODE), "\nĐiều 138. Quyền đơn phương chấm dứt, tạm hoãn"),
    (re.compile(r"(?:Thuộc\s+)?Điều\s+15%\s*Người\s+lao\s+động\s+nước\s+ngoài", re.IGNORECASE | re.UNICODE), "\nĐiều 154. Người lao động nước ngoài"),
    (re.compile(r"(?:Về\s+quyền\s+)?194,\s*Thời\s+hiệu\s+yêu\s+cầu", re.IGNORECASE | re.UNICODE), "\nĐiều 194. Thời hiệu yêu cầu"),
    (re.compile(r"Điều\s+6,\s*Phải\s+hoàn\s+trả\s+cho\s+người\s+sử\s+dụng\s+lao\s+động", re.IGNORECASE | re.UNICODE), "\n3. Phải hoàn trả cho người sử dụng lao động"),
    (re.compile(r"Điều\s+1\s+Trong\s+1\s+Trị\s+Trì", re.UNICODE), "Trong 1 Trị Trì"),
    (re.compile(r"(?:Đ[iị][eêệ][nupt]|Điều)\s+1\s+cầu\s+Tòa\s+ăn", re.IGNORECASE | re.UNICODE), "\n1. Cầu Tòa án"),
)


def _split_embedded_units(line: str) -> list[str]:
    """Split embedded Article headings and Clause numbers glued onto one line."""
    # First split embedded Article headings
    segments: list[str] = []
    matches = list(_EMBEDDED_HEADING_RE.finditer(line))
    last_idx = 0
    for m in matches:
        start = m.start()
        if start == 0:
            continue
        prefix = line[last_idx:start]
        if _REF_PREFIX_RE.search(prefix):
            continue
        if prefix.strip():
            segments.append(prefix.strip())
        last_idx = start
    rem = line[last_idx:].strip()
    if rem:
        segments.append(rem)

    # Then split embedded Clauses and Points inside each segment
    out: list[str] = []
    for seg in segments:
        seg = _EMBEDDED_POINT_RE.sub(r"\n\1", seg)
        for sub in seg.split("\n"):
            sub = sub.strip()
            if not sub:
                continue
            last_c = 0
            for cm in _EMBEDDED_CLAUSE_RE.finditer(sub):
                c_start = cm.start()
                if c_start == 0:
                    continue
                c_prefix = sub[last_c:c_start]
                if not c_prefix.endswith((" ", "\t")):
                    continue
                if _REF_BEFORE_CLAUSE.search(c_prefix):
                    continue
                cleaned_prefix = re.sub(r"\s+-$", "", c_prefix.strip())
                if cleaned_prefix:
                    out.append(cleaned_prefix)
                last_c = c_start
            c_rem = sub[last_c:].strip()
            if c_rem:
                out.append(c_rem)
    return out


_LEGAL_TYPO_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bĐiêu\b", re.UNICODE), "Điều"),
    (re.compile(r"\bDiều\b", re.UNICODE), "Điều"),
    (re.compile(r"\b(?:Diệu|Điên|Điền|Điềp)\s+(?=\d+)", re.UNICODE), "Điều "),
    (re.compile(r"\bhợp đông\b", re.UNICODE), "hợp đồng"),
    (re.compile(r"\btiêu chuâ\b", re.UNICODE), "tiêu chuẩn"),
    (re.compile(r"\bchâm dứt\b", re.UNICODE), "chấm dứt"),
    (re.compile(r"\btiên lương\b", re.UNICODE), "tiền lương"),
    (re.compile(r"\bnghĩa vu\b", re.UNICODE), "nghĩa vụ"),
    (re.compile(r"\bthực hiên\b", re.UNICODE), "thực hiện"),
    (re.compile(r"\bbảo hiêm\b", re.UNICODE), "bảo hiểm"),
    (re.compile(r"\bthâm quyền\b", re.UNICODE), "thẩm quyền"),
    (re.compile(r"\bhiêu lực\b", re.UNICODE), "hiệu lực"),
    (re.compile(r"\bquy đinh\b", re.UNICODE), "quy định"),
    (re.compile(r"\btô chức\b", re.UNICODE), "tổ chức"),
    (re.compile(r"\bTô chức\b", re.UNICODE), "Tổ chức"),
    (re.compile(r"\bđôi với\b", re.UNICODE), "đối với"),
    (re.compile(r"\bĐôi với\b", re.UNICODE), "Đối với"),
    (re.compile(r"\bbăng văn bản\b", re.UNICODE), "bằng văn bản"),
    (re.compile(r"\bkhuyên khích\b", re.UNICODE), "khuyến khích"),
    (re.compile(r"\btrường họp\b", re.UNICODE), "trường hợp"),
    (re.compile(r"\bthỏa thuân\b", re.UNICODE), "thỏa thuận"),
    (re.compile(r"\blạo động\b", re.UNICODE), "lao động"),
    (re.compile(r"\blao đông\b", re.UNICODE), "lao động"),
    (re.compile(r"\bsử dung\b", re.UNICODE), "sử dụng"),
    (re.compile(r"\bquyên lợi\b", re.UNICODE), "quyền lợi"),
    (re.compile(r"\btrách nhiêm\b", re.UNICODE), "trách nhiệm"),
    (re.compile(r"\bgiải quyêt\b", re.UNICODE), "giải quyết"),
    (re.compile(r"\bđiêu kiện\b", re.UNICODE), "điều kiện"),
    # Chapter Roman numeral OCR substitutions (e.g. Chương H -> Chương II, Chương 111 -> Chương III)
    (re.compile(r"^\s*Chương\s+H(?=\s+[A-ZĐÀ-Ỹ])", re.MULTILINE | re.UNICODE), "Chương II"),
    (re.compile(r"^\s*Chương\s+111(?=\s+[A-ZĐÀ-Ỹ])", re.MULTILINE | re.UNICODE), "Chương III"),
    (re.compile(r"^\s*Chương\s+V11(?=\s+KỶ)", re.MULTILINE | re.UNICODE), "Chương VIII"),
    (re.compile(r"^\s*Chương\s+V111(?=\s+[A-ZĐÀ-Ỹ])", re.MULTILINE | re.UNICODE), "Chương VIII"),
    (re.compile(r"^\s*Chương\s+1X(?=\s+[A-ZĐÀ-Ỹ])", re.MULTILINE | re.UNICODE), "Chương IX"),
    (re.compile(r"^\s*Chương\s+X11(?=\s+[A-ZĐÀ-Ỹ])", re.MULTILINE | re.UNICODE), "Chương XII"),
    (re.compile(r"^\s*Chương\s+Xn(?=\s+[A-ZĐÀ-Ỹ])", re.MULTILINE | re.UNICODE), "Chương XIII"),
)


def _normalize_legal_typos(text: str) -> str:
    for pattern, replacement in _LEGAL_TYPO_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def preprocess_legal_text(text: str) -> str:
    """Normalize common OCR tone/spelling errors in Vietnamese legal documents
    and split embedded Article headings and Clauses glued onto preceding lines."""
    # 1. Common Vietnamese legal terminology OCR typos
    text = _normalize_legal_typos(text)

    # 2. Contextual alias mapping for severely garbled Article headings
    for pattern, replacement in _ARTICLE_ALIAS_PATTERNS:
        text = pattern.sub(replacement, text)

    # 3. Split embedded Article headings, Clauses, and Points glued to preceding text
    new_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            new_lines.append("")
            continue
        new_lines.extend(_split_embedded_units(stripped))

    return "\n".join(new_lines)


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
# A footnote opens with a capital; "6 tháng tuổi, ..." or "01 tháng 01 năm
# 2026 ..." at a line start is body text that wrapped after a number.
_FOOTNOTE_START = re.compile(r"^(\d{1,3})\s+(?=[A-ZĐÀ-Ỹ])")
_CLAUSE_LIKE = re.compile(r"^\d+[a-zđ]?[.,]\s")
_FOOTNOTE_KEYWORDS = re.compile(
    r"sửa đổi|bổ sung|bãi bỏ|thay thế|hợp nhất|căn cứ ban hành|có hiệu lực",
    re.IGNORECASE | re.UNICODE,
)
_MAX_FOOTNOTE_LINES = 30
_BODY_START = re.compile(
    r"^(?:(?:ĐIỀU|[ĐD]i[eêèéềếểễệ]u)\s+\d|(?:CHƯƠNG|Chương|M[ỤU]C|M[ụu]c|PHẦN|Phần)\s|\d+[a-zđ]?[.,]\s|[a-zđ]\)\s)",
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
        text = preprocess_legal_text(text)
        if text.strip():
            cleaned.append(text)
    return cleaned


def clean_and_merge(
    pages_text: list[str],
    footnotes: list[dict] | None = None,
    page_numbers: list[int] | None = None,
) -> str:
    full_text = "\n".join(clean_pages(pages_text, footnotes, page_numbers))
    full_text = preprocess_legal_text(full_text)
    full_text = fix_line_breaks(full_text)
    full_text = preprocess_legal_text(full_text)
    return normalize_whitespace(full_text)
