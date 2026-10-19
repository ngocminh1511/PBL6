"""Build the fine-tune query sets from every source (docs/FINETUNE_DATA.md).

    load (sources.py) -> align to v5 (align.py) -> select tier/temporal
    -> deduplicate -> drop near-duplicates of benchmark questions
    -> cap synthetic queries -> split train/val by article

Writes data/processed/finetune/<source>/aligned.jsonl for every source and,
in data/processed/finetune/merged/:
    queries_train.jsonl   query_id, query, chunk_id, positive_chunk_ids, source, tier, ...
    queries_val.jsonl     id, question, chunk_relevance (train.py's IR evaluator format)
    rejected.jsonl        qid, source, reason
    build_report.json     counts per stage and source, coverage, checks

Validation questions come from held-out articles, never from the benchmark;
the benchmark stays the final test set.

Usage:
    python -m labor_rag.finetune.build_dataset
    python -m labor_rag.finetune.build_dataset --no-synthetic --no-tier-b
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from labor_rag.config import (
    BENCHMARKS_DIR,
    EVALUATION_DIR,
    FINETUNE_MERGED_DIR,
    LAO_DONG_DIR,
    finetune_source_dir,
)
from labor_rag.finetune import sources
from labor_rag.finetune.align import V5Index, align_record, norm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# Dedup keeps the first source in this order: expert/real questions before
# scraped Q&A, synthetic last.
SOURCE_PRIORITY = ["alqac", "vilegal", "tvpl", "bkai", "zalo", "vlsp", "phamson02"]
KEEP_TEMPORAL = {"keep", "remap"}
DEFAULTS = {
    "tier_b_min": 0.3,
    "synthetic_cap": 0.4,
    "val_ratio": 0.1,
    "leak_threshold": 0.5,
    "seed": 13,
    "val_per_article": 5,
}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_benchmark_questions() -> list[str]:
    """Every benchmark question (v1, v2, v3 and frozen benchmarks/<dataset_id>/)."""
    paths = sorted(EVALUATION_DIR.glob("benchmark_questions*.jsonl")) + sorted(BENCHMARKS_DIR.glob("*/*.jsonl"))
    questions = set()
    for path in paths:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    q = json.loads(line).get("question")
                    if q:
                        questions.add(q)
    return sorted(questions)


class LeakFilter:
    """Word-set Jaccard against benchmark questions via a token -> question index."""

    def __init__(self, questions: list[str], threshold: float):
        self.threshold = threshold
        self.sets = [set(norm(q).split()) for q in questions]
        self.exact = {norm(q) for q in questions}
        self.by_token: dict[str, list[int]] = defaultdict(list)
        for i, toks in enumerate(self.sets):
            for tok in toks:
                self.by_token[tok].append(i)

    def max_jaccard(self, query: str) -> float:
        if norm(query) in self.exact:
            return 1.0
        toks = set(norm(query).split())
        shared: Counter[int] = Counter()
        for tok in toks:
            for i in self.by_token.get(tok, ()):
                shared[i] += 1
        return max((n / (len(toks) + len(self.sets[i]) - n) for i, n in shared.items()), default=0.0)

    def leaks(self, query: str) -> bool:
        return self.max_jaccard(query) >= self.threshold


def de_muc(index: V5Index, cid: str) -> str:
    return ".".join(index.chunks[cid]["mapc"].split(".")[:2])


def selectable(rec: dict[str, Any], include_tier_b: bool, tier_b_min: float) -> str | None:
    """None when the record may be used, else the rejection reason."""
    if rec["tier"] == "C":
        return f"tier_C_{rec['temporal']}"
    if rec["temporal"] not in KEEP_TEMPORAL:
        return f"temporal_{rec['temporal']}"
    if rec["tier"] == "B" and not (include_tier_b and rec["score"] is not None and rec["score"] >= tier_b_min):
        return "tier_B_below_min"
    return None


def cap_synthetic(real: list[dict], synthetic: list[dict], cap: float, rng: random.Random) -> tuple[list[dict], list[dict]]:
    """Keep at most cap * total synthetic records, preferring articles real questions miss."""
    if cap <= 0:
        return [], synthetic
    limit = int(cap / (1 - cap) * len(real)) if cap < 1 else len(synthetic)
    covered = {a for r in real for a in r["articles"]}
    pool = synthetic[:]
    rng.shuffle(pool)
    pool.sort(key=lambda r: all(a in covered for a in r["articles"]))
    return pool[:limit], pool[limit:]


def split_by_article(records: list[dict], index: V5Index, ratio: float, rng: random.Random) -> set[str]:
    """Val articles: `ratio` of the articles that have a real tier-A question, per de muc."""
    by_de_muc: dict[str, set[str]] = defaultdict(set)
    for r in records:
        if r["tier"] == "A" and not r["is_synthetic"]:
            for cid in r["positive_chunk_ids"]:
                by_de_muc[de_muc(index, cid)].add(r["articles"][0])
    val: set[str] = set()
    for dm in sorted(by_de_muc):
        arts = sorted(by_de_muc[dm])
        rng.shuffle(arts)
        val.update(arts[: max(1, round(len(arts) * ratio))])
    return val


def build(
    source_names: list[str] = list(sources.LOADERS),
    chunks_path: Path = LAO_DONG_DIR / "chunks.jsonl",
    out_dir: Path = FINETUNE_MERGED_DIR,
    include_tier_b: bool = True,
    tier_b_min: float = DEFAULTS["tier_b_min"],
    synthetic_cap: float = DEFAULTS["synthetic_cap"],
    val_ratio: float = DEFAULTS["val_ratio"],
    leak_threshold: float = DEFAULTS["leak_threshold"],
    seed: int = DEFAULTS["seed"],
    val_per_article: int = DEFAULTS["val_per_article"],
) -> dict[str, Any]:
    rng = random.Random(seed)
    index = V5Index.from_jsonl(chunks_path)
    stage: dict[str, Counter] = defaultdict(Counter)
    rejected: list[dict[str, Any]] = []

    def reject(rec: dict[str, Any], reason: str) -> None:
        rejected.append({"qid": rec["qid"], "source": rec["source"], "query": rec["query"], "reason": reason})
        stage[f"rejected:{reason}"][rec["source"]] += 1

    # 1. load + align, per-source aligned.jsonl
    candidates = []
    for name in source_names:
        aligned = [align_record(r, index) for r in sources.load_source(name)]
        write_jsonl(finetune_source_dir(name) / "aligned.jsonl", aligned)
        stage["loaded"][name] = len(aligned)
        for rec in aligned:
            stage[f"tier_{rec['tier']}"][name] += 1
            stage[f"temporal_{rec['temporal']}"][name] += 1
            reason = selectable(rec, include_tier_b, tier_b_min)
            if reason:
                reject(rec, reason)
            else:
                candidates.append(rec)
        print(f"  {name:10s} {len(aligned):6d} loaded, {stage['tier_A'][name]} tier A")

    # 2. deduplicate on the normalized query, best source first
    rank = {s: i for i, s in enumerate(SOURCE_PRIORITY)}
    candidates.sort(key=lambda r: (rank.get(r["source"], len(rank)), r["tier"], -(r["score"] or 1.0)))
    seen: set[str] = set()
    unique = []
    for rec in candidates:
        key = norm(rec["query"])
        if key in seen:
            reject(rec, "duplicate")
        else:
            seen.add(key)
            unique.append(rec)

    # 3. benchmark leakage
    leak = LeakFilter(load_benchmark_questions(), leak_threshold)
    clean = []
    for rec in unique:
        if leak.leaks(rec["query"]):
            reject(rec, "near_benchmark")
        else:
            clean.append(rec)

    # 4. split by article, then cap synthetic within train
    val_articles = split_by_article(clean, index, val_ratio, rng)
    train, val = [], []
    per_article: Counter[str] = Counter()
    for rec in clean:
        arts = set(rec["articles"])
        if not arts & val_articles:
            train.append(rec)
        elif not arts <= val_articles:
            reject(rec, "split_boundary")
        elif rec["tier"] != "A" or rec["is_synthetic"]:
            reject(rec, "val_article_not_eligible")
        elif per_article[rec["articles"][0]] >= val_per_article:
            reject(rec, "val_per_article_cap")
        else:
            per_article[rec["articles"][0]] += 1
            val.append(rec)
    real = [r for r in train if not r["is_synthetic"]]
    kept_syn, dropped_syn = cap_synthetic(real, [r for r in train if r["is_synthetic"]], synthetic_cap, rng)
    for rec in dropped_syn:
        reject(rec, "synthetic_cap")
    train = real + kept_syn
    train.sort(key=lambda r: r["qid"])
    val.sort(key=lambda r: r["qid"])

    # 5. write
    write_jsonl(out_dir / "queries_train.jsonl", [
        {
            "query_id": r["qid"],
            "query": r["query"],
            "chunk_id": r["positive_chunk_ids"][0],
            "positive_chunk_ids": r["positive_chunk_ids"],
            "source": r["source"],
            "is_synthetic": r["is_synthetic"],
            "tier": r["tier"],
            "temporal": r["temporal"],
            "score": r["score"],
            "match": r["match"],
        }
        for r in train
    ])
    write_jsonl(out_dir / "queries_val.jsonl", [
        {
            "id": r["qid"],
            "question": r["query"],
            "chunk_relevance": {cid: 1 for cid in r["positive_chunk_ids"]},
            "de_muc": de_muc(index, r["positive_chunk_ids"][0]),
            "source": r["source"],
        }
        for r in val
    ])
    write_jsonl(out_dir / "rejected.jsonl", rejected)

    v3_gold = set()
    v3_path = EVALUATION_DIR / "benchmark_questions_v3.jsonl"
    if v3_path.exists():
        with v3_path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    v3_gold.update(json.loads(line).get("chunk_relevance", {}))
    train_chunks = {cid for r in train for cid in r["positive_chunk_ids"]}
    train_articles = {a for r in train for a in r["articles"]}
    val_set_articles = {a for r in val for a in r["articles"]}
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus": str(chunks_path),
        "params": {
            "sources": source_names, "include_tier_b": include_tier_b, "tier_b_min": tier_b_min,
            "synthetic_cap": synthetic_cap, "val_ratio": val_ratio, "val_per_article": val_per_article,
            "leak_threshold": leak_threshold, "seed": seed,
        },
        "stages": {k: dict(v) for k, v in sorted(stage.items())},
        "train": {
            "total": len(train),
            "by_source": dict(Counter(r["source"] for r in train)),
            "by_tier": dict(Counter(r["tier"] for r in train)),
            "by_temporal": dict(Counter(r["temporal"] for r in train)),
            "synthetic_ratio": round(sum(r["is_synthetic"] for r in train) / max(1, len(train)), 4),
            "chunks_covered": len(train_chunks),
            "articles_covered": len(train_articles),
            "by_de_muc": dict(Counter(de_muc(index, cid) for cid in train_chunks)),
            "benchmark_v3_gold_covered": f"{len(v3_gold & train_chunks)}/{len(v3_gold)}",
        },
        "val": {
            "total": len(val),
            "articles": len(val_set_articles),
            "by_source": dict(Counter(r["source"] for r in val)),
            "by_de_muc": dict(Counter(de_muc(index, r["positive_chunk_ids"][0]) for r in val)),
        },
        "checks": {
            "train_val_article_overlap": len(train_articles & val_set_articles),
            "near_benchmark_left": sum(leak.leaks(r["query"]) for r in train + val),
            "synthetic_ratio_ok": sum(r["is_synthetic"] for r in train) <= synthetic_cap * max(1, len(train)) + 1,
        },
        "corpus_chunks": len(index.chunks),
    }
    (out_dir / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sources", nargs="+", choices=list(sources.LOADERS), default=list(sources.LOADERS))
    parser.add_argument("--chunks", type=Path, default=LAO_DONG_DIR / "chunks.jsonl")
    parser.add_argument("--out-dir", type=Path, default=FINETUNE_MERGED_DIR)
    parser.add_argument("--no-tier-b", action="store_true", help="Chỉ dùng tier A")
    parser.add_argument("--tier-b-min", type=float, default=DEFAULTS["tier_b_min"])
    parser.add_argument("--synthetic-cap", type=float, default=DEFAULTS["synthetic_cap"])
    parser.add_argument("--no-synthetic", action="store_true", help="Bỏ hẳn câu hỏi sinh tự động")
    parser.add_argument("--val-ratio", type=float, default=DEFAULTS["val_ratio"])
    parser.add_argument("--val-per-article", type=int, default=DEFAULTS["val_per_article"])
    parser.add_argument("--leak-threshold", type=float, default=DEFAULTS["leak_threshold"])
    parser.add_argument("--seed", type=int, default=DEFAULTS["seed"])
    args = parser.parse_args()

    report = build(
        source_names=args.sources,
        chunks_path=args.chunks,
        out_dir=args.out_dir,
        include_tier_b=not args.no_tier_b,
        tier_b_min=args.tier_b_min,
        synthetic_cap=0.0 if args.no_synthetic else args.synthetic_cap,
        val_ratio=args.val_ratio,
        leak_threshold=args.leak_threshold,
        seed=args.seed,
        val_per_article=args.val_per_article,
    )
    print(json.dumps({k: report[k] for k in ("train", "val", "checks")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
