"""Parse data/raw/bophapdien/jsonData.js into plain JSON indexes.

jsonData.js is not valid JSON on its own -- it is three JS assignments
(`jdChuDe = [...]`, `jdDeMuc = [...]`, `jdAllTree = [...]`) whose right-hand
sides are each a well-formed JSON array. We locate each assignment and use
json.JSONDecoder.raw_decode to parse just the array literal that follows,
ignoring the surrounding JS.

Usage: python -m labor_rag.ingest.parse_jsondata

Outputs (under data/interim/):
  chu_de.json        -- {ChuDeID: {"Text":..., "STT":...}}
  de_muc.json         -- {DeMucID: {"Text":..., "STT":..., "ChuDe":...}}
  mapc_index.json     -- {MAPC: {"TEN":..., "ChuDeID":..., "DeMucID":..., "ChiMuc":..., "ID":...}}
                          global index covering the ENTIRE Bo Phap Dien, used to
                          resolve cross-de-muc REFERS_TO targets (pChiDan links).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from labor_rag.config import BOPHAPDIEN_DIR, INTERIM_DIR

sys.stdout.reconfigure(encoding="utf-8")

SOURCE = BOPHAPDIEN_DIR / "jsonData.js"
OUT_DIR = INTERIM_DIR

VARS = ("jdChuDe", "jdDeMuc", "jdAllTree")


def load_jsondata(path: Path) -> dict[str, list]:
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    result: dict[str, list] = {}
    for name in VARS:
        marker = f"{name} ="
        idx = text.find(marker)
        if idx == -1:
            marker = f"{name}="
            idx = text.find(marker)
        if idx == -1:
            raise ValueError(f"Could not find assignment for {name!r} in {path}")
        start = idx + len(marker)
        # skip whitespace
        while text[start].isspace():
            start += 1
        obj, _end = decoder.raw_decode(text, start)
        result[name] = obj
    return result


def build_indexes(data: dict[str, list]) -> tuple[dict, dict, dict]:
    chu_de = {item["Value"]: {"Text": item["Text"], "STT": item["STT"]} for item in data["jdChuDe"]}

    de_muc = {
        item["Value"]: {"Text": item["Text"], "STT": item["STT"], "ChuDe": item["ChuDe"]}
        for item in data["jdDeMuc"]
    }

    mapc_index = {}
    for item in data["jdAllTree"]:
        mapc_index[item["MAPC"]] = {
            "TEN": item["TEN"],
            "ChuDeID": item["ChuDeID"],
            "DeMucID": item["DeMucID"],
            "ChiMuc": item.get("ChiMuc"),
            "ID": item.get("ID"),
        }

    return chu_de, de_muc, mapc_index


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Reading {SOURCE} ...")
    data = load_jsondata(SOURCE)
    print(f"  jdChuDe:   {len(data['jdChuDe'])} entries")
    print(f"  jdDeMuc:   {len(data['jdDeMuc'])} entries")
    print(f"  jdAllTree: {len(data['jdAllTree'])} entries")

    chu_de, de_muc, mapc_index = build_indexes(data)

    (OUT_DIR / "chu_de.json").write_text(
        json.dumps(chu_de, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT_DIR / "de_muc.json").write_text(
        json.dumps(de_muc, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (OUT_DIR / "mapc_index.json").write_text(
        json.dumps(mapc_index, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote chu_de.json, de_muc.json, mapc_index.json to {OUT_DIR}")


if __name__ == "__main__":
    main()
