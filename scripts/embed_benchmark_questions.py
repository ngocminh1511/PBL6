"""Embed benchmark questions (benchmark_questions_v3.jsonl) via Modal GPU and index to Qdrant Cloud.
Collection: benchmark_questions_v3_bge
"""

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")
os.environ["HF_HOME"] = r"D:\PBL6_v2\hf_cache"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
sys.stdout.reconfigure(encoding="utf-8")

import modal
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

QUESTIONS_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "benchmark_questions_v3.jsonl"
COLLECTION_NAME = os.getenv("QUESTIONS_COLLECTION", "benchmark_questions_v3_bge")
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
MODAL_APP = "labor-rag-embed"
MODAL_MAX_BATCH_TOKENS = 32768
BATCH_SIZE = 64

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "60"))


def point_id_from_qid(qid: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"labor_rag:question:{qid}"))


def main():
    print("=" * 70)
    print(" EMBEDDING BENCHMARK QUESTIONS VIA MODAL GPU TO QDRANT CLOUD")
    print(f" Target Collection: {COLLECTION_NAME}")
    print(f" Source: {QUESTIONS_PATH}")
    print(f" Model: {MODEL_NAME}")
    print("=" * 70)

    # 1. Load questions
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = [json.loads(line.strip()) for line in f if line.strip()]
    print(f"Loaded {len(questions)} questions.")

    texts = [q["question"] for q in questions]

    # 2. Embed on Modal GPU
    print(f"\nSending {len(texts)} questions to Modal GPU ({MODAL_APP})...")
    embedder = modal.Cls.from_name(MODAL_APP, "Embedder")(model_name=MODEL_NAME)
    res = embedder.embed.remote(texts, MODAL_MAX_BATCH_TOKENS, BATCH_SIZE)
    dim = res["dim"]
    vectors = np.frombuffer(res["vectors"], dtype=np.float32).reshape(len(texts), dim)
    print(f"Embedded successfully on Modal! Dimension: {dim}, Vectors: {len(vectors)}")

    # 3. Connect to Qdrant Cloud
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=QDRANT_TIMEOUT)

    # 4. Create collection if not exists / recreate
    if client.collection_exists(COLLECTION_NAME):
        print(f"Collection {COLLECTION_NAME} exists. Deleting to recreate clean collection...")
        client.delete_collection(COLLECTION_NAME)

    print(f"Creating collection {COLLECTION_NAME} (dim={dim}, distance=Cosine)...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    # Payload indexes
    indexes = {
        "id": PayloadSchemaType.KEYWORD,
        "category": PayloadSchemaType.KEYWORD,
        "style": PayloadSchemaType.KEYWORD,
        "retrieval_type": PayloadSchemaType.KEYWORD,
        "de_muc": PayloadSchemaType.KEYWORD,
    }
    for field, schema in indexes.items():
        client.create_payload_index(COLLECTION_NAME, field_name=field, field_schema=schema)

    # 5. Upsert points
    points = [
        PointStruct(
            id=point_id_from_qid(q["id"]),
            vector=vectors[i].tolist(),
            payload=q,
        )
        for i, q in enumerate(questions)
    ]

    print(f"Upserting {len(points)} question points into {COLLECTION_NAME}...")
    client.upsert(collection_name=COLLECTION_NAME, points=points)

    cnt = client.count(COLLECTION_NAME).count
    print(f"\nSuccess! Collection {COLLECTION_NAME} now has {cnt} points on Qdrant Cloud.")
    print(f"Dashboard: {QDRANT_URL}/dashboard#/collections/{COLLECTION_NAME}")


if __name__ == "__main__":
    main()
