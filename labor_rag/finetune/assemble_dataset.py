"""Stage 4: Dataset Assembly for BGE-M3 Fine-tuning.

Combines synthetic queries, KG positive pairs, and mined hard negatives into:
- train.jsonl: Training samples with anchor, positive, and hard negatives
- val.jsonl: Validation benchmark questions
- dataset_stats.json: Dataset summary statistics

Output train.jsonl schema:
    {
        "id": "...",
        "anchor": "text",
        "positive": "text",
        "negatives": ["text_neg_1", ...],
        "type": "synthetic_query | kg_pair",
        "metadata": {...}
    }

Output val.jsonl schema:
    {
        "id": "q01",
        "question": "...",
        "relevance": {"mapc": grade, ...},
        "category": "..."
    }

Usage:
    python -m labor_rag.finetune.assemble_dataset
    python -m labor_rag.finetune.assemble_dataset --validate-only
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from labor_rag.config import EVALUATION_DIR, FINETUNE_DIR, LAO_DONG_DIR

DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_SYNTHETIC = FINETUNE_DIR / "synthetic_queries.jsonl"
DEFAULT_KG_PAIRS = FINETUNE_DIR / "kg_positive_pairs.jsonl"
DEFAULT_HARD_NEGS = FINETUNE_DIR / "hard_negatives.jsonl"
DEFAULT_BENCHMARK = EVALUATION_DIR / "benchmark_questions.jsonl"

DEFAULT_TRAIN = FINETUNE_DIR / "train.jsonl"
DEFAULT_VAL = FINETUNE_DIR / "val.jsonl"
DEFAULT_STATS = FINETUNE_DIR / "dataset_stats.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def assemble_dataset(
    chunks_path: Path = DEFAULT_CHUNKS,
    synthetic_path: Path = DEFAULT_SYNTHETIC,
    kg_pairs_path: Path = DEFAULT_KG_PAIRS,
    hard_negs_path: Path = DEFAULT_HARD_NEGS,
    benchmark_path: Path = DEFAULT_BENCHMARK,
    train_path: Path = DEFAULT_TRAIN,
    val_path: Path = DEFAULT_VAL,
    stats_path: Path = DEFAULT_STATS,
) -> dict[str, Any]:
    print("Loading chunks...")
    chunks = load_jsonl(chunks_path)
    chunks_by_id = {c["chunk_id"]: c for c in chunks}
    print(f"Loaded {len(chunks_by_id)} chunks.")

    # 1. Validation set from benchmark_questions.jsonl
    print(f"Loading benchmark questions from {benchmark_path}...")
    bench_records = load_jsonl(benchmark_path)
    val_path.parent.mkdir(parents=True, exist_ok=True)
    with val_path.open("w", encoding="utf-8") as f:
        for b in bench_records:
            val_record = {
                "id": b["id"],
                "question": b["question"],
                "relevance": b.get("relevance", {}),
                "category": b.get("category", ""),
            }
            f.write(json.dumps(val_record, ensure_ascii=False) + "\n")
    print(f"Saved {len(bench_records)} validation questions to {val_path}")

    # 2. Hard negatives map: query_id -> list of negative chunk_ids
    hard_negs_map: dict[str, list[dict[str, Any]]] = {}
    if hard_negs_path.exists():
        print(f"Loading hard negatives from {hard_negs_path}...")
        for row in load_jsonl(hard_negs_path):
            hard_negs_map[row["query_id"]] = row.get("hard_negatives", [])
        print(f"Loaded hard negatives for {len(hard_negs_map)} queries.")

    # 3. Synthetic queries
    synthetic_samples: list[dict[str, Any]] = []
    if synthetic_path.exists():
        print(f"Loading synthetic queries from {synthetic_path}...")
        queries = load_jsonl(synthetic_path)
        for q in queries:
            chunk_id = q["chunk_id"]
            if chunk_id not in chunks_by_id:
                continue
            pos_text = chunks_by_id[chunk_id]["text"]

            neg_texts = []
            if q["query_id"] in hard_negs_map:
                for neg_info in hard_negs_map[q["query_id"]]:
                    neg_cid = neg_info["chunk_id"]
                    if neg_cid in chunks_by_id:
                        neg_texts.append(chunks_by_id[neg_cid]["text"])

            synthetic_samples.append(
                {
                    "id": q["query_id"],
                    "anchor": q["query"],
                    "positive": pos_text,
                    "negatives": neg_texts,
                    "type": "synthetic_query",
                    "metadata": {
                        "chunk_id": chunk_id,
                        "style": q.get("style", "truc_tiep"),
                    },
                }
            )
        print(f"Constructed {len(synthetic_samples)} synthetic query samples.")
    else:
        print(f"[INFO] Synthetic queries file not found at {synthetic_path}; skipping synthetic samples.")

    # 4. KG positive pairs
    kg_samples: list[dict[str, Any]] = []
    if kg_pairs_path.exists():
        print(f"Loading KG pairs from {kg_pairs_path}...")
        kg_pairs = load_jsonl(kg_pairs_path)
        for p in kg_pairs:
            kg_samples.append(
                {
                    "id": p["pair_id"],
                    "anchor": p["anchor"],
                    "positive": p["positive"],
                    "negatives": [],
                    "type": "kg_pair",
                    "metadata": {
                        "relation": p.get("relation", "refers_to"),
                        "anchor_id": p.get("anchor_id", ""),
                        "positive_id": p.get("positive_id", ""),
                    },
                }
            )
        print(f"Constructed {len(kg_samples)} KG positive pair samples.")
    else:
        print(f"[INFO] KG positive pairs not found at {kg_pairs_path}; skipping KG samples.")

    # 5. Assemble and write train.jsonl
    all_train = synthetic_samples + kg_samples
    train_path.parent.mkdir(parents=True, exist_ok=True)
    with train_path.open("w", encoding="utf-8") as f:
        for s in all_train:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Saved {len(all_train)} training samples to {train_path}")

    # 6. Compute and save stats
    stats = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_train_samples": len(all_train),
        "synthetic_query_samples": len(synthetic_samples),
        "kg_pair_samples": len(kg_samples),
        "samples_with_hard_negatives": sum(1 for s in all_train if s["negatives"]),
        "validation_queries": len(bench_records),
        "corpus_chunks_count": len(chunks_by_id),
    }

    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Saved stats to {stats_path}")

    return stats


def validate_dataset(
    train_path: Path = DEFAULT_TRAIN,
    val_path: Path = DEFAULT_VAL,
    stats_path: Path = DEFAULT_STATS,
) -> bool:
    if not train_path.exists():
        print(f"[FAIL] Train path not found: {train_path}")
        return False
    if not val_path.exists():
        print(f"[FAIL] Val path not found: {val_path}")
        return False

    train_data = load_jsonl(train_path)
    val_data = load_jsonl(val_path)

    if not train_data:
        print(f"[FAIL] Train dataset is empty: {train_path}")
        return False
    if not val_data:
        print(f"[FAIL] Validation dataset is empty: {val_path}")
        return False

    # Check required fields
    type_counts = Counter()
    has_negs_count = 0
    for idx, s in enumerate(train_data, 1):
        if not s.get("anchor") or not s.get("positive"):
            print(f"[FAIL] Train sample #{idx} missing anchor or positive text")
            return False
        type_counts[s.get("type", "unknown")] += 1
        if s.get("negatives"):
            has_negs_count += 1

    print("\n--- Dataset Validation ---")
    print(f"Train samples count: {len(train_data)}")
    for t, cnt in type_counts.items():
        print(f"  - {t}: {cnt} ({cnt / len(train_data) * 100:.1f}%)")
    print(f"Samples with hard negatives: {has_negs_count}")
    print(f"Validation queries count: {len(val_data)}")

    if stats_path.exists():
        print("Stats file:")
        print(stats_path.read_text(encoding="utf-8"))

    print("[PASS] Dataset assembly is valid!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4: Assemble fine-tuning dataset")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Path to chunks.jsonl")
    parser.add_argument("--synthetic", type=Path, default=DEFAULT_SYNTHETIC, help="Path to synthetic_queries.jsonl")
    parser.add_argument("--kg-pairs", type=Path, default=DEFAULT_KG_PAIRS, help="Path to kg_positive_pairs.jsonl")
    parser.add_argument("--hard-negs", type=Path, default=DEFAULT_HARD_NEGS, help="Path to hard_negatives.jsonl")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK, help="Path to benchmark_questions.jsonl")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN, help="Path to train.jsonl")
    parser.add_argument("--val", type=Path, default=DEFAULT_VAL, help="Path to val.jsonl")
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS, help="Path to dataset_stats.json")
    parser.add_argument("--validate-only", action="store_true", help="Validate existing dataset files")
    args = parser.parse_args()

    if args.validate_only:
        valid = validate_dataset(args.train, args.val, args.stats)
        sys.exit(0 if valid else 1)

    assemble_dataset(
        chunks_path=args.chunks,
        synthetic_path=args.synthetic,
        kg_pairs_path=args.kg_pairs,
        hard_negs_path=args.hard_negs,
        benchmark_path=args.benchmark,
        train_path=args.train,
        val_path=args.val,
        stats_path=args.stats,
    )


if __name__ == "__main__":
    main()
