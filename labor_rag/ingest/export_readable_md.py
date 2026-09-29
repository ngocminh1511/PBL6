"""Export parsed de-muc trees (data/parsed/*.json, from parse_demuc_html.py)
as human-readable Markdown, organized in folders by Chu De (field of law) ->
De Muc (topic), so the data is easy to browse for a demo -- instead of flat
UUID-named HTML files with no grouping.

This reads the ALREADY-PARSED hierarchy (Chuong/Muc/Dieu/Khoan/Diem), so the
Markdown structure is guaranteed identical to what's loaded into Neo4j/Qdrant
-- it's a display format, not a re-parse of the raw HTML.

Usage: python ingest/export_readable_md.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(r"D:\Work\Learn\HK7_2026-2027\PBL6\labor_rag\data")
PARSED_DIR = DATA_DIR / "parsed"
OUT_DIR = DATA_DIR / "readable"

_UNSAFE_FILENAME = re.compile(r'[\\/:*?"<>|]')


def safe_filename(name: str) -> str:
    return _UNSAFE_FILENAME.sub("_", name).strip()


def render_dieu(dieu: dict) -> str:
    lines = [f"#### {dieu['ten']}"]
    if dieu["citation"]:
        lines.append(f"*{dieu['citation']}*")
    lines.append("")
    for khoan in dieu["khoan"]:
        lines.append(khoan["text"])
        for diem in khoan["diem"]:
            lines.append(f"  {diem['text']}")
    if dieu["references"]:
        refs = "; ".join(r["display_text"] for r in dieu["references"])
        lines.append("")
        lines.append(f"> Tham chiếu: {refs}")
    lines.append("")
    return "\n".join(lines)


def render_tree(tree: dict, de_muc_ten: str) -> str:
    parts = [f"# Đề mục {tree['de_muc_so']} - {de_muc_ten}", ""]

    for dieu in tree["top_level_dieu"]:
        parts.append(render_dieu(dieu))

    for chuong in tree["chuong"]:
        parts.append(f"## {chuong['so_hieu']} {chuong['ten']}".strip())
        parts.append("")
        for dieu in chuong["dieu"]:
            parts.append(render_dieu(dieu))
        for muc in chuong["muc"]:
            parts.append(f"### {muc['so_hieu']} {muc['ten']}".strip())
            parts.append("")
            for dieu in muc["dieu"]:
                parts.append(render_dieu(dieu))

    return "\n".join(parts)


def main() -> None:
    chu_de = json.loads((DATA_DIR / "chu_de.json").read_text(encoding="utf-8"))
    de_muc_meta = json.loads((DATA_DIR / "de_muc.json").read_text(encoding="utf-8"))

    n_written = 0
    for path in sorted(PARSED_DIR.glob("*.json")):
        tree = json.loads(path.read_text(encoding="utf-8"))
        de_muc_id = tree["de_muc_id"]
        meta = de_muc_meta.get(de_muc_id, {})
        de_muc_ten = meta.get("Text", de_muc_id)
        chu_de_ten = chu_de.get(meta.get("ChuDe", ""), {}).get("Text", "Khac")

        folder = OUT_DIR / safe_filename(chu_de_ten)
        folder.mkdir(parents=True, exist_ok=True)
        out_path = folder / f"{safe_filename(de_muc_ten)}.md"
        out_path.write_text(render_tree(tree, de_muc_ten), encoding="utf-8")
        print(f"{chu_de_ten}/{de_muc_ten}.md")
        n_written += 1

    print(f"\nDa xuat {n_written} file Markdown -> {OUT_DIR}")


if __name__ == "__main__":
    main()
