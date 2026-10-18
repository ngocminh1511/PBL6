"""Embed data/processed/lao_dong_v5/chunks.jsonl (from ontology_to_jsonl.py)
with a sentence-embedding model (bge-m3 by default) and upsert into Qdrant.

Point ids are uuid5(chunk_id), so re-indexing a document overwrites its own
points; the whole chunk is the payload, with indexes on the fields that
retrieval filters on (docs/structural_jsonl.md, sections 5.3 and 6).

Qdrant is QDRANT_URL (+ QDRANT_API_KEY for Qdrant Cloud), read from .env;
the default is the local qdrant container from docker-compose.yml.

Embedding runs on the local GPU/CPU by default. With --backend modal it runs
on a Modal GPU (deploy scripts/modal_embed.py once first); only the vectors
come back, the upsert still happens from this machine.

By default the collection is rebuilt from --chunks. With --upsert it is kept
and the chunks are merged in per Dieu (labor_rag/ingest/merge.py): the newer
version_date wins and the losing Dieu's old parts are deleted. A rebuild drops
PDF chunks loaded with --upsert, so it stops when the collection holds chunks
from another source; pass --recreate to rebuild anyway, then load them again.

Chunks of an amending document carry amends; after writing them, each amended
Dieu already in the collection gets the matching amended_by entries
(set_payload, no re-embedding; labor_rag/ingest/amending.py). A chunk whose
replaces names other documents ends them: effective_to_date = its
effective_from_date, and still_valid = false once that date has passed.

Usage: python -m labor_rag.ingest.embed_and_index [--backend modal] [--model ...] [--collection ...]
       python -m labor_rag.ingest.embed_and_index --chunks data/interim/pdf_chunks/<doc>_chunks.jsonl --upsert
       python -m labor_rag.ingest.embed_and_index --recreate   # rebuild, dropping PDF chunks
"""
from __future__ import annotations

import json
import argparse
import os
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from labor_rag.config import LAO_DONG_DATASET_ID, LAO_DONG_DIR
from labor_rag.ingest.amending import amended_by_updates, merge_amended_by, replaced_by
from labor_rag.ingest.batching import DEFAULT_MAX_BATCH_TOKENS, length_batches
from labor_rag.ingest.chunk_schema import article_id, point_id
from labor_rag.ingest.merge import PHAP_DIEN, plan_upsert

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

CHUNKS_PATH = LAO_DONG_DIR / "chunks.jsonl"

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_ld_v5_bge")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
# Seconds per request; the 5 s client default is too short for a far-away Qdrant Cloud region.
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "60"))
UPSERT_RETRIES = 3
BACKEND = os.getenv("EMBEDDING_BACKEND", "local")
BATCH_SIZE = 64
UPSERT_BATCH = 128
# A Modal T4 has 16 GB, four times the 4 GB the local default was measured on.
MODAL_MAX_BATCH_TOKENS = 32768
MODAL_APP = "labor-rag-embed"


PAYLOAD_INDEXES = {
    "document_id": PayloadSchemaType.KEYWORD,
    "mapc": PayloadSchemaType.KEYWORD,
    "meta_dieu": PayloadSchemaType.KEYWORD,
    "source": PayloadSchemaType.KEYWORD,
    "still_valid": PayloadSchemaType.BOOL,
    "effective_from_date": PayloadSchemaType.DATETIME,
    "effective_to_date": PayloadSchemaType.DATETIME,
}


def chunk_payload(c: dict) -> dict:
    return {**c, "dataset_id": c.get("dataset_id", LAO_DONG_DATASET_ID)}


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


def upsert_with_retry(client: QdrantClient, collection: str, points: list[PointStruct]) -> None:
    """Upsert one batch, retrying a timed-out request; point ids are stable, so a retry is idempotent."""
    for attempt in range(1, UPSERT_RETRIES + 1):
        try:
            client.upsert(collection_name=collection, points=points)
            return
        except ResponseHandlingException as exc:
            if attempt == UPSERT_RETRIES:
                raise
            print(f"  upsert failed ({exc}); retry {attempt}/{UPSERT_RETRIES - 1}")
            time.sleep(5 * attempt)


MERGE_FIELDS = ["chunk_id", "document_id", "meta_dieu", "source", "version_date", "text"]


def indexed_chunks(client: QdrantClient, collection: str, document_ids: list[str]) -> list[dict]:
    """Payloads already in the collection for these documents."""
    found: list[dict] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(must=[FieldCondition(key="document_id", match=MatchAny(any=document_ids))]),
            with_payload=MERGE_FIELDS,
            with_vectors=False,
            limit=256,
            offset=offset,
        )
        found += [point.payload for point in points if point.payload]
        if offset is None:
            return found


def other_source_documents(client: QdrantClient, collection: str) -> Counter:
    """Chunk count per document_id for chunks whose source is not Phap dien."""
    found: Counter = Counter()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(must_not=[FieldCondition(key="source", match=MatchValue(value=PHAP_DIEN))]),
            with_payload=["document_id"],
            with_vectors=False,
            limit=256,
            offset=offset,
        )
        found.update(str((point.payload or {}).get("document_id")) for point in points)
        if offset is None:
            return found


