"""Parse one data/raw/bophapdien/linh_vuc/<chu_de>/<de_muc>.html file into a hierarchical tree.

This module is the single HTML reader for the Bo Phap Dien dump. It writes
no files: build_abox.py calls parse_demuc_nodes() and turns the tree into the
ontology v4 ABox directly.

Key HTML facts (verified on all 306 de muc files):

* The source markup nests <p> inside <p class='pNoiDung'>, which is invalid
  HTML. lxml (like real browsers) auto-closes the outer <p>, so `pNoiDung`
  becomes an empty marker and the content paragraphs become classless
  siblings that follow it. html.parser does NOT do this and, on files with an
  unclosed <p> (e.g. 20.2 Lao dong), swallows every later Dieu into one
  paragraph -- always parse with lxml.
* Content of a Dieu is everything between its pDieu and the next pDieu /
  pChuong, apart from pGhiChu (source citation) and pChiDan (cross
  references). Besides classless <p> this includes tables, Word-pasted
  `MsoNormal` paragraphs, divs and lists.
* Word-pasted content can also wrap later Dieu in <div>s or close
  div._content early, so the reader walks blocks in document order
  (_content_blocks) instead of trusting the DOM nesting.
* Headings use one class, 'pChuong', for four levels: Phan > Chuong > Muc >
  Tieu muc. Each heading is a label line carrying an <a name=MAPC> anchor
  ("Chuong I") followed by an anchor-less title line ("NHUNG QUY DINH CHUNG").
  Every level is optional (7 de muc have Dieu directly under the de muc).
* A pChiDan right after a heading belongs to that heading, not to the
  preceding Dieu.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from labor_rag.config import BOPHAPDIEN_DIR

# Checked in order: "Tiểu mục" must win over "Mục".
HEADING_LEVELS = [
    ("phan", re.compile(r"^Phần\b", re.IGNORECASE)),
    ("tieu_muc", re.compile(r"^Tiểu\s+mục\b", re.IGNORECASE)),
    ("chuong", re.compile(r"^Chương\b", re.IGNORECASE)),
    ("muc", re.compile(r"^Mục\b", re.IGNORECASE)),
]
LEVEL_RANK = {"phan": 0, "chuong": 1, "muc": 2, "tieu_muc": 3}
DIEU_RE = re.compile(r"^Điều\s+(\S+?)\.?(?:\s+(.*))?$", re.IGNORECASE)
CHIDAN_LINK_RE = re.compile(r"ViewNoiDungPhapDien\('([^']+)'\)")
DE_MUC_HEADER_RE = re.compile(r"Đề mục\s+([\d.]+)")
STRUCTURAL_CLASSES = {"pChuong", "pDieu", "pGhiChu", "pNoiDung", "pChiDan"}


def _classes(el: Tag) -> list[str]:
    return el.get("class") or []


def _structural_class(el: Tag) -> str | None:
    return next((c for c in _classes(el) if c in STRUCTURAL_CLASSES), None)


def _anchor_mapc(el: Tag) -> str | None:
    a = el.find("a", attrs={"name": True})
    return a["name"] if a else None


_STRAY_SPACE_BEFORE_PUNCT = re.compile(r"(?<=[0-9a-zđA-ZĐ])\s+([.)])")


def _normalize_text(text: str) -> str:
    """Collapse whitespace and fix 'N .' / 'a )' artifacts from inline tags
    like `4<i>. Phôi </i>là...` splitting a number from its punctuation."""
    text = re.sub(r"\s+", " ", text).strip()
    return _STRAY_SPACE_BEFORE_PUNCT.sub(r"\1", text)


def _element_paragraphs(el: Tag) -> list[str]:
    """Text lines of one content element; tables become 'cell | cell' rows."""
    if el.name == "table":
        rows = []
        for tr in el.find_all("tr"):
            cells = [_normalize_text(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            row = " | ".join(cell for cell in cells if cell)
            if row:
                rows.append(row)
        return rows
    block_children = [c for c in el.children if isinstance(c, Tag) and c.name in {"p", "div", "table", "ul", "ol"}]
    if el.name in {"div", "ul", "ol"} and block_children:
        lines: list[str] = []
        for child in block_children:
            lines.extend(_element_paragraphs(child))
        return lines
    text = _normalize_text(el.get_text(" ", strip=True))
    return [text] if text else []


def _iter_blocks(nodes):
    """Flatten the DOM into document-order blocks: structural <p> elements,
    and content elements that contain no structural descendants. Wrappers
    that do contain structural elements (Word-pasted <div>s around later
    Dieu) are descended into, so DOM nesting never hides a Dieu."""
    for el in nodes:
        if not isinstance(el, Tag) or el.name in {"script", "style"}:
            continue
        if _structural_class(el) in {"pChuong", "pDieu", "pGhiChu", "pChiDan"}:
            yield el
        elif el.find(class_=lambda c: c in STRUCTURAL_CLASSES) is not None:
            if _structural_class(el) == "pNoiDung":
                yield el  # marker; its nested content follows
            yield from _iter_blocks(el.children)
        else:
            yield el


def _content_blocks(soup: BeautifulSoup):
    """Blocks of div._content plus everything after it. A stray </div> in
    Word-pasted content closes _content early in 16 files, leaving later
    Dieu as siblings of _content (verified: nothing else follows _content in
    well-formed files)."""
    content = soup.find("div", class_="_content")
    if content is None:
        return
    yield from _iter_blocks(content.children)
    node = content
    while node is not None and node.name not in {"body", "html", "[document]"}:
        yield from _iter_blocks(node.next_siblings)
        node = node.parent


def _parse_references(el: Tag) -> list[dict]:
    references = []
    for a in el.find_all("a", onclick=True):
        ref_m = CHIDAN_LINK_RE.search(a.get("onclick", ""))
        if ref_m:
            references.append(
                {
                    "target_mapc": ref_m.group(1),
                    "display_text": _normalize_text(a.get_text(" ", strip=True)),
                }
            )
    return references


def split_dieu_heading(ten: str) -> tuple[str | None, str]:
    """'Điều 20.5.LQ.1. Phạm vi điều chỉnh' -> ('20.5.LQ.1', 'Phạm vi điều chỉnh')."""
    m = DIEU_RE.match(ten)
    if not m:
        return None, ten
    return m.group(1).rstrip("."), (m.group(2) or "").strip()


def parse_demuc_nodes(html_path: Path) -> dict:
    """Parse a de muc into a generic tree.

    Returns {"de_muc_id", "de_muc_so", "children": [...]} where each child is
    either a heading {"kind": phan|chuong|muc|tieu_muc, "so_hieu", "ten",
    "mapc", "references", "children"} or a Dieu {"kind": "dieu", "mapc",
    "ten", "so_hieu", "tieu_de", "citation", "paragraphs", "references"}.
    """
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")

    header = soup.find("h3")
    m = DE_MUC_HEADER_RE.search(header.get_text(" ", strip=True)) if header else None
    root: dict = {"de_muc_id": html_path.stem, "de_muc_so": m.group(1) if m else None, "children": []}

    stack: list[dict] = []  # open headings, outermost first
    current_heading: dict | None = None  # heading whose title line may follow
    current_dieu: dict | None = None

    def attach(node: dict) -> None:
        (stack[-1]["children"] if stack else root["children"]).append(node)

    for el in _content_blocks(soup):
        cls = _structural_class(el)

        if cls == "pChuong":
            text = _normalize_text(el.get_text(" ", strip=True))
            mapc = _anchor_mapc(el)
            if mapc is None and current_heading is not None:
                # Anchor-less line = title of the heading just opened.
                current_heading["ten"] = f"{current_heading['ten']} {text}".strip()
                continue
            kind = next((k for k, regex in HEADING_LEVELS if regex.match(text)), "chuong")
            while stack and LEVEL_RANK[stack[-1]["kind"]] >= LEVEL_RANK[kind]:
                stack.pop()
            node = {"kind": kind, "so_hieu": text, "ten": "", "mapc": mapc, "references": [], "children": []}
            attach(node)
            stack.append(node)
            current_heading, current_dieu = node, None
            continue

        if cls == "pDieu":
            ten = _normalize_text(el.get_text(" ", strip=True))
            so_hieu, tieu_de = split_dieu_heading(ten)
            current_dieu = {
                "kind": "dieu",
                "mapc": _anchor_mapc(el),
                "ten": ten,
                "so_hieu": so_hieu,
                "tieu_de": tieu_de,
                "citation": None,
                "paragraphs": [],
                "references": [],
            }
            attach(current_dieu)
            current_heading = None
            continue

        if cls == "pChiDan":
            owner = current_dieu if current_dieu is not None else current_heading
            if owner is not None:
                owner["references"].extend(_parse_references(el))
            continue

        if current_dieu is None:
            continue  # stray element outside any Dieu

        if cls == "pGhiChu":
            text = _normalize_text(el.get_text(" ", strip=True))
            if text:
                current_dieu["citation"] = f"{current_dieu['citation']} {text}" if current_dieu["citation"] else text
            continue

        # pNoiDung (usually an empty marker under lxml) and every unclassed /
        # Mso* / table element after it are the Dieu's content.
        current_dieu["paragraphs"].extend(_element_paragraphs(el))

    return root


def iter_dieu(node: dict, ancestors: tuple[dict, ...] = ()):
    """Yield (dieu, ancestor_headings) in document order."""
    for child in node["children"]:
        if child["kind"] == "dieu":
            yield child, ancestors
        else:
            yield from iter_dieu(child, ancestors + (child,))


def load_linh_vuc_index() -> dict:
    """{de_muc_id: {"path", "chu_de", "de_muc"}}, paths relative to BOPHAPDIEN_DIR."""
    return json.loads((BOPHAPDIEN_DIR / "linh_vuc_index.json").read_text(encoding="utf-8"))
