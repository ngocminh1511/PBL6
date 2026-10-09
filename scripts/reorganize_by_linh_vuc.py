"""Reorganize the flat, UUID-named data/raw/bophapdien/demuc/*.html files into
folders grouped by linh vuc (legal field / Chu De), using human-readable
slugs, so the data can be browsed by field instead of opaque UUIDs.

Pure filesystem move + rename -- no HTML content is touched or reparsed.
Metadata (Chu De / De Muc names) comes from data/interim/chu_de.json and
data/interim/de_muc.json (already extracted from data/raw/bophapdien/jsonData.js
by labor_rag/ingest/parse_jsondata.py).

Output:
  data/raw/bophapdien/linh_vuc/<chu_de_slug>/<de_muc_slug>.html
  data/raw/bophapdien/linh_vuc_index.json   -- {de_muc_id: {path, chu_de, de_muc}}
  demuc/ is removed once emptied.

Idempotent: safe to re-run -- files already moved (per the index) are skipped
instead of erroring on a missing source.

Usage: python scripts/reorganize_by_linh_vuc.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT = PROJECT_DIR / "data" / "raw" / "bophapdien"
DEMUC_DIR = ROOT / "demuc"
LINH_VUC_DIR = ROOT / "linh_vuc"
INDEX_PATH = ROOT / "linh_vuc_index.json"

INTERIM_DIR = PROJECT_DIR / "data" / "interim"
CHU_DE_PATH = INTERIM_DIR / "chu_de.json"
DE_MUC_PATH = INTERIM_DIR / "de_muc.json"


def slugify(text: str) -> str:
    """Vietnamese text -> ASCII, underscore-separated slug (e.g. 'Lao động'
    -> 'lao_dong'). Same technique as crawl_data's slugify(), just joined
    with '_' instead of '-' to match the layout the user asked for."""
    text = text.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = re.sub(r"[^\w\s-]", "", ascii_only).strip().lower()
    slug = re.sub(r"[\s_-]+", "_", ascii_only)
    return slug or "chua_phan_loai"


def unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    n = 2
    while True:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def main() -> None:
    chu_de = json.loads(CHU_DE_PATH.read_text(encoding="utf-8"))
    de_muc = json.loads(DE_MUC_PATH.read_text(encoding="utf-8"))

    index: dict[str, dict] = {}
    if INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    n_moved = 0
    n_already_done = 0
    n_missing_src = 0
    n_unmapped = 0
    by_chu_de: dict[str, int] = {}

    for de_muc_id, meta in de_muc.items():
        de_muc_ten = meta.get("Text", de_muc_id)
        chu_de_id = meta.get("ChuDe", "")
        chu_de_ten = chu_de.get(chu_de_id, {}).get("Text", "chua_phan_loai")

        src = DEMUC_DIR / f"{de_muc_id}.html"

        if de_muc_id in index:
            n_already_done += 1
            continue

        if not src.exists():
            n_missing_src += 1
            continue

        dest_dir = LINH_VUC_DIR / slugify(chu_de_ten)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = unique_path(dest_dir / f"{slugify(de_muc_ten)}.html")

        shutil.move(str(src), str(dest))
        index[de_muc_id] = {
            "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
            "chu_de": chu_de_ten,
            "de_muc": de_muc_ten,
        }
        by_chu_de[chu_de_ten] = by_chu_de.get(chu_de_ten, 0) + 1
        n_moved += 1

    # Any leftover HTML files in demuc/ not covered by de_muc.json at all.
    if DEMUC_DIR.exists():
        for leftover in sorted(DEMUC_DIR.glob("*.html")):
            de_muc_id = leftover.stem
            if de_muc_id in index:
                continue
            dest_dir = LINH_VUC_DIR / "chua_phan_loai"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = unique_path(dest_dir / leftover.name)
            shutil.move(str(leftover), str(dest))
            index[de_muc_id] = {
                "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
                "chu_de": None,
                "de_muc": None,
            }
            n_unmapped += 1
            print(f"  CANH BAO: {de_muc_id}.html khong co trong de_muc.json -> {dest}")

    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    if DEMUC_DIR.exists():
        try:
            os.rmdir(DEMUC_DIR)
            print(f"Da xoa thu muc rong: {DEMUC_DIR}")
        except OSError:
            remaining = list(DEMUC_DIR.iterdir())
            print(f"demuc/ chua rong, con {len(remaining)} muc, khong xoa.")

    print(f"\nDa move: {n_moved} file vao {len(by_chu_de)} thu muc linh vuc")
    for chu_de_ten, n in sorted(by_chu_de.items()):
        print(f"  {slugify(chu_de_ten)}/  ({n} de muc)")
    if n_already_done:
        print(f"Da bo qua (da move tu truoc, theo index): {n_already_done}")
    if n_missing_src:
        print(f"CANH BAO: {n_missing_src} de_muc trong de_muc.json khong co file HTML tren dia (chua pho bien hoa)")
    if n_unmapped:
        print(f"CANH BAO: {n_unmapped} file HTML khong khop de_muc.json, da chuyen vao linh_vuc/chua_phan_loai/")
    print(f"Index: {INDEX_PATH}")


if __name__ == "__main__":
    main()
