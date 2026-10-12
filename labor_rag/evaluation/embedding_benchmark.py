"""Benchmark three sentence-embedding models on the Lao dong ontology v4 chunks.

The benchmark deliberately measures vector retrieval only.  It uses the 1,407
chunks of data/processed/lao_dong_v4, three isolated Qdrant collections, and a
manually labelled question set.  Neo4j and the LLM generation stage are kept
out of the primary metric so that the effect of the embedding model can be
measured directly.

Run from the repository root:

    python -m labor_rag.evaluation.embedding_benchmark --validate-only
    python -m labor_rag.evaluation.embedding_benchmark --rebuild \
        --questions labor_rag/evaluation/benchmark_questions_v2.jsonl \
        --results-dir labor_rag/evaluation/results/lao_dong_v2

The default question set is v1 (30 questions on 20.5) until the v2 set is
finalized.  The ``--rebuild`` flag only recreates the three ``<prefix>_*``
collections declared in ``MODELS``.
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from labor_rag.config import EVALUATION_DIR, LAO_DONG_DATASET_ID, LAO_DONG_V4_DIR
from labor_rag.ingest.batching import DEFAULT_MAX_BATCH_TOKENS, length_batches

load_dotenv()

DEFAULT_CHUNKS = LAO_DONG_V4_DIR / "chunks.jsonl"
DEFAULT_QUESTIONS = EVALUATION_DIR / "benchmark_questions.jsonl"
DEFAULT_RESULTS = EVALUATION_DIR / "results"
DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
BATCH_SIZE = 64


MODELS: list[dict[str, str]] = [
    {
        "key": "bkai",
        "model": "bkai-foundation-models/vietnamese-bi-encoder",
        "collection": "legal_ld_v4_bkai",
    },
    {
        "key": "bge",
        "model": "BAAI/bge-m3",
        "collection": "legal_ld_v4_bge",
    },
    {
        "key": "mpnet",
        "model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "collection": "legal_ld_v4_mpnet",
    },
]


COLLECTION_RE = re.compile(r"^legal_[a-z0-9_]+_(bkai|bge|mpnet)$")
DEFAULT_COLLECTION_PREFIX = "legal_ld_v4"


def with_collection_prefix(specs: list[dict[str, str]], prefix: str) -> list[dict[str, str]]:
    """Give each model its own collection under ``prefix`` (legal_ld_v4_bkai, ...)."""

    if not re.match(r"^legal_[a-z0-9_]+$", prefix):
        raise ValueError(f"Collection prefix must look like legal_<name>: {prefix!r}")
    return [{**spec, "collection": f"{prefix}_{spec['key']}"} for spec in specs]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a UTF-8 JSON Lines file and include line numbers in errors."""

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"Expected an object at {path}:{line_number}")
        rows.append(row)
    return rows


