"""Embed data/processed/lao_dong_v4/chunks.jsonl (from ontology_to_jsonl.py)
with a Vietnamese sentence-embedding model and upsert into Qdrant.

Qdrant is QDRANT_URL (+ QDRANT_API_KEY for Qdrant Cloud), read from .env;
the default is the local qdrant container from docker-compose.yml.

Embedding runs on the local GPU/CPU by default. With --backend modal it runs
on a Modal GPU (deploy scripts/modal_embed.py once first); only the vectors
come back, the upsert still happens from this machine.

Usage: python -m labor_rag.ingest.embed_and_index [--backend modal] [--model ...] [--collection ...]
"""
from __future__ import annotations

import json
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from labor_rag.config import LAO_DONG_V4_DIR
from labor_rag.ingest.batching import DEFAULT_MAX_BATCH_TOKENS, length_batches

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

CHUNKS_PATH = LAO_DONG_V4_DIR / "chunks.jsonl"

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_ld_v4_bkai")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
BACKEND = os.getenv("EMBEDDING_BACKEND", "local")
BATCH_SIZE = 64
UPSERT_BATCH = 128
# A Modal T4 has 16 GB, four times the 4 GB the local default was measured on.
MODAL_MAX_BATCH_TOKENS = 32768
MODAL_APP = "labor-rag-embed"


def chunk_payload(c: dict) -> dict:
    return {
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
    }


def embed_local(texts: list[str], model_name: str, max_batch_tokens: int, batch_size: int):
    """Yield (indices, vectors) per length-aware batch, embedded on this machine."""
    from sentence_transformers import SentenceTransformer

    print(f"Loading embedding model: {model_name} (first run downloads it, may take a while)")
    model = SentenceTransformer(model_name)
    batches = length_batches(texts, model.tokenizer, model.max_seq_length, max_batch_tokens, batch_size)
    for batch_ids in batches:
        vectors = model.encode(
            [texts[idx] for idx in batch_ids],
            batch_size=len(batch_ids),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        yield batch_ids, vectors


def embed_modal(texts: list[str], model_name: str, max_batch_tokens: int, batch_size: int):
    """Embed everything in one call to the deployed Modal app, then yield fixed-size slices."""
    import modal
    import numpy as np

    print(f"Embedding {len(texts)} texts with {model_name} on Modal (cold start loads the model, ~1-2 min)")
    embedder = modal.Cls.from_name(MODAL_APP, "Embedder")(model_name=model_name)
    result = embedder.embed.remote(texts, max_batch_tokens, batch_size)
    vectors = np.frombuffer(result["vectors"], dtype=np.float32).reshape(len(texts), result["dim"])
    for start in range(0, len(texts), UPSERT_BATCH):
        ids = list(range(start, min(start + UPSERT_BATCH, len(texts))))
        yield ids, vectors[ids]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--collection", default=COLLECTION)
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    parser.add_argument("--backend", choices=["local", "modal"], default=BACKEND)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Max chunks per batch")
    parser.add_argument(
        "--max-batch-tokens",
        type=int,
        default=None,
        help=f"Token budget per batch (batch size x longest chunk); default {DEFAULT_MAX_BATCH_TOKENS} "
        f"local, {MODAL_MAX_BATCH_TOKENS} on Modal",
    )
    args = parser.parse_args()
    max_batch_tokens = args.max_batch_tokens or (
        MODAL_MAX_BATCH_TOKENS if args.backend == "modal" else DEFAULT_MAX_BATCH_TOKENS
    )

    chunks = [json.loads(line) for line in args.chunks.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(chunks)} chunks from {args.chunks}")
    texts = [c["text"] for c in chunks]

    # Fail on a wrong URL/key before spending GPU time.
    client = QdrantClient(url=args.qdrant_url, api_key=QDRANT_API_KEY)
    client.get_collections()

    embed = embed_modal if args.backend == "modal" else embed_local
    done = 0
    for batch_ids, vectors in embed(texts, args.model, max_batch_tokens, args.batch_size):
        if done == 0:
            dim = len(vectors[0])
            print(f"Embedding dimension: {dim}")
            if client.collection_exists(args.collection):
                client.delete_collection(args.collection)
            client.create_collection(
                collection_name=args.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        # Point ids stay the chunk's position in the file, whatever the batch order.
        points = [
            PointStruct(id=idx, vector=vector.tolist(), payload=chunk_payload(chunks[idx]))
            for idx, vector in zip(batch_ids, vectors)
        ]
        client.upsert(collection_name=args.collection, points=points)
        done += len(batch_ids)
        print(f"  upserted {done}/{len(chunks)} (batch of {len(batch_ids)})")

    print(f"Done. Qdrant dashboard: {args.qdrant_url}/dashboard#/collections/{args.collection}")


if __name__ == "__main__":
    main()
