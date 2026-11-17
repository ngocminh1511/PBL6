"""Auto-chain embedding: embeds both TH2 (lao_dong_v5) and TH1 (lao_dong_v6)
into Qdrant (local or Cloud) using either local CPU/GPU or Modal Cloud GPU,
then runs a side-by-side comparison test.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DEFAULT_QDRANT_KEY = os.getenv("QDRANT_API_KEY") or None
DEFAULT_BACKEND = os.getenv("EMBEDDING_BACKEND", "local")

TH2_COLLECTION = "legal_ld_v5_bge"
TH1_COLLECTION = "legal_ld_v6_bge"
TH2_CHUNKS = "data/processed/lao_dong_v5/chunks.jsonl"
TH1_CHUNKS = "data/processed/lao_dong_v6/chunks.jsonl"


def get_collection_points(qdrant_url: str, collection: str, api_key: str | None = None) -> int:
    try:
        url = f"{qdrant_url}/collections/{collection}"
        headers = {}
        if api_key:
            headers["api-key"] = api_key
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("result", {}).get("points_count", 0)
    except Exception:
        return 0


def run_embed(chunks_path: str, collection: str, backend: str, qdrant_url: str) -> bool:
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "labor_rag.ingest.embed_and_index",
        "--chunks",
        chunks_path,
        "--collection",
        collection,
        "--backend",
        backend,
        "--qdrant-url",
        qdrant_url,
    ]
    print(f"\n>>> Running: {' '.join(cmd)}", flush=True)
    res = subprocess.run(cmd)
    return res.returncode == 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["local", "modal"], default=DEFAULT_BACKEND)
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    args = parser.parse_args()

    print("=" * 65, flush=True)
    print(" PIPELINE EMBEDDING TỰ ĐỘNG CHO CẢ 2 TRƯỜNG HỢP (TH1 & TH2)", flush=True)
    print("=" * 65, flush=True)
    print(f"Backend: {args.backend.upper()}", flush=True)
    print(f"Qdrant Destination: {args.qdrant_url}", flush=True)

    # 1. Embed TH2
    print(f"\n[BƯỚC 1/3] Bắt đầu Embedding TH2 ({TH2_CHUNKS} -> {TH2_COLLECTION})...", flush=True)
    ok2 = run_embed(TH2_CHUNKS, TH2_COLLECTION, args.backend, args.qdrant_url)
    if not ok2:
        print("Lỗi khi chạy embedding cho TH2. Dừng pipeline.", flush=True)
        return 1

    # 2. Embed TH1
    print(f"\n[BƯỚC 2/3] Bắt đầu Embedding TH1 ({TH1_CHUNKS} -> {TH1_COLLECTION})...", flush=True)
    ok1 = run_embed(TH1_CHUNKS, TH1_COLLECTION, args.backend, args.qdrant_url)
    if not ok1:
        print("Lỗi khi chạy embedding cho TH1. Dừng pipeline.", flush=True)
        return 1

    # 3. Test & Compare
    print("\n[BƯỚC 3/3] Kiểm tra số lượng vector và chạy thử nghiệm truy vấn so sánh...", flush=True)
    p2 = get_collection_points(args.qdrant_url, TH2_COLLECTION, DEFAULT_QDRANT_KEY)
    p1 = get_collection_points(args.qdrant_url, TH1_COLLECTION, DEFAULT_QDRANT_KEY)
    print(f"  TH2 ({TH2_COLLECTION}): {p2} points", flush=True)
    print(f"  TH1 ({TH1_COLLECTION}): {p1} points", flush=True)

    print("\n>>> Thử nghiệm truy vấn so sánh song song giữa TH1 và TH2...", flush=True)
    test_cmd = [
        sys.executable,
        "-m",
        "labor_rag.retrieval.vector_search",
        "Người lao động thử việc có được trả lương không?",
        "--compare",
        "--qdrant-url",
        args.qdrant_url,
    ]
    subprocess.run(test_cmd)

    print("\n" + "=" * 65, flush=True)
    print(" HOÀN TẤT TOÀN BỘ PIPELINE CHO CẢ 2 TRƯỜNG HỢP THÀNH CÔNG!", flush=True)
    print("=" * 65, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
