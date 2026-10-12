"""Stage 2: Knowledge Graph Positive Pairs for BGE-M3 Fine-tuning.

Extracts semantic positive pairs from the Lao dong Knowledge Graph:
1. REFERS_TO: Two articles that explicitly cite each other (cross-reference) -> strong semantic relation.
2. Same Chapter (PART_OF Chapter): Two articles belonging to the same legal chapter -> topical relation.
3. Split Article Parts: Parts of the same article (e.g. p1 and p2) -> structural positive pair.

Output JSONL schema:
    {
        "pair_id": "kg_refers_...",
        "anchor": "text of article A",
        "positive": "text of article B",
        "relation": "refers_to | same_chapter | same_article_part",
        "anchor_id": "mapc or chunk_id",
        "positive_id": "mapc or chunk_id"
    }

Usage:
    python -m labor_rag.finetune.kg_pairs
    python -m labor_rag.finetune.kg_pairs --validate-only
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from labor_rag.config import FINETUNE_DIR, LAO_DONG_DIR
from labor_rag.ingest.chunk_schema import article_id

DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_EDGES = LAO_DONG_DIR / "kg_edges.jsonl"
DEFAULT_OUTPUT = FINETUNE_DIR / "kg_positive_pairs.jsonl"


def load_chunks_map(chunks_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Load chunks and index by mapc and article_id.

    Returns:
        mapc_to_chunk: mapc -> representative chunk (part 1 or single chunk)
        article_to_parts: article_id -> list of chunks
    """
    mapc_to_chunk: dict[str, dict[str, Any]] = {}
    article_to_parts: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            mapc = chunk.get("mapc")
            if mapc and mapc not in mapc_to_chunk:
                # First part or single chunk
                mapc_to_chunk[mapc] = chunk
            art_id = article_id(chunk["chunk_id"])
            article_to_parts[art_id].append(chunk)

    return mapc_to_chunk, article_to_parts


