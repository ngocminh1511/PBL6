"""Embed data/legacy/chunks.jsonl (from build_chunks.py) with a Vietnamese
sentence-embedding model and upsert into Qdrant. Requires the qdrant
container from docker-compose.yml to be running.

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

from labor_rag.config import LEGACY_DIR

sys.stdout.reconfigure(encoding="utf-8")

CHUNKS_PATH = LEGACY_DIR / "chunks.jsonl"

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
COLLECTION = os.getenv("QDRANT_COLLECTION", "labor_dieu")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
BATCH_SIZE = 64


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
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

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
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
            for idx, (c, vector) in enumerate(zip(batch, vectors), start=start)
        ]
        client.upsert(collection_name=args.collection, points=points)
        print(f"  upserted {start + len(batch)}/{len(chunks)}")

    print(f"Done. Qdrant dashboard: {args.qdrant_url}/dashboard#/collections/{args.collection}")


if __name__ == "__main__":
    main()
