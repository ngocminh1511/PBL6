"""Stage 3: Hard Negative Mining for BGE-M3 Fine-tuning.

Uses a pretrained bi-encoder (default: BAAI/bge-m3) to mine hard negatives
for each query in merged/queries_train.jsonl (build_dataset.py).

Hard negatives are passages that score high in cosine similarity against
the query embedding, but are NOT a positive passage: candidates in the same
Article/Điều as any positive, or in an article that a positive's article
REFERS_TO (or is referred to by), are skipped as likely false negatives.

Output JSONL schema:
    {
        "query_id": "...",
        "query": "...",
        "chunk_id": "...",
        "positive_chunk_ids": ["...", ...],
        "hard_negatives": [
            {"chunk_id": "...", "score": 0.812},
            ...
        ]
    }

Usage:
    python -m labor_rag.finetune.mine_negatives
    python -m labor_rag.finetune.mine_negatives --neg-k 5 --top-k 30
    python -m labor_rag.finetune.mine_negatives --validate-only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import torch
from sentence_transformers import SentenceTransformer

from labor_rag.config import FINETUNE_MERGED_DIR, LAO_DONG_DIR
from labor_rag.ingest.chunk_schema import article_id

DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_QUERIES = FINETUNE_MERGED_DIR / "queries_train.jsonl"
DEFAULT_OUTPUT = FINETUNE_MERGED_DIR / "hard_negatives.jsonl"
DEFAULT_KG_EDGES = LAO_DONG_DIR / "kg_edges.jsonl"
DEFAULT_MODEL = "BAAI/bge-m3"
ARTICLE_IRI_PREFIX = "Article_"


def load_reference_neighbours(edges_path: Path, chunks: list[dict[str, Any]]) -> dict[str, set[str]]:
    """article_id -> article_ids it REFERS_TO or is referred to by (both directions)."""
    if not edges_path.exists():
        return {}
    article_of_mapc = {c["mapc"]: article_id(c["chunk_id"]) for c in chunks if c.get("mapc")}

    def to_article(node: str) -> str | None:
        if node in article_of_mapc:
            return article_of_mapc[node]
        tail = node.rsplit("#", 1)[-1]
        if tail.startswith(ARTICLE_IRI_PREFIX):
            return article_of_mapc.get(tail[len(ARTICLE_IRI_PREFIX):].replace("_", "."))
        return None

    neighbours: dict[str, set[str]] = defaultdict(set)
    with edges_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            edge = json.loads(line)
            if edge.get("type") != "REFERS_TO":
                continue
            a, b = to_article(edge["source"]), to_article(edge["target"])
            if a and b and a != b:
                neighbours[a].add(b)
                neighbours[b].add(a)
    return neighbours


def load_chunks(chunks_path: Path) -> list[dict[str, Any]]:
    chunks = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def load_queries(queries_path: Path) -> list[dict[str, Any]]:
    queries = []
    with queries_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def mine_hard_negatives(
    queries: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    model_name: str = DEFAULT_MODEL,
    output_path: Path = DEFAULT_OUTPUT,
    top_k: int = 30,
    neg_k: int = 5,
    batch_size: int = 32,
    device: str | None = None,
    neighbours: dict[str, set[str]] | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading embedding model '{model_name}' on {device}...")
    model = SentenceTransformer(model_name, device=device)

    # Load existing progress if any
    seen_query_ids: set[str] = set()
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        seen_query_ids.add(rec["query_id"])
                    except Exception:
                        pass
        print(f"Resuming: found {len(seen_query_ids)} already mined queries.")

    pending_queries = [q for q in queries if q["query_id"] not in seen_query_ids]
    if not pending_queries:
        print("All queries already processed.")
        return

    print(f"Encoding corpus ({len(chunks)} chunks)...")
    t0 = time.time()
    corpus_texts = [c["text"] for c in chunks]
    corpus_embeddings = model.encode(
        corpus_texts,
        batch_size=batch_size,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    print(f"Corpus encoded in {time.time() - t0:.1f}s. Embedding shape: {corpus_embeddings.shape}")

    # Build lookup for chunk articles
    chunk_articles = [article_id(c["chunk_id"]) for c in chunks]

    print(f"Mining hard negatives for {len(pending_queries)} queries (top_k={top_k}, neg_k={neg_k})...")
    mined_count = 0
    with output_path.open("a", encoding="utf-8") as out_f:
        for start_idx in range(0, len(pending_queries), batch_size):
            batch = pending_queries[start_idx : start_idx + batch_size]
            batch_query_texts = [q["query"] for q in batch]

            batch_query_embs = model.encode(
                batch_query_texts,
                batch_size=len(batch),
                convert_to_tensor=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            # Cosine similarity matrix: [batch_len, corpus_size]
            sim_matrix = torch.matmul(batch_query_embs, corpus_embeddings.T)
            top_scores, top_indices = torch.topk(sim_matrix, k=min(top_k, len(chunks)), dim=1)

            for i, query_item in enumerate(batch):
                positives = query_item.get("positive_chunk_ids") or [query_item["chunk_id"]]
                excluded = {article_id(cid) for cid in positives}
                for art in list(excluded):
                    excluded |= (neighbours or {}).get(art, set())
                negatives: list[dict[str, Any]] = []

                cand_indices = top_indices[i].tolist()
                cand_scores = top_scores[i].tolist()

                for c_idx, score in zip(cand_indices, cand_scores):
                    cand_chunk = chunks[c_idx]
                    # Exclude positives, their articles and referenced articles
                    if chunk_articles[c_idx] in excluded:
                        continue
                    negatives.append(
                        {
                            "chunk_id": cand_chunk["chunk_id"],
                            "score": round(float(score), 4),
                        }
                    )
                    if len(negatives) >= neg_k:
                        break

                record = {
                    "query_id": query_item["query_id"],
                    "query": query_item["query"],
                    "chunk_id": query_item["chunk_id"],
                    "positive_chunk_ids": positives,
                    "hard_negatives": negatives,
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                mined_count += 1

            out_f.flush()
            if (start_idx + batch_size) % (batch_size * 10) == 0 or (start_idx + len(batch)) == len(pending_queries):
                current_done = min(start_idx + len(batch), len(pending_queries))
                print(f"[{current_done}/{len(pending_queries)}] Mined hard negatives for {current_done} queries.")

    print(f"Hard negative mining complete! Total queries mined: {mined_count}. Saved to {output_path}")


def validate_hard_negatives(output_path: Path = DEFAULT_OUTPUT) -> bool:
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

    required = {"query_id", "query", "chunk_id", "hard_negatives"}
    neg_counts = Counter()
    has_false_positives = 0

    for idx, rec in enumerate(records, 1):
        missing = required - set(rec.keys())
        if missing:
            print(f"[FAIL] Record #{idx} missing fields: {missing}")
            return False
        negs = rec.get("hard_negatives", [])
        neg_counts[len(negs)] += 1

        pos_art = article_id(rec["chunk_id"])
        for n in negs:
            if article_id(n["chunk_id"]) == pos_art:
                has_false_positives += 1

    if has_false_positives > 0:
        print(f"[WARN] Found {has_false_positives} hard negatives that share the same article as the query!")

    print("\n--- Hard Negatives Validation ---")
    print(f"Total queries: {len(records)}")
    print("Hard negatives count distribution per query:")
    for num_negs, count in sorted(neg_counts.items()):
        print(f"  - {num_negs} negatives: {count} queries ({count / len(records) * 100:.1f}%)")
    print("Sample record:")
    print(json.dumps(records[0], ensure_ascii=False, indent=2))
    print("[PASS] Hard negatives file is valid!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: Mine hard negatives using pretrained bi-encoder")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Path to chunks.jsonl")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES, help="Path to queries_train.jsonl")
    parser.add_argument("--kg-edges", type=Path, default=DEFAULT_KG_EDGES, help="kg_edges.jsonl for REFERS_TO exclusion")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to output jsonl")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Model name for negative mining")
    parser.add_argument("--top-k", type=int, default=30, help="Initial candidate pool size per query")
    parser.add_argument("--neg-k", type=int, default=5, help="Number of hard negatives to keep per query")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for encoding")
    parser.add_argument("--device", type=str, default=None, help="Device (cpu or cuda)")
    parser.add_argument("--validate-only", action="store_true", help="Validate output file only")
    args = parser.parse_args()

    if args.validate_only:
        valid = validate_hard_negatives(args.output)
        sys.exit(0 if valid else 1)

    chunks = load_chunks(args.chunks)
    queries = load_queries(args.queries)

    mine_hard_negatives(
        queries=queries,
        chunks=chunks,
        model_name=args.model,
        output_path=args.output,
        top_k=args.top_k,
        neg_k=args.neg_k,
        batch_size=args.batch_size,
        device=args.device,
        neighbours=load_reference_neighbours(args.kg_edges, chunks),
    )


if __name__ == "__main__":
    main()
