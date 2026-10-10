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
    StructureLevel.SECTION: re.compile(r"^\s*(?:MỤC|Mục)\s+(\d+)\b\.?\s*"),
    # OCR often gets the tone mark of "Điều" wrong ("Điêu", "Diều").
    StructureLevel.ARTICLE: re.compile(r"^\s*(?:ĐIỀU|[ĐD]i[eêèéềếểễệ]u)\s+(\d+)\b[.,]?\s*"),
    # "1." or, as OCR often reads it, "1," before a capitalised sentence.
    StructureLevel.CLAUSE: re.compile(r"^\s*(\d+)(?:\.\s+|,\s+(?=[A-ZĐÀ-Ỹ]))"),
    # Điểm labels are lower-case; OCR often capitalises them ("A) ").
    StructureLevel.POINT: re.compile(r"^\s*([a-zđA-ZĐ])\)\s+"),
}

# Lines that open almost every official document but are not its title.
_NOT_TITLE = re.compile(r"CỘNG HÒA XÃ HỘI CHỦ NGHĨA|ĐỘC LẬP\s*-\s*TỰ DO\s*-\s*HẠNH PHÚC")
_DOC_TYPES = [
    "BỘ LUẬT", "LUẬT", "PHÁP LỆNH", "NGHỊ QUYẾT", "NGHỊ ĐỊNH",
    "QUYẾT ĐỊNH", "THÔNG TƯ LIÊN TỊCH", "THÔNG TƯ", "CHỈ THỊ",
]
_APPENDIX = re.compile(r"^\s*PHỤ\s+LỤC", re.IGNORECASE)


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

    for level in (StructureLevel.CHAPTER, StructureLevel.SECTION, StructureLevel.ARTICLE):
        m = PATTERNS[level].match(stripped)
        if m:
            return ParsedLine(level, number=m.group(1), title=stripped[m.end():].strip())

    m = PATTERNS[StructureLevel.CLAUSE].match(stripped)
    # A Khoản number is small; "2019. ..." at a line start is not a Khoản.
    if m and 1 <= int(m.group(1)) <= 99:
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


def _append_text(state: _State, text: str) -> None:
    """Attach a continuation line to the innermost open unit."""
    if not text.strip():
        return
    if state.clause:
        if state.clause.points:
            point = state.clause.points[-1]
            point.text = f"{point.text} {text}".strip()
        else:
            state.clause.text = f"{state.clause.text} {text}".strip()
    elif state.article:
        state.article.full_text = f"{state.article.full_text} {text}".strip()
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


def parse_structure(text: str, document_id: str = "") -> LegalDocument:
    lines = text.split("\n")
    state = _State()

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
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

    # "Số: 45/2019/QH14", "Số: 145/2020/NĐ-CP"
    m = re.search(r"(?:Số|số)[:\s]+(\d+/\d{4}/[A-ZĐ\-]+\d*)", head)
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
    return metadata
