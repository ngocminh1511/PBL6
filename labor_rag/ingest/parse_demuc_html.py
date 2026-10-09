"""Parse one data/raw/bophapdien/linh_vuc/<chu_de>/<de_muc>.html file into a hierarchical tree.

Key HTML fact (verified with BeautifulSoup+lxml, which follows the same
auto-close rule real browsers use): the source markup nests <p> inside
<p class='pNoiDung'> (`<p class='pNoiDung'><p>...</p><p>...</p></p>`), which
is invalid HTML. Any spec-compliant parser auto-closes the outer <p> on the
first inner <p>, so after parsing, `pNoiDung` becomes an EMPTY marker
element and its "content" paragraphs become plain classless <p> siblings
that follow it, up to the next classed element (pChiDan / pDieu / pChuong).
The parser below relies on that flattened sibling structure, not on nesting.

Six-level hierarchy present in the data: Van ban (derived from pGhiChu
citation text, not a DOM containment level) -> Chuong -> Muc (optional) ->
Dieu -> Khoan -> Diem. Chuong and Muc share the SAME class 'pChuong' (each
is a pair of <p class='pChuong'> elements: a short label line "Chuong I" /
"Muc 1", followed by an upper-case title line) and are told apart only by
regex on the label text.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from labor_rag.config import BOPHAPDIEN_DIR, PARSED_DIR

sys.stdout.reconfigure(encoding="utf-8")

CHUONG_RE = re.compile(r"^Chương\b", re.IGNORECASE)
MUC_RE = re.compile(r"^Mục\s+\d+", re.IGNORECASE)
KHOAN_RE = re.compile(r"^(\d{1,3})\s*\.\s*")
DIEM_RE = re.compile(r"^([a-zđ]{1,2})\s*\)\s*", re.IGNORECASE)
CHIDAN_LINK_RE = re.compile(r"ViewNoiDungPhapDien\('([^']+)'\)")
DE_MUC_HEADER_RE = re.compile(r"Đề mục\s+([\d.]+)")


def _classes(el: Tag) -> list[str]:
    return el.get("class") or []


def _anchor_mapc(el: Tag) -> str | None:
    a = el.find("a", attrs={"name": True})
    return a["name"] if a else None


_STRAY_SPACE_BEFORE_PUNCT = re.compile(r"(?<=[0-9a-zđA-ZĐ])\s+([.)])")


def _normalize_text(text: str) -> str:
    """Collapse whitespace and fix 'N .' / 'a )' artifacts from inline tags
    like `4<i>. Phôi </i>là...` splitting a number from its punctuation."""
    text = re.sub(r"\s+", " ", text).strip()
    return _STRAY_SPACE_BEFORE_PUNCT.sub(r"\1", text)


def split_khoan_diem(paragraphs: list[str]) -> list[dict]:
    """Group a flat list of content paragraphs into Khoan -> Diem."""
    khoan_list: list[dict] = []
    current_khoan: dict | None = None
    for text in paragraphs:
        m_khoan = KHOAN_RE.match(text)
        if m_khoan:
            current_khoan = {"so": m_khoan.group(1), "text": text, "diem": []}
            khoan_list.append(current_khoan)
            continue
        m_diem = DIEM_RE.match(text)
        if m_diem and current_khoan is not None:
            current_khoan["diem"].append({"so": m_diem.group(1), "text": text})
            continue
        if current_khoan is not None:
            # Wrapped continuation line of the current Khoan/Diem (no new marker).
            current_khoan["text"] += " " + text
        else:
            # Dieu has no Khoan numbering at all -- plain paragraph(s).
            khoan_list.append({"so": None, "text": text, "diem": []})
    return khoan_list


def parse_demuc(html_path: Path) -> dict:
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    header_text = soup.find("h3").get_text(" ", strip=True) if soup.find("h3") else ""
    m = DE_MUC_HEADER_RE.search(header_text)
    de_muc_so = m.group(1) if m else None

    content = soup.find("div", class_="_content")
    children = [c for c in content.children if isinstance(c, Tag)] if content else []

    chuong_list: list[dict] = []
    current_chuong: dict | None = None
    current_muc: dict | None = None
    top_level_dieu: list[dict] = []  # Dieu appearing before any Chuong (rare/none expected)

    n = len(children)
    i = 0
    while i < n:
        el = children[i]
        classes = _classes(el)

        if "pChuong" in classes:
            label_text = _normalize_text(el.get_text(" ", strip=True))
            mapc = _anchor_mapc(el)
            i += 1
            title_text = ""
            if i < n and "pChuong" in _classes(children[i]):
                title_text = _normalize_text(children[i].get_text(" ", strip=True))
                i += 1
            node = {"so_hieu": label_text, "ten": title_text, "mapc": mapc, "muc": [], "dieu": []}
            if MUC_RE.match(label_text):
                current_muc = node
                if current_chuong is not None:
                    current_chuong["muc"].append(node)
            else:
                current_chuong = node
                current_muc = None
                chuong_list.append(node)
            continue

        if "pDieu" in classes:
            mapc = _anchor_mapc(el)
            ten = _normalize_text(el.get_text(" ", strip=True))
            i += 1

            citation = None
            if i < n and "pGhiChu" in _classes(children[i]):
                citation = _normalize_text(children[i].get_text(" ", strip=True))
                i += 1

            content_paragraphs: list[str] = []
            if i < n and "pNoiDung" in _classes(children[i]):
                i += 1  # skip the now-empty pNoiDung marker
                while i < n and not _classes(children[i]):
                    text = _normalize_text(children[i].get_text(" ", strip=True))
                    if text:
                        content_paragraphs.append(text)
                    i += 1

            references: list[dict] = []
            if i < n and "pChiDan" in _classes(children[i]):
                for a in children[i].find_all("a", onclick=True):
                    ref_m = CHIDAN_LINK_RE.search(a.get("onclick", ""))
                    if ref_m:
                        references.append(
                            {
                                "target_mapc": ref_m.group(1),
                                "display_text": _normalize_text(a.get_text(strip=True)),
                            }
                        )
                i += 1

            dieu_node = {
                "mapc": mapc,
                "ten": ten,
                "citation": citation,
                "khoan": split_khoan_diem(content_paragraphs),
                "references": references,
            }

            if current_muc is not None:
                current_muc["dieu"].append(dieu_node)
            elif current_chuong is not None:
                current_chuong["dieu"].append(dieu_node)
            else:
                top_level_dieu.append(dieu_node)
            continue

        # Unrecognized stray element at top level -- skip.
        i += 1

    return {
        "de_muc_id": html_path.stem,
        "de_muc_so": de_muc_so,
        "chuong": chuong_list,
        "top_level_dieu": top_level_dieu,
    }


def _count_dieu(tree: dict) -> int:
    total = len(tree["top_level_dieu"])
    for ch in tree["chuong"]:
        total += len(ch["dieu"])
        for mc in ch["muc"]:
            total += len(mc["dieu"])
    return total


def main() -> None:
    bo_phap_dien_dir = BOPHAPDIEN_DIR
    out_dir = PARSED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # demuc/<id>.html files were reorganized into linh_vuc/<chu_de>/<de_muc>.html
    # by scripts/reorganize_by_linh_vuc.py; this index maps id -> current relative path.
    index_path = bo_phap_dien_dir / "linh_vuc_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))

    ids = sys.argv[1:]
    if not ids:
        print("Usage: python -m labor_rag.ingest.parse_demuc_html <de_muc_id> [<de_muc_id> ...]")
        raise SystemExit(1)

    for de_muc_id in ids:
        entry = index.get(de_muc_id)
        if entry is None:
            raise SystemExit(
                f"{de_muc_id}: khong tim thay trong {index_path} "
                "(chay reorganize_by_linh_vuc.py truoc, hoac kiem tra lai id)."
            )
        html_path = bo_phap_dien_dir / entry["path"]
        tree = parse_demuc(html_path)
        # parse_demuc() derives de_muc_id from the HTML filename stem, which
        # used to be the UUID itself (flat demuc/<uuid>.html layout). Files
        # now live under linh_vuc/<chu_de>/<slug>.html, so the stem is a slug
        # -- restore the real UUID here so downstream (build_chunks.py,
        # build_kg.py) can still key into de_muc.json/mapc_index.json by id.
        tree["de_muc_id"] = de_muc_id
        n_dieu = _count_dieu(tree)
        if n_dieu == 0:
            # De muc chua co noi dung (vd. 20.1): khong ghi file JSON rong.
            print(f"{de_muc_id}: khong co Dieu nao, bo qua.")
            continue
        n_chuong = len(tree["chuong"])
        n_muc = sum(len(ch["muc"]) for ch in tree["chuong"])
        n_refs = sum(
            len(d["references"])
            for ch in tree["chuong"]
            for d in (ch["dieu"] + [x for mc in ch["muc"] for x in mc["dieu"]])
        )
        out_path = out_dir / f"{de_muc_id}.json"
        out_path.write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
        print(
            f"{de_muc_id}: {n_chuong} Chuong, {n_muc} Muc, {n_dieu} Dieu, "
            f"{n_refs} cross-references -> {out_path}"
        )


if __name__ == "__main__":
    main()
