"""Xem nhanh cấu trúc các tập VLSP 2025 LegalSLM (không tải toàn bộ).

Với mỗi tập: stream N mẫu đầu, in tên cột + số split + một mẫu rút gọn,
đồng thời ghi N mẫu vào data/interim/vlsp_samples/<tên>.jsonl để xem lại.

Cần: đã bấm đồng ý điều khoản trên từng trang dataset (gated=auto) và có token:
    huggingface-cli login        (hoặc đặt HF_TOKEN trong .env / biến môi trường)

Chạy từ thư mục gốc repo:
    python scripts/inspect_vlsp.py
    python scripts/inspect_vlsp.py --only legal-corpus qa-non-reasoning --n 200
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "interim" / "vlsp_samples"
OWNER = "longstnguyen"
DATASETS = [
    "legal-corpus",
    "qa-non-reasoning",
    "qa-reasoning",
    "legal-document-detection",
    "legal-document-revision",
    "mcq-non-reasoning",
    "nli-non-reasoning",
]


def shorten(value, limit: int = 300):
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [+{len(value) - limit} ký tự]"
    if isinstance(value, list):
        return [shorten(v, limit) for v in value[:3]] + (["..."] if len(value) > 3 else [])
    if isinstance(value, dict):
        return {k: shorten(v, limit) for k, v in value.items()}
    return value


def inspect(name: str, n: int, token: str | None) -> None:
    from datasets import get_dataset_split_names, load_dataset

    repo = f"{OWNER}/vlsp2025-{name}"
    print(f"\n{'=' * 78}\n{repo}")
    try:
        splits = get_dataset_split_names(repo, token=token)
    except Exception as exc:  # noqa: BLE001 - in lỗi gốc cho người dùng đọc
        print(f"  KHÔNG TRUY CẬP ĐƯỢC: {type(exc).__name__}: {str(exc)[:200]}")
        print("  -> kiểm tra: đã login? đã bấm 'Agree' ở trang dataset chưa?")
        return
    print(f"  splits: {splits}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    split = "train" if "train" in splits else splits[0]
    ds = load_dataset(repo, split=split, streaming=True, token=token)
    rows = []
    for row in ds:
        rows.append(row)
        if len(rows) >= n:
            break
    if not rows:
        print("  (rỗng)")
        return

    print(f"  split dùng để xem: {split} | cột: {list(rows[0].keys())}")
    print("  mẫu đầu tiên (rút gọn):")
    print(json.dumps(shorten(rows[0]), ensure_ascii=False, indent=2))

    out = OUT_DIR / f"{name}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    print(f"  đã ghi {len(rows)} mẫu -> {out.relative_to(ROOT)}")


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=100, help="số mẫu stream cho mỗi tập")
    parser.add_argument("--only", nargs="*", choices=DATASETS, help="chỉ xem một số tập")
    args = parser.parse_args()

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or True
    for name in args.only or DATASETS:
        inspect(name, args.n, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
