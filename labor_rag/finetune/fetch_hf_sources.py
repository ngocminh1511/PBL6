"""Download the Hugging Face retrieval datasets used as extra fine-tune sources.

Each source lands in its own folder, data/finetune/<source>/, keeping the
repository's file layout. Files already on disk are skipped unless --force.

    bkai       YuITC/Vietnamese-Legal-Documents (BKAI legal retrieval, MIT)
    phamson02  phamson02/large-vi-legal-queries (LLM-generated queries, CC BY 4.0)
    alqac      another-symato/VMTEB-ALQAC-retrieval (ALQAC queries + corpus)

TVPL and VLSP are streamed by extract_tvpl_*.py / extract_vlsp_pairs.py, and
ViLegal / Zalo are placed by hand (docs/FINETUNE_DATA.md).

Usage:
    python -m labor_rag.finetune.fetch_hf_sources
    python -m labor_rag.finetune.fetch_hf_sources --sources bkai alqac --force
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from labor_rag.config import ROOT_DIR, finetune_raw_dir

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

HF_SOURCES: dict[str, tuple[str, list[str]]] = {
    "bkai": ("YuITC/Vietnamese-Legal-Documents", ["train.parquet", "test.parquet"]),
    "phamson02": ("phamson02/large-vi-legal-queries", ["large_vi_legal_queries.parquet"]),
    "alqac": (
        "another-symato/VMTEB-ALQAC-retrieval",
        [
            "corpus/train-00000-of-00001.parquet",
            "queries/train-00000-of-00001.parquet",
            "data_ir/train-00000-of-00001.parquet",
        ],
    ),
}


def fetch(source: str, force: bool = False, token: str | None = None) -> list[Path]:
    """Download one source's files into data/finetune/<source>/ and return their paths."""
    from huggingface_hub import hf_hub_download

    repo, files = HF_SOURCES[source]
    out_dir = finetune_raw_dir(source)
    paths = []
    for name in files:
        target = out_dir / name
        if target.exists() and not force:
            print(f"  [{source}] có sẵn: {target.relative_to(ROOT_DIR)}")
        else:
            hf_hub_download(repo, name, repo_type="dataset", local_dir=out_dir, token=token)
            print(f"  [{source}] đã tải: {target.relative_to(ROOT_DIR)}")
        paths.append(target)
    return paths


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sources", nargs="+", choices=sorted(HF_SOURCES), default=sorted(HF_SOURCES))
    parser.add_argument("--force", action="store_true", help="Tải lại cả file đã có")
    args = parser.parse_args()

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or None
    for source in args.sources:
        fetch(source, force=args.force, token=token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
