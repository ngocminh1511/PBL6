"""Split an appendix into its forms ("Mẫu số …") and export one as a Word document.

Form headings are matched as whole codes, not substrings, so "Mẫu số 05a" is not
mistaken for "05" and "2015" never matches "20". Extraction noise such as
"M ẫ u số 1" or "10 /PLIII" is tolerated by comparing codes without spaces.
A block that names more than one form is a table of contents and never starts a form.
"""
from __future__ import annotations

import io
import re

_HEADING = re.compile(
    r"m\s*ẫ\s*u\s*(?:s\s*ố)?\s*[:.]?\s*([0-9]+[a-z]?(?:\s*/\s*pl\s*[ivxlc]+)?)",
    re.IGNORECASE,
)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def normalize_code(code: str) -> str:
    return re.sub(r"\s+", "", code).upper()


def form_sections(item: dict) -> list[dict]:
    """Return [{code, title, block_ids}] for every form whose start block is found."""
    wanted = {normalize_code(code): code for code in item.get("forms") or []}
    blocks = item.get("blocks") or []
    if not wanted or not blocks:
        return []
    starts: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, block in enumerate(blocks):
        text = _text(block.get("html", ""))
        first = _HEADING.match(text)
        if not first:
            continue
        codes = {normalize_code(code) for code in _HEADING.findall(text)}
        code = normalize_code(first.group(1))
        if len(codes) == 1 and code in wanted and code not in seen:
            seen.add(code)
            starts.append((index, code))
    names = _titles(item)
    sections = []
    for position, (start, code) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(blocks)
        heading = _text(blocks[start].get("html", ""))
        own = heading[_HEADING.match(heading).end():].strip(" :.-")
        title = names.get(code) or (own if _useful(own) else "") or _next_line(blocks, start, end)
        sections.append({
            "code": wanted[code],
            "title": title[:200],
            "block_ids": [block.get("id") for block in blocks[start:end] if block.get("id")],
            "start": start,
            "end": end,
        })
    return sections


def _titles(item: dict) -> dict[str, str]:
    """Form names from the appendix title and table-of-contents blocks ("Mẫu số 01/PLV Hợp đồng …")."""
    sources = [item.get("title") or ""] + [_text(block.get("html", "")) for block in item.get("blocks") or []]
    names: dict[str, str] = {}
    for text in sources:
        matches = list(_HEADING.finditer(text))
        if len(matches) < 2 and text is not sources[0]:
            continue
        for position, match in enumerate(matches):
            stop = matches[position + 1].start() if position + 1 < len(matches) else len(text)
            name = text[match.end():stop].strip(" :.-;,")
            code = normalize_code(match.group(1))
            if _useful(name) and code not in names and len(name) <= 200:
                names[code] = name
    return names


def _useful(name: str) -> bool:
    """A form name, not the "Ban hành kèm theo …" issuing note printed above many forms."""
    folded = re.sub(r"\s+", "", name).lower()
    return bool(name) and not folded.startswith("banhành")


_LETTERHEAD = ("CỘNG HÒA", "ĐỘC LẬP", "ỦY BAN", "SỞ ", "VÀ XÃ HỘI", "TÊN ", "BỘ ", "CỤC ", "PHÒNG ")


def _next_line(blocks: list[dict], start: int, end: int) -> str:
    """The form's own heading, e.g. "QUYẾT ĐỊNH" + "Về việc …"; empty when there is none."""
    window = [_text(block.get("html", "")) for block in blocks[start + 1:min(end, start + 15)]]
    for index, text in enumerate(window):
        if (3 <= len(text) <= 120 and text == text.upper() and any(c.isalpha() for c in text)
                and not any(c.isdigit() for c in text) and not any(mark in text for mark in _LETTERHEAD)):
            title = text.capitalize()
            following = window[index + 1] if index + 1 < len(window) else ""
            if re.match(r"(về việc|v/v)\b", following, re.IGNORECASE):
                title += " " + following[0].lower() + following[1:]
            return title
    return ""


def form_blocks(item: dict, code: str | None) -> list[dict] | None:
    """Blocks of one form, all blocks when code is None, None when the form is unknown."""
    blocks = item.get("blocks") or []
    if code is None:
        return blocks
    target = normalize_code(code)
    for section in form_sections(item):
        if normalize_code(section["code"]) == target:
            return blocks[section["start"]:section["end"]]
    return None


def export_docx(title: str, subtitle: str, blocks: list[dict]) -> bytes:
    """Paragraphs and tables of the given blocks as an editable .docx."""
    from bs4 import BeautifulSoup
    from docx import Document
    from docx.shared import Pt

    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(13)
    document.add_heading(title, level=1)
    if subtitle:
        document.add_paragraph().add_run(subtitle).italic = True
    soup = BeautifulSoup("".join(block.get("html", "") for block in blocks), "lxml")
    root = soup.body or soup
    for node in root.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "li"], recursive=True):
        if node.find_parent("table") is not None:
            continue
        if node.name == "table":
            _add_table(document, node)
        elif node.name.startswith("h"):
            text = _text(str(node))
            if text:
                document.add_heading(text, level=min(int(node.name[1]) + 1, 4))
        else:
            if node.find_parent("li") is not None and node.name != "li":
                continue
            _add_paragraph(document.add_paragraph(), node)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _add_paragraph(paragraph, node) -> None:
    from bs4 import NavigableString
    for part in node.descendants:
        if not isinstance(part, NavigableString) or not str(part).strip("\n"):
            continue
        parents = {parent.name for parent in part.parents}
        run = paragraph.add_run(re.sub(r"\s+", " ", str(part)))
        run.bold = bool(parents & {"b", "strong"})
        run.italic = bool(parents & {"i", "em"})


def _add_table(document, table) -> None:
    rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
    if not rows:
        return
    width = max(sum(int(cell.get("colspan", 1) or 1) for cell in row.find_all(["td", "th"], recursive=False))
                for row in rows)
    grid = document.add_table(rows=len(rows), cols=max(width, 1))
    grid.style = "Table Grid"
    for r, row in enumerate(rows):
        column = 0
        for cell in row.find_all(["td", "th"], recursive=False):
            span = max(int(cell.get("colspan", 1) or 1), 1)
            if column >= width:
                break
            target = grid.cell(r, column)
            if span > 1 and column + span - 1 < width:
                target = target.merge(grid.cell(r, column + span - 1))
            target.text = _text(str(cell))
            column += span
