"""Parse cleaned legal text into the 6-level hierarchy of Vietnamese law.

    1. Phần    "Phần thứ nhất", "PHẦN I"
    2. Chương  "Chương I", "CHƯƠNG XIV"
    3. Mục     "Mục 1"
    4. Điều    "Điều 1.", "Điều 220"
    5. Khoản   "1. ", "2. "
    6. Điểm    "a) ", "đ) "

Each line is matched against these patterns from the highest level down; a
state machine tracks the open Phần/Chương/Mục/Điều/Khoản and attaches
continuation lines to the innermost open unit.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import IntEnum

from labor_rag.ocr.schemas import (
    Article,
    Chapter,
    Clause,
    DocumentMetadata,
    LegalDocument,
    Part,
    Point,
    Section,
)

logger = logging.getLogger(__name__)


class StructureLevel(IntEnum):
    PART = 1
    CHAPTER = 2
    SECTION = 3
    ARTICLE = 4
    CLAUSE = 5
    POINT = 6
    TEXT = 7


PATTERNS = {
    StructureLevel.PART: re.compile(
        r"^\s*PHẦN\s+"
        r"(?:"
        r"(?:THỨ\s+)?(?:NHẤT|HAI|BA|BỐN|NĂM|SÁU|BẢY|TÁM|CHÍN|MƯỜI"
        r"(?:\s+MỘT|\s+HAI|\s+BA|\s+BỐN|\s+LĂM)?)"
        r"|[IVXLCDM]+"
        r"|[0-9]+"
        r")",
        re.IGNORECASE | re.UNICODE,
    ),
    StructureLevel.CHAPTER: re.compile(r"^\s*(?:CHƯƠNG|Chương)\s+([IVXLCDM]+|[0-9]+)\b\.?\s*"),
    # OCR often drops the dot below or space: "Muc 3", "Muc4".
    StructureLevel.SECTION: re.compile(r"^\s*(?:M[ỤU]C|M[ụu]c)\s*(\d+)\b\.?\s*"),
    # OCR often gets the tone mark or ending of "Điều" wrong ("Điêu", "Diều", "Diệu", "Điên", "Điền", "Điềp").
    # An inserted Dieu keeps its neighbour's number plus a letter: "Điều 35a".
    StructureLevel.ARTICLE: re.compile(
        r"^\s*(?:ĐIỀU|[ĐDđd]i[eêèéềếểễệ][unp])\s+([1-9]\d*[a-zđ]?)(?=[.,:\s-]|$)[.,:]?\s*",
        re.UNICODE | re.IGNORECASE,
    ),
    # "1." (with or without space after dot, avoiding decimals like 1.5), or OCR variants
    # ("1,", "1/", "1:", "1)") before a capitalised sentence, optionally with a leading bullet.
    StructureLevel.CLAUSE: re.compile(
        r"^\s*(?:[-*•]\s*)?(\d+[a-zđ]?)(?:\.(?!\d)\s*|[,/:)]\s+(?=[A-ZĐÀ-Ỹ]))",
        re.UNICODE,
    ),
    # Điểm labels are lower-case; OCR often capitalises them ("A) ").
    StructureLevel.POINT: re.compile(r"^\s*([a-zđA-ZĐ])\)\s+"),
}

# Lines that open almost every official document but are not its title.
_NOT_TITLE = re.compile(r"CỘNG HÒA XÃ HỘI CHỦ NGHĨA|ĐỘC LẬP\s*-\s*TỰ DO\s*-\s*HẠNH PHÚC")
_DOC_TYPES = [
    "BỘ LUẬT", "LUẬT", "PHÁP LỆNH", "NGHỊ QUYẾT", "NGHỊ ĐỊNH",
    "QUYẾT ĐỊNH", "THÔNG TƯ LIÊN TỊCH", "THÔNG TƯ", "CHỈ THỊ",
]
_APPENDIX = re.compile(
    r"^\s*(?:PHỤ\s+LỤC(?:\s|$)|Phụ\s+lục(?:\s+(?:[IVXLCDM]+|\d+|số\s+\d+))?(?:\s*[:.\-–]|\s*$))",
    re.UNICODE,
)


@dataclass
class ParsedLine:
    level: StructureLevel
    number: str = ""  # "I", "1", "a"
    title: str = ""  # heading text of Phần/Chương/Mục/Điều
    text: str = ""  # body text of Khoản/Điểm/plain lines


def parse_line(line: str) -> ParsedLine:
    stripped = line.strip()
    if not stripped:
        return ParsedLine(level=StructureLevel.TEXT)

    m = PATTERNS[StructureLevel.PART].match(stripped)
    if m:
        return ParsedLine(StructureLevel.PART, number=m.group().strip(), title=stripped[m.end():].strip())

    for level in (StructureLevel.CHAPTER, StructureLevel.SECTION):
        m = PATTERNS[level].match(stripped)
        if m:
            return ParsedLine(level, number=m.group(1), title=stripped[m.end():].strip())

    m = PATTERNS[StructureLevel.ARTICLE].match(stripped)
    if m:
        num_m = re.match(r"\d+", m.group(1))
        # A valid Dieu number in legal documents is between 1 and 350
        if num_m and 1 <= int(num_m.group()) <= 350:
            return ParsedLine(StructureLevel.ARTICLE, number=m.group(1), title=stripped[m.end():].strip())

    m = PATTERNS[StructureLevel.CLAUSE].match(stripped)
    # A Khoản number is small; "2019. ..." at a line start is not a Khoản.
    if m and 1 <= int(re.match(r"\d+", m.group(1)).group()) <= 99:
        return ParsedLine(StructureLevel.CLAUSE, number=m.group(1), text=stripped[m.end():].strip())

    m = PATTERNS[StructureLevel.POINT].match(stripped)
    if m:
        return ParsedLine(StructureLevel.POINT, number=m.group(1).lower(), text=stripped[m.end():].strip())

    return ParsedLine(StructureLevel.TEXT, text=stripped)


# ============================================================
# State machine
# ============================================================

@dataclass
class _State:
    part: Part | None = None
    chapter: Chapter | None = None
    section: Section | None = None
    article: Article | None = None
    clause: Clause | None = None

    preamble_lines: list[str] = field(default_factory=list)
    appendix_lines: list[str] = field(default_factory=list)
    in_preamble: bool = True
    in_appendix: bool = False

    parts: list[Part] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)  # not inside a Phần
    articles: list[Article] = field(default_factory=list)  # not inside a Chương


def _make_id(*parts: str) -> str:
    return "_".join(p.lower().replace(" ", "_").replace(".", "").strip("_") for p in parts if p)


def _flush_clause(state: _State) -> None:
    if state.clause and state.article:
        state.article.clauses.append(state.clause)
    state.clause = None


def _flush_article(state: _State) -> None:
    _flush_clause(state)
    if state.article:
        if state.section:
            state.section.articles.append(state.article)
        elif state.chapter:
            state.chapter.articles.append(state.article)
        elif state.part and state.part.chapters:
            state.part.chapters[-1].articles.append(state.article)
        else:
            state.articles.append(state.article)
    state.article = None


def _flush_section(state: _State) -> None:
    _flush_article(state)
    if state.section:
        if state.chapter:
            state.chapter.sections.append(state.section)
        else:
            # A Mục outside any Chương: keep its Điều at document level.
            state.articles.extend(state.section.articles)
    state.section = None


def _flush_chapter(state: _State) -> None:
    _flush_section(state)
    if state.chapter:
        (state.part.chapters if state.part else state.chapters).append(state.chapter)
    state.chapter = None


def _flush_part(state: _State) -> None:
    _flush_chapter(state)
    if state.part:
        state.parts.append(state.part)
    state.part = None


def _append_text(state: _State, text: str, sep: str = " ") -> None:
    """Attach a continuation line to the innermost open unit (a newline sep keeps quoted lines apart)."""
    if not text.strip():
        return
    if state.clause:
        if state.clause.points:
            point = state.clause.points[-1]
            point.text = f"{point.text}{sep}{text}".strip()
        else:
            state.clause.text = f"{state.clause.text}{sep}{text}".strip()
    elif state.article:
        state.article.full_text = f"{state.article.full_text}{sep}{text}".strip()
    elif state.in_appendix:
        state.appendix_lines.append(text)
    elif state.in_preamble:
        state.preamble_lines.append(text)


def _find_title(lines: list[str]) -> str:
    """The all-caps document-type line (LUẬT ..., NGHỊ ĐỊNH ...) near the
    top, else the first long all-caps line that is not the national motto."""
    head = [line.strip() for line in lines[:40] if line.strip() and line.isupper()]
    for line in head:
        if any(line.startswith(t) for t in _DOC_TYPES):
            return line
    for line in head:
        if len(line) > 10 and not _NOT_TITLE.search(line):
            return line
    return ""


# A quotation longer than this many lines is taken as an opening quote whose
# closing one OCR lost, so it does not swallow the rest of the document.
MAX_QUOTED_LINES = 150

_QUOTE_CHARS = '"“”'
_AMENDING_TITLE = re.compile(r"sửa\s+đ[oổ]i|b[oổ]\s+sung|bãi\s+bỏ", re.IGNORECASE)


def _opens_quote(line: str, previous: str) -> bool:
    """An amendment quotation starts a line right after a lead ending in ":" ("... như sau:")."""
    return line.lstrip()[:1] in _QUOTE_CHARS and previous.rstrip().endswith(":")


def _closes_quote(line: str) -> bool:
    """A line ending in a quote mark; a lone mark (split off "\\"Điều 32") only opens."""
    text = line.strip().rstrip(".;,").rstrip()
    return len(text) > 1 and text[-1] in _QUOTE_CHARS


def quoted_lines(lines: list[str]) -> set[int]:
    """Indexes of the lines inside a quotation that spans several lines.

    An amending article quotes the new wording of another document:
        2. Sửa đổi, bổ sung Điều 32 của Bộ luật Tố tụng dân sự như sau:
        "Điều 32. Những tranh chấp về lao động ...
        1. Tranh chấp lao động cá nhân ...
        a) Về xử lý kỷ luật lao động ..."
    The "1." and "a)" there belong to the quoted text, not to this document,
    so they must not open a Khoản or Điểm. Quote marks in OCR text are
    unreliable (lost, or "FA \"Ng\"\"" from a smudge), so counting them is
    not enough: a quotation opens only at the start of a line that follows a
    lead ending in ":", and closes at the first line ending in a quote mark.
    Another opening before that means the closing mark was lost; a quotation
    not closed within MAX_QUOTED_LINES lines is ignored. The opening line is
    parsed as usual; the lines after it, up to the closing one, are text.
    """
    content = [(i, line) for i, line in enumerate(lines) if line.strip()]
    quoted: set[int] = set()
    k = 1
    while k < len(content):
        start, line = content[k]
        if not _opens_quote(line, content[k - 1][1]) or _closes_quote(line):
            k += 1
            continue
        end = None
        for m in range(k + 1, min(len(content), k + 1 + MAX_QUOTED_LINES)):
            if _opens_quote(content[m][1], content[m - 1][1]):
                break
            if _closes_quote(content[m][1]):
                end = m
                break
        if end is None:
            k += 1
            continue
        quoted.update(i for i, _ in content[k + 1:end + 1])
        k = end + 1
    return quoted


def parse_structure(text: str, document_id: str = "") -> LegalDocument:
    lines = text.split("\n")
    state = _State()
    quoted = quoted_lines(lines)

    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        if index in quoted and state.article and _AMENDING_TITLE.search(state.article.article_title):
            _append_text(state, stripped, "\n")
            continue

        if _APPENDIX.match(stripped):
            _flush_part(state)
            state.in_appendix = True
            state.in_preamble = False
        if state.in_appendix:
            state.appendix_lines.append(stripped)
            continue

        parsed = parse_line(stripped)

        if parsed.level == StructureLevel.PART:
            _flush_part(state)
            state.in_preamble = False
            label = parsed.number.split()[-1] if parsed.number else str(len(state.parts) + 1)
            state.part = Part(part_id=_make_id("phan", label), part_number=parsed.number, part_title=parsed.title)

        elif parsed.level == StructureLevel.CHAPTER:
            _flush_chapter(state)
            state.in_preamble = False
            state.chapter = Chapter(
                chapter_id=_make_id("chuong", parsed.number),
                chapter_number=f"Chương {parsed.number}",
                chapter_title=parsed.title,
            )

        elif parsed.level == StructureLevel.SECTION:
            _flush_section(state)
            state.in_preamble = False
            state.section = Section(
                section_id=_make_id(state.chapter.chapter_id if state.chapter else "", "muc", parsed.number),
                section_number=f"Mục {parsed.number}",
                section_title=parsed.title,
            )

        elif parsed.level == StructureLevel.ARTICLE:
            if state.clause and re.match(r"^(?:và|hoặc|của\s+[Bb]ộ\s+luật|của\s+[Ll]uật|thì\s+)\b", parsed.title, re.IGNORECASE):
                _append_text(state, stripped)
                continue
            # When inside an amending article (e.g. Điều 219), smaller article numbers (e.g. Điều 54, 55)
            # are quoted amendment targets belonging to this article rather than new root-level articles.
            if state.article and re.search(r"sửa\s+đ[oổ]i|b[oổ]\s+sung|bãi\s+bỏ", state.article.article_title, re.IGNORECASE):
                cur_num_m = re.match(r"\d+", state.article.article_number.split()[-1])
                new_num_m = re.match(r"\d+", parsed.number)
                if cur_num_m and new_num_m and int(new_num_m.group()) < int(cur_num_m.group()):
                    _append_text(state, stripped)
                    continue
            _flush_article(state)
            state.in_preamble = False
            state.article = Article(
                article_id=_make_id("dieu", parsed.number),
                article_number=f"Điều {parsed.number}",
                article_title=parsed.title,
            )

        elif parsed.level == StructureLevel.CLAUSE and state.article:
            _flush_clause(state)
            state.clause = Clause(
                clause_id=_make_id(state.article.article_id, "khoan", parsed.number),
                clause_number=f"Khoản {parsed.number}",
                text=parsed.text,
            )

        elif parsed.level == StructureLevel.POINT and state.clause:
            state.clause.points.append(Point(
                point_id=_make_id(state.clause.clause_id, "diem", parsed.number),
                point_label=parsed.number,
                text=parsed.text,
            ))

        else:
            # Plain text, or a Khoản/Điểm marker outside a Điều/Khoản
            # (a numbered list in the preamble): keep the line as text.
            _append_text(state, stripped)

    _flush_part(state)

    title = _find_title(lines)
    doc = LegalDocument(
        document_id=document_id or (_make_id(title[:50]) if title else "unknown"),
        title=title,
        preamble="\n".join(state.preamble_lines),
        parts=state.parts,
        chapters=state.chapters,
        articles=state.articles,
        appendices=state.appendix_lines,
        full_text=text,
    )
    n_chapters = len(doc.chapters) + sum(len(p.chapters) for p in doc.parts)
    logger.info(
        "Structure: %d Phần, %d Chương, %d Điều",
        len(doc.parts), n_chapters, sum(1 for _ in doc.iter_articles()),
    )
    return doc


# ============================================================
# Metadata from the first page
# ============================================================

def extract_metadata(text: str, title: str = "", source_file: str = "", total_pages: int = 0) -> DocumentMetadata:
    metadata = DocumentMetadata(source_file=source_file, total_pages=total_pages)
    head = text[:3000]

    # "Số: 45/2019/QH14", "Luật số: 84/2015/QH13", "Số : 40/2021/QĐ-TTg".
    # In a VBHN the number of the consolidated document comes before "được
    # sửa đổi, bổ sung bởi:"; the amending documents listed after it have
    # numbers too, so a miss before it must not fall through to them.
    amended_by = _AMENDED_BY.search(head)
    m = re.search(_SO + r"\s*:?\s*" + _SO_HIEU, head[: amended_by.start()] if amended_by else head, re.IGNORECASE)
    if m:
        metadata.so_hieu = m.group(1)

    # Prefer the title: the body of a Nghị định cites "Căn cứ Luật ...".
    title_upper = title.upper()
    doc_type = next((t for t in _DOC_TYPES if title_upper.startswith(t)), None)
    if doc_type is None:
        doc_type = next((t for t in _DOC_TYPES if t in head[:1000].upper()), None)
    if doc_type:
        metadata.loai_van_ban = doc_type.capitalize()

    m = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", head, re.IGNORECASE)
    if m:
        metadata.ngay_ban_hanh = f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    for pattern in (r"QUỐC\s+HỘI", r"THỦ\s+TƯỚNG\s+CHÍNH\s+PHỦ", r"CHÍNH\s+PHỦ", r"BỘ\s+(?!LUẬT)[A-ZĐÀ-Ỹ ,-]+"):
        m = re.search(pattern, head[:1000])
        if m:
            metadata.co_quan_ban_hanh = m.group().strip()
            break

    _consolidation_metadata(metadata, text, head)
    return metadata


# A van ban hop nhat (VBHN) opens with "Bộ luật Lao động số 45/2019/QH14 ngày
# ... , có hiệu lực kể từ ngày 01 tháng 01 năm 2021, được sửa đổi, bổ sung
# bởi:" and a numbered list of the amending documents with their own dates.
_SO_HIEU = r"(\d+[a-z]?/\d{4}/[\wĐđÐ-]+)"
# "số", as OCR also reads it: "sô", "só", "so".
_SO = r"\bs[ốôóo]"
_VBHN_NUMBER = re.compile(_SO + r"\s*:?\s*(\d+/VBHN-[\wĐđÐ-]+)", re.IGNORECASE)
_AMENDED_BY = re.compile(r"được\s+sửa\s+đổi,?\s+bổ\s+sung\s+bởi\s*:", re.IGNORECASE)
_EFFECTIVE = re.compile(
    r"có\s+hiệu\s+lực\s+(?:thi\s+hành\s+)?(?:k[ểêe]\s+)?từ\s+ngày\s+"  # OCR: "kê từ"
    r"(?:(\d{1,2})/(\d{1,2})/(\d{4})|(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4}))",
    re.IGNORECASE,
)
# "Bộ luật này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021." in the Dieu on entry into force.
_OWN_EFFECTIVE = re.compile(
    r"(?:Bộ\s+luật|Luật|Pháp\s+lệnh|Nghị\s+quyết|Nghị\s+định|Quyết\s+định|Thông\s+tư(?:\s+liên\s+tịch)?)\s+này\s+"
    + _EFFECTIVE.pattern,
    re.IGNORECASE,
)
_LIST_ITEM = re.compile(r"(?m)^\s*\d+[.,]\s+")


def _effective_date(match: re.Match) -> str:
    day, month, year = (match.group(1), match.group(2), match.group(3)) if match.group(3) else match.group(4, 5, 6)
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def _consolidation_metadata(metadata: DocumentMetadata, text: str, head: str) -> None:
    """Fill hop_nhat, so_hieu_vbhn, van_ban_sua_doi, ngay_hieu_luc and version_date."""
    vbhn = _VBHN_NUMBER.search(head)
    if vbhn:
        metadata.so_hieu_vbhn = vbhn.group(1)
    amended_by = _AMENDED_BY.search(head)
    metadata.hop_nhat = bool(vbhn or amended_by)

    if amended_by:
        own = _EFFECTIVE.search(head[: amended_by.start()])
        if own:
            metadata.ngay_hieu_luc = _effective_date(own)
        # The list ends where the preamble ("Căn cứ ...") or the body starts.
        rest = head[amended_by.end():]
        end = re.search(r"Căn\s+cứ|^\s*(?:Chương|CHƯƠNG|Điều|PHẦN|Phần)\s", rest, re.MULTILINE)
        listing = rest[: end.start()] if end else rest
        for item in _LIST_ITEM.split(listing):
            number = re.search(_SO + r"\s+" + _SO_HIEU, item, re.IGNORECASE)
            effective = _EFFECTIVE.search(item)
            if number:
                metadata.van_ban_sua_doi.append(
                    {"so_hieu": number.group(1), "ngay_hieu_luc": _effective_date(effective) if effective else ""}
                )
    if not metadata.ngay_hieu_luc:
        own = _OWN_EFFECTIVE.search(text)
        if own:
            metadata.ngay_hieu_luc = _effective_date(re.search(_EFFECTIVE, own.group()))

    dates = [metadata.ngay_hieu_luc, *(doc["ngay_hieu_luc"] for doc in metadata.van_ban_sua_doi)]
    metadata.version_date = max((d for d in dates if d), default="")
