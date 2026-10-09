"""Flatten parsed de-muc trees (ingest/parse_demuc_html.py output) into flat
retrieval chunks -- one chunk per Dieu, prefixed with a breadcrumb so the
embedding carries hierarchy context (Chuong/Muc/citation) even though the
chunk itself is just the Dieu's own text.

Usage: python -m labor_rag.ingest.build_chunks
"""
from __future__ import annotations

import json
import sys

from labor_rag.config import INTERIM_DIR, LEGACY_DIR, PARSED_DIR

sys.stdout.reconfigure(encoding="utf-8")

DE_MUC_META = INTERIM_DIR / "de_muc.json"
OUT_PATH = LEGACY_DIR / "chunks.jsonl"


def _dieu_body(dieu: dict) -> str:
    lines = []
    for khoan in dieu["khoan"]:
        lines.append(khoan["text"])
        for diem in khoan["diem"]:
            lines.append("  " + diem["text"])
    return "\n".join(lines)


def build_chunks_for_tree(tree: dict, de_muc_ten: str) -> list[dict]:
    chunks = []

    def emit(dieu: dict, chuong: dict | None, muc: dict | None):
        breadcrumb_parts = [f"Đề mục {tree['de_muc_so']} - {de_muc_ten}"]
        if chuong:
            breadcrumb_parts.append(f"{chuong['so_hieu']} {chuong['ten']}".strip())
        if muc:
            breadcrumb_parts.append(f"{muc['so_hieu']} {muc['ten']}".strip())
        breadcrumb = " > ".join(breadcrumb_parts)

        body = _dieu_body(dieu)
        text = f"{breadcrumb}\n{dieu['ten']}\n{dieu['citation'] or ''}\n{body}".strip()

        chunks.append(
            {
                "chunk_id": dieu["mapc"],
                "mapc": dieu["mapc"],
                "de_muc_id": tree["de_muc_id"],
                "de_muc_so": tree["de_muc_so"],
                "chuong": chuong["so_hieu"] if chuong else None,
                "muc": muc["so_hieu"] if muc else None,
                "ten": dieu["ten"],
                "citation": dieu["citation"],
                "breadcrumb": breadcrumb,
                "text": text,
                "n_khoan": len(dieu["khoan"]),
                "n_refs": len(dieu["references"]),
            }
        )

    for dieu in tree["top_level_dieu"]:
        emit(dieu, None, None)
    for chuong in tree["chuong"]:
        for dieu in chuong["dieu"]:
            emit(dieu, chuong, None)
        for muc in chuong["muc"]:
            for dieu in muc["dieu"]:
                emit(dieu, chuong, muc)

    return chunks


def main() -> None:
    de_muc_meta = json.loads(DE_MUC_META.read_text(encoding="utf-8"))

    all_chunks: list[dict] = []
    for path in sorted(PARSED_DIR.glob("*.json")):
        tree = json.loads(path.read_text(encoding="utf-8"))
        de_muc_id = tree["de_muc_id"]
        de_muc_ten = de_muc_meta.get(de_muc_id, {}).get("Text", "")
        chunks = build_chunks_for_tree(tree, de_muc_ten)
        all_chunks.extend(chunks)
        print(f"{de_muc_id} ({de_muc_ten}): {len(chunks)} chunks")

    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"Total: {len(all_chunks)} chunks -> {OUT_PATH}")


if __name__ == "__main__":
    main()