def load_and_validate_dataset(
    chunks_path: Path = DEFAULT_CHUNKS,
    questions_path: Path = DEFAULT_QUESTIONS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load chunks/questions and validate every gold MAPC before querying."""

    chunks = read_jsonl(chunks_path)
    questions = read_jsonl(questions_path)
    mapcs = [str(chunk.get("mapc", "")) for chunk in chunks]
    if not chunks:
        raise ValueError(f"No chunks found in {chunks_path}")
    if len(set(mapcs)) != len(mapcs) or any(not mapc for mapc in mapcs):
        raise ValueError("Chunks must have unique, non-empty mapc values")
    mapc_set = set(mapcs)

    errors: list[str] = []
    for question in questions:
        question_id = str(question.get("id", "<missing-id>"))
        text = question.get("question")
        relevance = question.get("relevance")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{question_id}: question must be a non-empty string")
        if not isinstance(relevance, dict) or not relevance:
            errors.append(f"{question_id}: relevance must be a non-empty object")
            continue
        valid_positive = False
        for mapc, grade in relevance.items():
            if mapc not in mapc_set:
                errors.append(f"{question_id}: unknown gold mapc {mapc}")
            try:
                grade_number = float(grade)
            except (TypeError, ValueError):
                errors.append(f"{question_id}: relevance for {mapc} is not numeric")
                continue
            if grade_number not in {1.0, 2.0, 3.0}:
                errors.append(f"{question_id}: relevance for {mapc} must be 1, 2, or 3")
            if grade_number > 0:
                valid_positive = True
        if not valid_positive:
            errors.append(f"{question_id}: must contain at least one positive gold label")

    ids = [str(question.get("id", "")) for question in questions]
    if len(set(ids)) != len(ids):
        errors.append("Question ids must be unique")
    if errors:
        raise ValueError("Gold-label validation failed:\n- " + "\n- ".join(errors))
    return chunks, questions


def _embedding_dimension(model: SentenceTransformer) -> int:
    get_dimension = getattr(model, "get_embedding_dimension", None)
    if get_dimension is None:
        get_dimension = model.get_sentence_embedding_dimension
    dimension = get_dimension()
    if dimension is None:
        raise ValueError("The embedding model did not expose a vector dimension")
    return int(dimension)


def _as_vector_list(vector: Any) -> list[float]:
    return vector.tolist() if hasattr(vector, "tolist") else [float(value) for value in vector]


def _payload_for_chunk(chunk: dict[str, Any], model_key: str, model_id: str) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id", chunk.get("mapc")),
        "mapc": chunk["mapc"],
        "uri": chunk.get("uri"),
        "ten": chunk.get("ten", ""),
        "citation": chunk.get("citation", ""),
        "breadcrumb": chunk.get("breadcrumb", ""),
        "text": chunk.get("text", ""),
        "document_uri": chunk.get("document_uri"),
        "source": chunk.get("source", "ontology_v4"),
        "dataset_id": chunk.get("dataset_id", LAO_DONG_DATASET_ID),
        "embedding_model_key": model_key,
        "embedding_model": model_id,
    }


def _collection_dimension(info: Any) -> int | None:
    try:
        vectors = info.config.params.vectors
        if hasattr(vectors, "size"):
            return int(vectors.size)
        if isinstance(vectors, dict) and len(vectors) == 1:
            return int(next(iter(vectors.values())).size)
    except (AttributeError, TypeError, StopIteration):
        return None
    return None


def _get_collection_info(client: QdrantClient, collection: str) -> Any | None:
    try:
        return client.get_collection(collection_name=collection)
    except Exception as exc:  # qdrant-client uses different exception classes across versions
        if "not found" in str(exc).lower() or "404" in str(exc):
            return None
        raise


def _collection_has_expected_mapcs(
    client: QdrantClient,
    collection: str,
    expected_mapcs: set[str],
) -> bool:
    """Check payload identity so an old same-sized collection is not reused."""

    found: set[str] = set()
    offset: Any = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=256,
            with_payload=["mapc"],
            with_vectors=False,
        )
        found.update(
            str(point.payload.get("mapc"))
            for point in points
            if point.payload and point.payload.get("mapc") is not None
        )
        if offset is None:
            break
    return found == expected_mapcs


def _index_chunks(
    client: QdrantClient,
    collection: str,
    chunks: list[dict[str, Any]],
    model: SentenceTransformer,
    model_key: str,
    model_id: str,
    batch_size: int,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
) -> tuple[float, int]:
    started = time.perf_counter()
    texts = [str(chunk.get("text", "")) for chunk in chunks]
    batches = length_batches(texts, model.tokenizer, model.max_seq_length, max_batch_tokens, batch_size)
    done = 0
    for batch in batches:
        vectors = model.encode(
            [texts[index] for index in batch],
            batch_size=len(batch),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # Point ids stay the chunk's position in the file, whatever the batch order.
        points = [
            PointStruct(
                id=index,
                vector=_as_vector_list(vector),
                payload=_payload_for_chunk(chunks[index], model_key, model_id),
            )
            for index, vector in zip(batch, vectors)
        ]
        client.upsert(collection_name=collection, points=points, wait=True)
        done += len(batch)
        print(f"  indexed {done}/{len(chunks)} into {collection} (batch of {len(batch)})")
    return time.perf_counter() - started, len(chunks)


def ensure_collection_index(
    client: QdrantClient,
    model_spec: dict[str, str],
    chunks: list[dict[str, Any]],
    model: SentenceTransformer,
    dimension: int,
    batch_size: int = BATCH_SIZE,
    rebuild: bool = False,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
) -> dict[str, Any]:
    """Create/rebuild one isolated legal_* collection or safely reuse it."""

    collection = model_spec["collection"]
    if not COLLECTION_RE.match(collection) or collection == "labor_dieu":
        raise ValueError(f"Refusing to index unapproved collection: {collection}")

    expected_mapcs = {str(chunk["mapc"]) for chunk in chunks}
    info = _get_collection_info(client, collection)
    points_count = int(getattr(info, "points_count", 0) or 0) if info else 0
    reusable = (
        not rebuild
        and info is not None
        and points_count == len(chunks)
        and _collection_dimension(info) == dimension
        and _collection_has_expected_mapcs(client, collection, expected_mapcs)
    )
    if reusable:
        return {
            "action": "reused",
            "index_time_seconds": 0.0,
            "indexed_points": points_count,
            "dimension": dimension,
        }

    # Delete/create only the approved ontology-v4 collection.  Using the
    # explicit API avoids Qdrant's deprecated recreate_collection wrapper.
    if info is not None:
        client.delete_collection(collection_name=collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
    )
    index_time, indexed_points = _index_chunks(
        client=client,
        collection=collection,
        chunks=chunks,
        model=model,
        model_key=model_spec["key"],
        model_id=model_spec["model"],
        batch_size=batch_size,
        max_batch_tokens=max_batch_tokens,
    )
    return {
        "action": "rebuilt",
        "index_time_seconds": round(index_time, 6),
        "indexed_points": indexed_points,
        "dimension": dimension,
    }


def _query_points(client: QdrantClient, collection: str, vector: list[float], top_k: int) -> list[Any]:
    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        return list(response.points)
    return list(client.search(collection_name=collection, query_vector=vector, limit=top_k, with_payload=True))


def retrieve_once(
    client: QdrantClient,
    model: SentenceTransformer,
    collection: str,
    question: str,
    top_k: int,
) -> dict[str, Any]:
    encode_started = time.perf_counter()
    vector = _as_vector_list(model.encode(question, normalize_embeddings=True, show_progress_bar=False))
    encode_ms = (time.perf_counter() - encode_started) * 1000

    search_started = time.perf_counter()
    hits = _query_points(client, collection, vector, top_k)
    search_ms = (time.perf_counter() - search_started) * 1000

    results: list[dict[str, Any]] = []
    for rank, hit in enumerate(hits, start=1):
        payload = hit.payload or {}
        mapc = payload.get("mapc")
        if mapc is None:
            continue
        results.append(
            {
                "rank": rank,
                "mapc": str(mapc),
                "score": round(float(hit.score), 8),
                "ten": payload.get("ten", ""),
                "citation": payload.get("citation", ""),
            }
        )
    return {
        "results": results,
        "encode_latency_ms": encode_ms,
        "search_latency_ms": search_ms,
        "total_latency_ms": encode_ms + search_ms,
    }


def _first_relevant_rank(results: list[dict[str, Any]], relevance: dict[str, Any], top_k: int) -> int | None:
    gold = {str(mapc) for mapc, grade in relevance.items() if float(grade) > 0}
    for result in results[:top_k]:
        if result["mapc"] in gold:
            return int(result["rank"])
    return None


def _ndcg_at_k(results: list[dict[str, Any]], relevance: dict[str, Any], top_k: int) -> float:
    grades = {str(mapc): float(grade) for mapc, grade in relevance.items()}
    dcg = sum(
        (2 ** grades[result["mapc"]] - 1) / math.log2(result["rank"] + 1)
        for result in results[:top_k]
        if result["mapc"] in grades
    )
    ideal_grades = sorted((grade for grade in grades.values() if grade > 0), reverse=True)[:top_k]
    ideal_dcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1))
    return dcg / ideal_dcg if ideal_dcg else 0.0


def calculate_query_metrics(
    results: list[dict[str, Any]],
    relevance: dict[str, Any],
    top_k: int,
) -> dict[str, float | int | None]:
    gold = {str(mapc) for mapc, grade in relevance.items() if float(grade) > 0}
    first_rank = _first_relevant_rank(results, relevance, top_k)
    return {
        "recall_at_1": int(any(result["mapc"] in gold for result in results[:1])),
        "recall_at_5": int(any(result["mapc"] in gold for result in results[:5])),
        "recall_at_10": int(any(result["mapc"] in gold for result in results[:10])),
        "first_relevant_rank": first_rank,
        "mrr_at_10": 1.0 / first_rank if first_rank is not None else 0.0,
        "ndcg_at_10": _ndcg_at_k(results, relevance, min(top_k, 10)),
    }


def evaluate_model(
    model_spec: dict[str, str],
    chunks: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    qdrant_url: str,
    top_k: int,
    warmup: int,
    repeats: int,
    batch_size: int,
    rebuild: bool,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    model_started = time.perf_counter()
    model = SentenceTransformer(model_spec["model"])
    model_load_seconds = time.perf_counter() - model_started
    dimension = _embedding_dimension(model)
    client = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY") or None)
    index_info = ensure_collection_index(
        client=client,
        model_spec=model_spec,
        chunks=chunks,
        model=model,
        dimension=dimension,
        batch_size=batch_size,
        rebuild=rebuild,
        max_batch_tokens=max_batch_tokens,
    )

    for question in questions[:warmup]:
        retrieve_once(client, model, model_spec["collection"], str(question["question"]), top_k)

    per_query: list[dict[str, Any]] = []
    for question in questions:
        runs = [
            retrieve_once(client, model, model_spec["collection"], str(question["question"]), top_k)
            for _ in range(repeats)
        ]
        metrics = calculate_query_metrics(
            results=runs[0]["results"],
            relevance=question["relevance"],
            top_k=top_k,
        )
        total_latencies = [float(run["total_latency_ms"]) for run in runs]
        encode_latencies = [float(run["encode_latency_ms"]) for run in runs]
        search_latencies = [float(run["search_latency_ms"]) for run in runs]
        per_query.append(
            {
                "model": model_spec["key"],
                "model_id": model_spec["model"],
                "collection": model_spec["collection"],
                "question_id": question["id"],
                "question": question["question"],
                "de_muc": question.get("de_muc"),
                "style": question.get("style"),
                "tags": question.get("tags", []),
                "gold_relevance": question["relevance"],
                "top_k_results": runs[0]["results"],
                "first_relevant_rank": metrics["first_relevant_rank"],
                "recall_at_1": metrics["recall_at_1"],
                "recall_at_5": metrics["recall_at_5"],
                "recall_at_10": metrics["recall_at_10"],
                "mrr_at_10": metrics["mrr_at_10"],
                "ndcg_at_10": metrics["ndcg_at_10"],
                "encode_latency_ms": round(median(encode_latencies), 4),
                "search_latency_ms": round(median(search_latencies), 4),
                "latency_ms": round(median(total_latencies), 4),
                "latency_runs_ms": [round(value, 4) for value in total_latencies],
            }
        )

    summary = {
        "model": model_spec["key"],
        "model_id": model_spec["model"],
        "collection": model_spec["collection"],
        "embedding_dimension": dimension,
        "query_count": len(per_query),
        "index_action": index_info["action"],
        "indexed_points": index_info["indexed_points"],
        "Recall@1": round(mean(float(row["recall_at_1"]) for row in per_query), 6),
        "Recall@5": round(mean(float(row["recall_at_5"]) for row in per_query), 6),
        "Recall@10": round(mean(float(row["recall_at_10"]) for row in per_query), 6),
        "MRR@10": round(mean(float(row["mrr_at_10"]) for row in per_query), 6),
        "nDCG@10": round(mean(float(row["ndcg_at_10"]) for row in per_query), 6),
        "mean_latency_ms": round(mean(float(row["latency_ms"]) for row in per_query), 4),
        "median_latency_ms": round(median(float(row["latency_ms"]) for row in per_query), 4),
        "mean_encode_latency_ms": round(mean(float(row["encode_latency_ms"]) for row in per_query), 4),
        "mean_search_latency_ms": round(mean(float(row["search_latency_ms"]) for row in per_query), 4),
        "index_time_seconds": index_info["index_time_seconds"],
    }
    metadata = {
        **model_spec,
        "embedding_dimension": dimension,
        "model_load_time_seconds": round(model_load_seconds, 6),
        "index": index_info,
        "query_config": {"top_k": top_k, "warmup": warmup, "repeats": repeats},
    }
    try:
        client.close()
    except AttributeError:
        pass
    del model
    gc.collect()
    return summary, per_query, metadata


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_benchmark(
    chunks_path: Path = DEFAULT_CHUNKS,
    questions_path: Path = DEFAULT_QUESTIONS,
    results_dir: Path = DEFAULT_RESULTS,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    top_k: int = 10,
    warmup: int = 3,
    repeats: int = 3,
    batch_size: int = BATCH_SIZE,
    rebuild: bool = False,
    model_keys: list[str] | None = None,
    collection_prefix: str = DEFAULT_COLLECTION_PREFIX,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
) -> dict[str, Any]:
    """Run the benchmark and write summary/per-query/metadata outputs."""

    chunks, questions = load_and_validate_dataset(chunks_path, questions_path)
    selected = with_collection_prefix(
        [spec for spec in MODELS if model_keys is None or spec["key"] in model_keys], collection_prefix
    )
    if not selected:
        raise ValueError("No model selected")
    unknown = set(model_keys or []) - {spec["key"] for spec in MODELS}
    if unknown:
        raise ValueError(f"Unknown model key(s): {', '.join(sorted(unknown))}")

    summaries: list[dict[str, Any]] = []
    per_query_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    for model_spec in selected:
        print(f"\n[{model_spec['key']}] loading {model_spec['model']}")
        summary, rows, metadata = evaluate_model(
            model_spec=model_spec,
            chunks=chunks,
            questions=questions,
            qdrant_url=qdrant_url,
            top_k=top_k,
            warmup=warmup,
            repeats=repeats,
            batch_size=batch_size,
            rebuild=rebuild,
            max_batch_tokens=max_batch_tokens,
        )
        summaries.append(summary)
        per_query_rows.extend(rows)
        metadata_rows.append(metadata)
        print(
            f"  Recall@10={summary['Recall@10']:.3f} "
            f"MRR@10={summary['MRR@10']:.3f} "
            f"median={summary['median_latency_ms']:.2f} ms"
        )

    results_dir.mkdir(parents=True, exist_ok=True)
    summary_path = results_dir / "summary.csv"
    fieldnames = [
        "model",
        "model_id",
        "collection",
        "embedding_dimension",
        "query_count",
        "index_action",
        "indexed_points",
        "Recall@1",
        "Recall@5",
        "Recall@10",
        "MRR@10",
        "nDCG@10",
        "mean_latency_ms",
        "median_latency_ms",
        "mean_encode_latency_ms",
        "mean_search_latency_ms",
        "index_time_seconds",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fieldnames} for row in summaries)

    _write_jsonl(results_dir / "per_query_results.jsonl", per_query_rows)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "chunks_path": str(chunks_path),
            "questions_path": str(questions_path),
            "chunk_count": len(chunks),
            "question_count": len(questions),
            "dataset_id": chunks[0].get("dataset_id", LAO_DONG_DATASET_ID),
        },
        "config": {
            "qdrant_url": qdrant_url,
            "top_k": top_k,
            "warmup": warmup,
            "repeats": repeats,
            "batch_size": batch_size,
            "max_batch_tokens": max_batch_tokens,
            "rebuild": rebuild,
            "collection_prefix": collection_prefix,
            "neo4j_in_primary_metric": False,
        },
        "models": metadata_rows,
    }
    (results_dir / "model_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nWrote benchmark outputs to {results_dir}")
    return {"summary": summaries, "per_query": per_query_rows, "metadata": metadata}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Max chunks per indexing batch")
    parser.add_argument(
        "--max-batch-tokens",
        type=int,
        default=DEFAULT_MAX_BATCH_TOKENS,
        help="Token budget per indexing batch (batch size x longest chunk); raise it on a large GPU",
    )
    parser.add_argument("--model", dest="model_keys", action="append", choices=[spec["key"] for spec in MODELS])
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Recreate only <prefix>_bkai/<prefix>_bge/<prefix>_mpnet before indexing",
    )
    parser.add_argument(
        "--collection-prefix",
        default=DEFAULT_COLLECTION_PREFIX,
        help="Qdrant collection prefix; use a new one per chunk set (e.g. legal_ld_v4 for lao_dong_v4)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate chunks and manually labelled questions without loading models or Qdrant",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.top_k < 10:
        raise SystemExit("--top-k must be at least 10 because the benchmark reports Recall@10/MRR@10")
    chunks, questions = load_and_validate_dataset(args.chunks, args.questions)
    print(f"Validated {len(chunks)} chunks and {len(questions)} gold questions")
    if args.validate_only:
        return 0
    run_benchmark(
        chunks_path=args.chunks,
        questions_path=args.questions,
        results_dir=args.results_dir,
        qdrant_url=args.qdrant_url,
        top_k=args.top_k,
        warmup=args.warmup,
        repeats=args.repeats,
        batch_size=args.batch_size,
        rebuild=args.rebuild,
        model_keys=args.model_keys,
        collection_prefix=args.collection_prefix,
        max_batch_tokens=args.max_batch_tokens,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
