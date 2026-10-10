"""Embed data/processed/lao_dong_v4/chunks.jsonl (from ontology_to_jsonl.py)
with a Vietnamese sentence-embedding model and upsert into Qdrant. Requires
the qdrant container from docker-compose.yml to be running.

Usage: python -m labor_rag.ingest.embed_and_index [--chunks ...] [--collection ...]
"""
from __future__ import annotations

import json
import argparse
import os
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from labor_rag.config import LAO_DONG_V4_DIR
from labor_rag.ingest.batching import DEFAULT_MAX_BATCH_TOKENS, length_batches

sys.stdout.reconfigure(encoding="utf-8")

CHUNKS_PATH = LAO_DONG_V4_DIR / "chunks.jsonl"

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_ld_v4_bkai")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
BATCH_SIZE = 64


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Max chunks per batch")
    parser.add_argument(
        "--max-batch-tokens",
        type=int,
        default=DEFAULT_MAX_BATCH_TOKENS,
        help="Token budget per batch (batch size x longest chunk); raise it on a large GPU",
    )
    args = parser.parse_args()

    chunks = [json.loads(line) for line in args.chunks.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(chunks)} chunks from {args.chunks}")

    print(f"Loading embedding model: {args.model} (first run downloads it, may take a while)")
    model = SentenceTransformer(args.model)
    dim = model.get_sentence_embedding_dimension()
    print(f"Embedding dimension: {dim}")

    client = QdrantClient(url=args.qdrant_url)
    client.recreate_collection(
        collection_name=args.collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    texts = [c["text"] for c in chunks]
    batches = length_batches(texts, model.tokenizer, model.max_seq_length, args.max_batch_tokens, args.batch_size)
    done = 0
    for batch_ids in batches:
        batch = [chunks[idx] for idx in batch_ids]
        vectors = model.encode(
            [texts[idx] for idx in batch_ids],
            batch_size=len(batch_ids),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # Point ids stay the chunk's position in the file, whatever the batch order.
        points = [
            PointStruct(
                id=idx,
                vector=vector.tolist(),
                payload={
                    "mapc": c["mapc"],
                    "uri": c.get("uri"),
                    "de_muc_id": c.get("de_muc_id"),
                    "de_muc_so": c.get("de_muc_so"),
                    "chuong": c.get("chuong"),
                    "muc": c.get("muc"),
                    "ten": c.get("ten"),
                    "citation": c.get("citation"),
                    "breadcrumb": c.get("breadcrumb", ""),
                    "text": c.get("text", ""),
                    "document_uri": c.get("document_uri"),
                    "source": c.get("source", "labor_rag"),
                    "dataset_id": c.get("dataset_id"),
                },
            )
            for idx, c, vector in zip(batch_ids, batch, vectors)
        ]
        client.upsert(collection_name=args.collection, points=points)
        done += len(batch_ids)
        print(f"  upserted {done}/{len(chunks)} (batch of {len(batch_ids)})")

    print(f"Done. Qdrant dashboard: {args.qdrant_url}/dashboard#/collections/{args.collection}")


if __name__ == "__main__":
    main()