def link_amendments(client: QdrantClient, collection: str, chunks: list[dict]) -> None:
    """Add the amends of these chunks to amended_by of every part of the
    amended Dieu. A Dieu not indexed yet is reported; load this file again
    after loading it."""
    updates = amended_by_updates(chunks)
    if not updates:
        return
    document_ids = sorted({target.split(":", 1)[0] for target in updates})
    indexed: dict[str, list] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(must=[FieldCondition(key="document_id", match=MatchAny(any=document_ids))]),
            with_payload=["chunk_id", "amended_by"],
            with_vectors=False,
            limit=256,
            offset=offset,
        )
        for point in points:
            indexed.setdefault(article_id(point.payload["chunk_id"]), []).append(point)
        if offset is None:
            break
    for target, entries in sorted(updates.items()):
        for point in indexed.get(target, []):
            merged = merge_amended_by(point.payload.get("amended_by") or [], entries)
            client.set_payload(collection, payload={"amended_by": merged}, points=[point.id])
        print(f"  amended_by of {target}: {len(entries)} entries" if target in indexed else f"WARNING: {target} is amended but not indexed")


def retire_replaced(client: QdrantClient, collection: str, chunks: list[dict]) -> None:
    """End the documents these chunks replace, without re-embedding them."""
    for document_id, effective in sorted(replaced_by(chunks).items()):
        selector = Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
        found = client.count(collection, count_filter=selector, exact=True).count
        if not found:
            print(f"WARNING: {document_id} is replaced but not indexed")
            continue
        payload: dict = {"effective_to_date": effective}
        if effective and effective <= date.today().isoformat():
            payload["still_valid"] = False
        client.set_payload(collection, payload=payload, points=selector)
        print(f"  {document_id}: {found} chunks ended on {effective}")


def apply_upsert_plan(client: QdrantClient, collection: str, chunks: list[dict]) -> list[dict]:
    """Delete the old parts of every Dieu the new chunks win, and return the
    chunks still to embed and write."""
    document_ids = sorted({c["document_id"] for c in chunks})
    plan = plan_upsert(indexed_chunks(client, collection, document_ids), chunks)
    for warning in plan.warnings:
        print(f"WARNING: {warning}")
    print(
        f"Upsert into {collection}: write {len(plan.upsert)} chunks, delete {len(plan.delete)} old parts, "
        f"keep {len(plan.kept)} newer indexed Dieu, {len(plan.unchanged)} unchanged"
    )
    for key in plan.kept:
        print(f"  kept indexed version of {key}")
    if plan.delete:
        client.delete(collection, points_selector=PointIdsList(points=[point_id(c) for c in plan.delete]))
    return plan.upsert


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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--upsert",
        action="store_true",
        help="add to the collection instead of rebuilding it: per Dieu, the newer version_date wins "
        "(labor_rag/ingest/merge.py); used for PDF chunks from pdf_to_chunks",
    )
    mode.add_argument(
        "--recreate",
        action="store_true",
        help="rebuild even when the collection holds chunks from another source (PDF); they are dropped",
    )
    args = parser.parse_args()
    max_batch_tokens = args.max_batch_tokens or (
        MODAL_MAX_BATCH_TOKENS if args.backend == "modal" else DEFAULT_MAX_BATCH_TOKENS
    )

    chunks = [json.loads(line) for line in args.chunks.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(chunks)} chunks from {args.chunks}")
    duplicates = [key for key, n in Counter(c["chunk_id"] for c in chunks).items() if n > 1]
    if duplicates:
        raise SystemExit(f"Repeated chunk_id would overwrite points: {duplicates[:5]}")

    # Fail on a wrong URL/key before spending GPU time.
    client = QdrantClient(url=args.qdrant_url, api_key=QDRANT_API_KEY, timeout=QDRANT_TIMEOUT)
    client.get_collections()

    exists = client.collection_exists(args.collection)
    if exists:
        # Qdrant in strict mode refuses a filter on a field without an index, so
        # a collection built before an index was added (source, effective_to_date)
        # gets it before the checks below filter on it.
        for field, schema in PAYLOAD_INDEXES.items():
            client.create_payload_index(args.collection, field_name=field, field_schema=schema)
    recreate = not args.upsert or not exists
    if recreate and exists and not args.recreate:
        others = other_source_documents(client, args.collection)
        if others:
            listed = ", ".join(f"{doc} ({n})" for doc, n in sorted(others.items()))
            raise SystemExit(
                f"{args.collection} holds {sum(others.values())} chunks not from Phap dien: {listed}.\n"
                "A rebuild would delete them. Use --upsert to merge, or --recreate to rebuild and load them again."
            )
    incoming = chunks
    if not recreate:
        chunks = apply_upsert_plan(client, args.collection, chunks)
        if not chunks:
            print("Nothing to embed.")
            link_amendments(client, args.collection, incoming)
            retire_replaced(client, args.collection, incoming)
            return
    texts = [c["text"] for c in chunks]

    embed = embed_modal if args.backend == "modal" else embed_local
    done = 0
    for batch_ids, vectors in embed(texts, args.model, max_batch_tokens, args.batch_size):
        if done == 0 and recreate:
            dim = len(vectors[0])
            print(f"Embedding dimension: {dim}")
            if client.collection_exists(args.collection):
                client.delete_collection(args.collection)
            client.create_collection(
                collection_name=args.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            for field, schema in PAYLOAD_INDEXES.items():
                client.create_payload_index(args.collection, field_name=field, field_schema=schema)
        points = [
            PointStruct(id=point_id(chunks[idx]["chunk_id"]), vector=vector.tolist(), payload=chunk_payload(chunks[idx]))
            for idx, vector in zip(batch_ids, vectors)
        ]
        upsert_with_retry(client, args.collection, points)
        done += len(batch_ids)
        print(f"  upserted {done}/{len(chunks)} (batch of {len(batch_ids)})")

    link_amendments(client, args.collection, incoming)
    retire_replaced(client, args.collection, incoming)
    print(f"Done. Qdrant dashboard: {args.qdrant_url}/dashboard#/collections/{args.collection}")


if __name__ == "__main__":
    main()