def build_refers_to_pairs(
    mapc_to_chunk: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build positive pairs from REFERS_TO edges between articles."""
    pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for edge in edges:
        if edge.get("type") != "REFERS_TO":
            continue
        src = edge.get("source", "")
        tgt = edge.get("target", "")

        if not src or not tgt or src == tgt:
            continue
        if src not in mapc_to_chunk or tgt not in mapc_to_chunk:
            continue

        pair_key = (src, tgt)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        anchor_chunk = mapc_to_chunk[src]
        positive_chunk = mapc_to_chunk[tgt]

        safe_src = src.replace(".", "_")
        safe_tgt = tgt.replace(".", "_")
        pairs.append(
            {
                "pair_id": f"kg_refers_{safe_src}_{safe_tgt}",
                "anchor": anchor_chunk["text"],
                "positive": positive_chunk["text"],
                "relation": "refers_to",
                "anchor_id": src,
                "positive_id": tgt,
            }
        )

    return pairs


def build_chapter_pairs(
    mapc_to_chunk: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    max_per_chapter: int = 20,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Build positive pairs from articles belonging to the same legal chapter."""
    chapter_members: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.get("type") == "PART_OF" and "Chapter" in edge.get("target", ""):
            src = edge.get("source", "")
            if src in mapc_to_chunk:
                chapter_members[edge["target"]].append(src)

    rng = random.Random(seed)
    pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for ch_iri, members in sorted(chapter_members.items()):
        # Deduplicate members within chapter
        unique_members = sorted(set(members))
        if len(unique_members) < 2:
            continue

        all_combos = list(itertools.combinations(unique_members, 2))
        k = min(max_per_chapter, len(all_combos))
        sampled = rng.sample(all_combos, k) if len(all_combos) > k else all_combos

        ch_name = ch_iri.split("#")[-1]
        for src, tgt in sampled:
            pair_key = (min(src, tgt), max(src, tgt))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            safe_src = src.replace(".", "_")
            safe_tgt = tgt.replace(".", "_")
            pairs.append(
                {
                    "pair_id": f"kg_ch_{ch_name}_{safe_src}_{safe_tgt}",
                    "anchor": mapc_to_chunk[src]["text"],
                    "positive": mapc_to_chunk[tgt]["text"],
                    "relation": "same_chapter",
                    "anchor_id": src,
                    "positive_id": tgt,
                }
            )

    return pairs


def build_split_article_pairs(
    article_to_parts: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build pairs from consecutive parts of long articles split into parts."""
    pairs: list[dict[str, Any]] = []
    for art_id, parts in article_to_parts.items():
        if len(parts) < 2:
            continue
        sorted_parts = sorted(parts, key=lambda c: c["chunk_id"])
        for i in range(len(sorted_parts) - 1):
            p1 = sorted_parts[i]
            p2 = sorted_parts[i + 1]
            safe_id1 = p1["chunk_id"].replace(":", "_").replace("-", "_")
            safe_id2 = p2["chunk_id"].replace(":", "_").replace("-", "_")
            pairs.append(
                {
                    "pair_id": f"kg_part_{safe_id1}_{safe_id2}",
                    "anchor": p1["text"],
                    "positive": p2["text"],
                    "relation": "same_article_part",
                    "anchor_id": p1["chunk_id"],
                    "positive_id": p2["chunk_id"],
                }
            )
    return pairs


def run_build_kg_pairs(
    chunks_path: Path = DEFAULT_CHUNKS,
    edges_path: Path = DEFAULT_EDGES,
    output_path: Path = DEFAULT_OUTPUT,
    max_chapter_pairs: int = 20,
    seed: int = 42,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading chunks from {chunks_path}...")
    mapc_to_chunk, article_to_parts = load_chunks_map(chunks_path)
    print(f"Loaded {len(mapc_to_chunk)} unique mapc and {len(article_to_parts)} unique articles.")

    print(f"Loading edges from {edges_path}...")
    edges: list[dict[str, Any]] = []
    with edges_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                edges.append(json.loads(line))
    print(f"Loaded {len(edges)} KG edges.")

    print("Building REFERS_TO pairs...")
    refers_pairs = build_refers_to_pairs(mapc_to_chunk, edges)
    print(f"Found {len(refers_pairs)} REFERS_TO pairs.")

    print("Building same-chapter pairs...")
    chapter_pairs = build_chapter_pairs(mapc_to_chunk, edges, max_per_chapter=max_chapter_pairs, seed=seed)
    print(f"Found {len(chapter_pairs)} same-chapter pairs.")

    print("Building split article pairs...")
    split_pairs = build_split_article_pairs(article_to_parts)
    print(f"Found {len(split_pairs)} split article pairs.")

    all_pairs = refers_pairs + chapter_pairs + split_pairs

    with output_path.open("w", encoding="utf-8") as f:
        for p in all_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"Saved {len(all_pairs)} total KG positive pairs to {output_path}")


def validate_kg_pairs(output_path: Path = DEFAULT_OUTPUT) -> bool:
    if not output_path.exists():
        print(f"[FAIL] Output file does not exist: {output_path}")
        return False

    records: list[dict[str, Any]] = []
    with output_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records.append(rec)
            except Exception as e:
                print(f"[FAIL] Line {idx} invalid JSON: {e}")
                return False

    if not records:
        print(f"[FAIL] Output file is empty: {output_path}")
        return False

    required = {"pair_id", "anchor", "positive", "relation", "anchor_id", "positive_id"}
    rel_counter = Counter()

    for idx, rec in enumerate(records, 1):
        missing = required - set(rec.keys())
        if missing:
            print(f"[FAIL] Record #{idx} missing fields: {missing}")
            return False
        if not rec["anchor"].strip() or not rec["positive"].strip():
            print(f"[FAIL] Record #{idx} has empty anchor or positive text")
            return False
        rel_counter[rec["relation"]] += 1

    print("\n--- KG Positive Pairs Validation ---")
    print(f"Total pairs: {len(records)}")
    print("Relation breakdown:")
    for rel, count in rel_counter.most_common():
        pct = (count / len(records)) * 100
        print(f"  - {rel}: {count} ({pct:.1f}%)")
    print("Sample pair:")
    sample = dict(records[0])
    sample["anchor"] = sample["anchor"][:100] + "..."
    sample["positive"] = sample["positive"][:100] + "..."
    print(json.dumps(sample, ensure_ascii=False, indent=2))
    print("[PASS] KG positive pairs file is valid!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: Build KG-based positive pairs")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Path to chunks.jsonl")
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES, help="Path to kg_edges.jsonl")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to output jsonl")
    parser.add_argument("--max-chapter-pairs", type=int, default=20, help="Max pairs sampled per chapter")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--validate-only", action="store_true", help="Validate output file only")
    args = parser.parse_args()

    if args.validate_only:
        valid = validate_kg_pairs(args.output)
        sys.exit(0 if valid else 1)

    run_build_kg_pairs(
        chunks_path=args.chunks,
        edges_path=args.edges,
        output_path=args.output,
        max_chapter_pairs=args.max_chapter_pairs,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
