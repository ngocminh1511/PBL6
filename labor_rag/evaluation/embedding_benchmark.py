"""Benchmark three sentence-embedding models on the Lao dong chunks (schema v5).

The benchmark deliberately measures vector retrieval only.  Neo4j and the LLM
stages are kept out so that the effect of the embedding model is measured
directly.  Each model has its own Qdrant collection ``<prefix>_<model>``.

A run normally targets a frozen benchmark version (benchmark_version.py,
docs/BENCHMARK.md): the chunks, questions and collection prefix come from
benchmarks/<dataset_id>/manifest.json, and the run stops if the data no longer
matches it.  Results go to results/<dataset_id>/<testset>/<run_id>/.

Run from the repository root:

    python -m labor_rag.evaluation.benchmark_version freeze --dataset lao_dong_v5 --testset v1 \
        --questions labor_rag/evaluation/benchmark_questions.jsonl
    python -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1 --validate-only
    python -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1 --model bge

Without --benchmark it is an ad-hoc run on --chunks/--questions, written to
results/adhoc/<run_id>/.

Gold labels are ``relevance: {mapc: grade}`` with grades 1-3.  Results are
grouped by mapc (best part wins) before scoring, so a split Dieu counts once.
Binary metrics count a Dieu as relevant from ``--min-grade`` (default 2:
grade 1 only gives context, annotation/GUIDELINES.md); nDCG uses every grade.

Metrics (k = 1, 5, 10; definitions as in NitiBench, EMNLP 2025):
  HitRate@k    share of questions with at least one relevant Dieu in the top k
  Recall@k     relevant Dieu found in the top k / all relevant Dieu (micro)
  MultiHit@k   share of questions with every relevant Dieu in the top k
  MRR@10       1 / rank of the first relevant Dieu
  nDCG@10      graded, gain 2^grade - 1
Each comes with a 95% bootstrap confidence interval over questions (metrics.csv).
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable, Iterable

import numpy as np
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from labor_rag.config import EVALUATION_DIR, LAO_DONG_DATASET_ID, LAO_DONG_DIR, RESULTS_DIR, ROOT_DIR
from labor_rag.ingest.batching import DEFAULT_MAX_BATCH_TOKENS, length_batches
from labor_rag.ingest.chunk_schema import point_id

load_dotenv()

DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_QUESTIONS = EVALUATION_DIR / "benchmark_questions.jsonl"
DEFAULT_RESULTS = RESULTS_DIR
DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
BATCH_SIZE = 64
# Parts of one Dieu collapse into one result, so fetch extra hits.
OVERFETCH = 2
DEFAULT_MIN_GRADE = 2
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 0
CUTOFFS = (1, 5, 10)


MODELS: list[dict[str, str]] = [
    {
        "key": "bkai",
        "model": "bkai-foundation-models/vietnamese-bi-encoder",
        "collection": "legal_ld_v5_bkai",
    },
    {
        "key": "bge",
        "model": "BAAI/bge-m3",
        "collection": "legal_ld_v5_bge",
    },
    {
        "key": "mpnet",
        "model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "collection": "legal_ld_v5_mpnet",
    },
]


COLLECTION_RE = re.compile(r"^legal_[a-z0-9_]+_(bkai|bge|mpnet)$")
DEFAULT_COLLECTION_PREFIX = "legal_ld_v5"
# Reported metrics, in column order.  Recall@1 equals HitRate@1 for single-gold
# questions and adds little, so it is left out.
METRICS = [
    "HitRate@1",
    "HitRate@5",
    "HitRate@10",
    "Recall@5",
    "Recall@10",
    "MultiHit@5",
    "MultiHit@10",
    "MRR@10",
    "nDCG@10",
]


def with_collection_prefix(specs: list[dict[str, str]], prefix: str) -> list[dict[str, str]]:
    """Give each model its own collection under ``prefix`` (legal_ld_v5_bkai, ...)."""

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


def validate_questions(
    chunks: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    min_grade: float = DEFAULT_MIN_GRADE,
) -> list[str]:
    """Every problem with the gold labels of ``questions`` against ``chunks``."""

    errors: list[str] = []
    chunk_ids = [str(chunk.get("chunk_id") or "") for chunk in chunks]
    if len(set(chunk_ids)) != len(chunk_ids) or any(not chunk_id for chunk_id in chunk_ids):
        errors.append("Chunks must have unique, non-empty chunk_id values")
    # Gold labels are mapc; every part of a split Dieu carries the same one.
    mapc_set = {str(chunk["mapc"]) for chunk in chunks if chunk.get("mapc")}

    for question in questions:
        question_id = str(question.get("id", "<missing-id>"))
        text = question.get("question")
        relevance = question.get("relevance")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{question_id}: question must be a non-empty string")
        if not isinstance(relevance, dict) or not relevance:
            errors.append(f"{question_id}: relevance must be a non-empty object")
            continue
        has_relevant = False
        for mapc, grade in relevance.items():
            if mapc not in mapc_set:
                errors.append(f"{question_id}: unknown gold mapc {mapc}")
            elif "://" in mapc:
                # The repeated codes get their node URI as mapc (KNOWN_ISSUES 5),
                # which is not stable across versions.
                errors.append(f"{question_id}: gold {mapc} has no stable mapc (repeated Dieu code)")
            try:
                grade_number = float(grade)
            except (TypeError, ValueError):
                errors.append(f"{question_id}: relevance for {mapc} is not numeric")
                continue
            if grade_number not in {1.0, 2.0, 3.0}:
                errors.append(f"{question_id}: relevance for {mapc} must be 1, 2, or 3")
            if grade_number >= min_grade:
                has_relevant = True
        if not has_relevant:
            errors.append(f"{question_id}: needs at least one gold Dieu with grade >= {min_grade:g}")

    ids = [str(question.get("id", "")) for question in questions]
    if len(set(ids)) != len(ids):
        errors.append("Question ids must be unique")
    return errors


def load_and_validate_dataset(
    chunks_path: Path = DEFAULT_CHUNKS,
    questions_path: Path = DEFAULT_QUESTIONS,
    min_grade: float = DEFAULT_MIN_GRADE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load chunks/questions and validate every gold MAPC before querying."""

    chunks = read_jsonl(chunks_path)
    questions = read_jsonl(questions_path)
    if not chunks:
        raise ValueError(f"No chunks found in {chunks_path}")
    errors = validate_questions(chunks, questions, min_grade)
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


def _text_digest(text: Any) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8")).hexdigest()


def _payload_for_chunk(chunk: dict[str, Any], model_key: str, model_id: str, dataset_id: str) -> dict[str, Any]:
    return {
        **chunk,
        "dataset_id": chunk.get("dataset_id", dataset_id),
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


def _collection_has_expected_chunks(
    client: QdrantClient,
    collection: str,
    expected: dict[str, str],
) -> bool:
    """True if the collection holds exactly these chunk_ids with this text.

    ``expected`` maps chunk_id to a digest of its text: a collection with the
    same ids but older text (re-projected chunks) is not reused.
    """

    found: dict[str, str] = {}
    offset: Any = None
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=256,
            with_payload=["chunk_id", "text"],
            with_vectors=False,
        )
        for point in points:
            if point.payload and point.payload.get("chunk_id") is not None:
                found[str(point.payload["chunk_id"])] = _text_digest(point.payload.get("text"))
        if offset is None:
            break
    return found == expected


def _index_chunks(
    client: QdrantClient,
    collection: str,
    chunks: list[dict[str, Any]],
    model: SentenceTransformer,
    model_key: str,
    model_id: str,
    dataset_id: str,
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
        points = [
            PointStruct(
                id=point_id(chunks[index]["chunk_id"]),
                vector=_as_vector_list(vector),
                payload=_payload_for_chunk(chunks[index], model_key, model_id, dataset_id),
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
    dataset_id: str = LAO_DONG_DATASET_ID,
) -> dict[str, Any]:
    """Create/rebuild one isolated legal_* collection or safely reuse it."""

    collection = model_spec["collection"]
    if not COLLECTION_RE.match(collection) or collection == "labor_dieu":
        raise ValueError(f"Refusing to index unapproved collection: {collection}")

    expected = {str(chunk["chunk_id"]): _text_digest(chunk.get("text")) for chunk in chunks}
    info = _get_collection_info(client, collection)
    points_count = int(getattr(info, "points_count", 0) or 0) if info else 0
    reusable = (
        not rebuild
        and info is not None
        and points_count == len(chunks)
        and _collection_dimension(info) == dimension
        and _collection_has_expected_chunks(client, collection, expected)
    )
    if reusable:
        return {
            "action": "reused",
            "index_time_seconds": 0.0,
            "indexed_points": points_count,
            "dimension": dimension,
        }

    # legal_ld_v5_bge is also the chatbot's collection, so a rebuilt one gets
    # the same payload indexes as embed_and_index creates.
    from labor_rag.ingest.embed_and_index import PAYLOAD_INDEXES

    # Delete/create only the approved legal_* collection.  Using the
    # explicit API avoids Qdrant's deprecated recreate_collection wrapper.
    if info is not None:
        client.delete_collection(collection_name=collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
    )
    for field, schema in PAYLOAD_INDEXES.items():
        client.create_payload_index(collection, field_name=field, field_schema=schema)
    index_time, indexed_points = _index_chunks(
        client=client,
        collection=collection,
        chunks=chunks,
        model=model,
        model_key=model_spec["key"],
        model_id=model_spec["model"],
        dataset_id=dataset_id,
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
    hits = _query_points(client, collection, vector, top_k * OVERFETCH)
    search_ms = (time.perf_counter() - search_started) * 1000

    # One result per Dieu (mapc): hits come best first, so the first part seen
    # carries the Dieu's score and later parts are dropped.
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        payload = hit.payload or {}
        mapc = payload.get("mapc")
        if mapc is None or str(mapc) in seen:
            continue
        seen.add(str(mapc))
        results.append(
            {
                "rank": len(results) + 1,
                "mapc": str(mapc),
                "chunk_id": payload.get("chunk_id"),
                "score": round(float(hit.score), 8),
                "ten": payload.get("ten", ""),
            }
        )
        if len(results) == top_k:
            break
    return {
        "results": results,
        "encode_latency_ms": encode_ms,
        "search_latency_ms": search_ms,
        "total_latency_ms": encode_ms + search_ms,
    }


def _relevant(relevance: dict[str, Any], min_grade: float) -> set[str]:
    return {str(mapc) for mapc, grade in relevance.items() if float(grade) >= min_grade}


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
    min_grade: float = DEFAULT_MIN_GRADE,
) -> dict[str, Any]:
    """Per-question values; ``found_at_k`` / ``n_relevant`` feed the micro Recall."""

    relevant = _relevant(relevance, min_grade)
    ranked = [result["mapc"] for result in results]
    first_rank = next((rank for rank, mapc in enumerate(ranked[:10], start=1) if mapc in relevant), None)
    row: dict[str, Any] = {"n_relevant": len(relevant), "first_relevant_rank": first_rank}
    for k in CUTOFFS:
        found = len(relevant & set(ranked[:k]))
        row[f"found_at_{k}"] = found
        row[f"hit_at_{k}"] = int(found > 0)
        row[f"multi_hit_at_{k}"] = int(found == len(relevant))
    row["mrr_at_10"] = 1.0 / first_rank if first_rank is not None else 0.0
    row["ndcg_at_10"] = _ndcg_at_k(results, relevance, 10)
    return row


# Each metric as a function of a block of per-question rows, so one function
# gives both the point estimate and every bootstrap resample.
METRIC_FUNCTIONS: dict[str, Callable[[dict[str, np.ndarray]], float]] = {
    **{f"HitRate@{k}": (lambda c, k=k: float(c[f"hit_at_{k}"].mean())) for k in CUTOFFS},
    **{f"Recall@{k}": (lambda c, k=k: float(c[f"found_at_{k}"].sum() / c["n_relevant"].sum())) for k in (5, 10)},
    **{f"MultiHit@{k}": (lambda c, k=k: float(c[f"multi_hit_at_{k}"].mean())) for k in (5, 10)},
    "MRR@10": lambda c: float(c["mrr_at_10"].mean()),
    "nDCG@10": lambda c: float(c["ndcg_at_10"].mean()),
}
METRIC_COLUMNS = ["n_relevant", "mrr_at_10", "ndcg_at_10"] + [
    f"{name}_at_{k}" for k in CUTOFFS for name in ("found", "hit", "multi_hit")
]


def aggregate_metrics(
    rows: list[dict[str, Any]],
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, dict[str, float]]:
    """{metric: {value, ci_low, ci_high}}: 95% percentile bootstrap over questions."""

    columns = {name: np.array([float(row[name]) for row in rows]) for name in METRIC_COLUMNS}
    values = {metric: METRIC_FUNCTIONS[metric](columns) for metric in METRICS}
    draws: dict[str, list[float]] = {metric: [] for metric in METRICS}
    rng = np.random.default_rng(seed)
    for _ in range(samples):
        index = rng.integers(0, len(rows), size=len(rows))
        resampled = {name: column[index] for name, column in columns.items()}
        for metric in METRICS:
            draws[metric].append(METRIC_FUNCTIONS[metric](resampled))
    output: dict[str, dict[str, float]] = {}
    for metric, value in values.items():
        low, high = (float(x) for x in np.percentile(draws[metric], [2.5, 97.5])) if samples else (value, value)
        output[metric] = {"value": round(value, 6), "ci_low": round(low, 6), "ci_high": round(high, 6)}
    return output


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
    min_grade: float = DEFAULT_MIN_GRADE,
    dataset_id: str = LAO_DONG_DATASET_ID,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    model_started = time.perf_counter()
    model = SentenceTransformer(model_spec["model"])
    model_load_seconds = time.perf_counter() - model_started
    dimension = _embedding_dimension(model)
    client = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY") or None, timeout=int(os.getenv("QDRANT_TIMEOUT", "60")))
    index_info = ensure_collection_index(
        client=client,
        model_spec=model_spec,
        chunks=chunks,
        model=model,
        dimension=dimension,
        batch_size=batch_size,
        rebuild=rebuild,
        max_batch_tokens=max_batch_tokens,
        dataset_id=dataset_id,
    )

    for question in questions[:warmup]:
        retrieve_once(client, model, model_spec["collection"], str(question["question"]), top_k)

    per_query: list[dict[str, Any]] = []
    for question in questions:
        runs = [
            retrieve_once(client, model, model_spec["collection"], str(question["question"]), top_k)
            for _ in range(repeats)
        ]
        metrics = calculate_query_metrics(runs[0]["results"], question["relevance"], min_grade)
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
                **metrics,
                "encode_latency_ms": round(median(encode_latencies), 4),
                "search_latency_ms": round(median(search_latencies), 4),
                "latency_ms": round(median(total_latencies), 4),
                "latency_runs_ms": [round(value, 4) for value in total_latencies],
            }
        )

    aggregated = aggregate_metrics(per_query, samples=bootstrap_samples)
    summary = {
        "model": model_spec["key"],
        "model_id": model_spec["model"],
        "collection": model_spec["collection"],
        "embedding_dimension": dimension,
        "max_seq_length": getattr(model, "max_seq_length", None),
        "query_count": len(per_query),
        "index_action": index_info["action"],
        "indexed_points": index_info["indexed_points"],
        **{metric: aggregated[metric]["value"] for metric in METRICS},
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
        "metrics_ci95": aggregated,
    }
    try:
        client.close()
    except AttributeError:
        pass
    del model
    gc.collect()
    return summary, per_query, metadata


def breakdown_rows(per_query: list[dict[str, Any]], samples: int = 0) -> list[dict[str, Any]]:
    """Metrics per model and per de_muc / style / tag, to see where a model fails."""

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in per_query:
        keys = [("de_muc", row.get("de_muc")), ("style", row.get("style"))]
        keys += [("tag", tag) for tag in row.get("tags") or []]
        for field, value in keys:
            if value:
                groups.setdefault((row["model"], field, str(value)), []).append(row)
    output = []
    for (model, field, value), rows in sorted(groups.items()):
        aggregated = aggregate_metrics(rows, samples=samples)
        output.append(
            {"model": model, "group_by": field, "group": value, "questions": len(rows)}
            | {metric: aggregated[metric]["value"] for metric in METRICS}
        )
    return output


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fieldnames} for row in rows)


def _git_commit() -> str | None:
    try:
        output = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        )
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT_DIR, capture_output=True, text=True).stdout
        return output.stdout.strip() + ("-dirty" if dirty.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def run_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_benchmark(
    chunks_path: Path = DEFAULT_CHUNKS,
    questions_path: Path = DEFAULT_QUESTIONS,
    results_dir: Path | None = None,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    top_k: int = 10,
    warmup: int = 3,
    repeats: int = 3,
    batch_size: int = BATCH_SIZE,
    rebuild: bool = False,
    model_keys: list[str] | None = None,
    collection_prefix: str = DEFAULT_COLLECTION_PREFIX,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
    min_grade: float = DEFAULT_MIN_GRADE,
    benchmark: dict[str, Any] | None = None,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    """Run the benchmark and write its outputs to one run directory.

    ``benchmark`` is a resolved benchmark version (benchmark_version.resolve);
    it overrides the chunks, questions and collection prefix.
    """

    if benchmark is not None:
        chunks_path = benchmark["chunks_path"]
        questions_path = benchmark["questions_path"]
        collection_prefix = benchmark["collection_prefix"]
    chunks, questions = load_and_validate_dataset(chunks_path, questions_path, min_grade)
    dataset_id = benchmark["dataset_id"] if benchmark else str(chunks[0].get("dataset_id") or LAO_DONG_DATASET_ID)
    run_id = run_id_now()
    if results_dir is None:
        results_dir = (
            DEFAULT_RESULTS / benchmark["dataset_id"] / benchmark["testset"] / run_id
            if benchmark
            else DEFAULT_RESULTS / "adhoc" / run_id
        )
    unknown = set(model_keys or []) - {spec["key"] for spec in MODELS}
    if unknown:
        raise ValueError(f"Unknown model key(s): {', '.join(sorted(unknown))}")
    selected = with_collection_prefix(
        [spec for spec in MODELS if model_keys is None or spec["key"] in model_keys], collection_prefix
    )
    if not selected:
        raise ValueError("No model selected")

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
            min_grade=min_grade,
            dataset_id=dataset_id,
            bootstrap_samples=bootstrap_samples,
        )
        summaries.append(summary)
        per_query_rows.extend(rows)
        metadata_rows.append(metadata)
        ci = metadata["metrics_ci95"]
        print(
            f"  index {summary['index_action']}; "
            + "  ".join(
                f"{metric}={ci[metric]['value']:.3f} [{ci[metric]['ci_low']:.3f}, {ci[metric]['ci_high']:.3f}]"
                for metric in ("HitRate@5", "Recall@10", "MRR@10", "nDCG@10")
            )
            + f"  median={summary['median_latency_ms']:.1f} ms"
        )

    results_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        results_dir / "summary.csv",
        summaries,
        [
            "model",
            "model_id",
            "collection",
            "embedding_dimension",
            "max_seq_length",
            "query_count",
            "index_action",
            "indexed_points",
            *METRICS,
            "mean_latency_ms",
            "median_latency_ms",
            "mean_encode_latency_ms",
            "mean_search_latency_ms",
            "index_time_seconds",
        ],
    )
    _write_csv(
        results_dir / "metrics.csv",
        [
            {"model": meta["key"], "metric": metric, **meta["metrics_ci95"][metric]}
            for meta in metadata_rows
            for metric in METRICS
        ],
        ["model", "metric", "value", "ci_low", "ci_high"],
    )
    _write_csv(
        results_dir / "breakdown.csv",
        breakdown_rows(per_query_rows),
        ["model", "group_by", "group", "questions", *METRICS],
    )
    _write_jsonl(results_dir / "per_query_results.jsonl", per_query_rows)
    run = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "benchmark": None
        if benchmark is None
        else {
            "dataset_id": benchmark["dataset_id"],
            "testset": benchmark["testset"],
            "testset_sha256": benchmark["testset_entry"]["sha256"],
            "data": benchmark["data"],
            "warnings": benchmark["warnings"],
        },
        "dataset": {
            "dataset_id": dataset_id,
            "chunks_path": str(chunks_path),
            "questions_path": str(questions_path),
            "chunk_count": len(chunks),
            "question_count": len(questions),
        },
        "config": {
            # The host only: QDRANT_URL can carry nothing secret, the API key is never written.
            "qdrant_host": qdrant_url.split("//")[-1].split("/")[0],
            "top_k": top_k,
            "warmup": warmup,
            "repeats": repeats,
            "batch_size": batch_size,
            "max_batch_tokens": max_batch_tokens,
            "rebuild": rebuild,
            "collection_prefix": collection_prefix,
            "min_grade": min_grade,
            "bootstrap_samples": bootstrap_samples,
            "neo4j_in_primary_metric": False,
        },
        "models": metadata_rows,
    }
    (results_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote benchmark outputs to {results_dir}")
    return {"summary": summaries, "per_query": per_query_rows, "metadata": run, "results_dir": results_dir}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", metavar="DATASET_ID", help="frozen benchmark version, e.g. lao_dong_v5")
    parser.add_argument("--testset", help="test set of that benchmark, e.g. v1")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="ad-hoc run only")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="ad-hoc run only")
    parser.add_argument("--results-dir", type=Path, help="default results/<dataset_id>/<testset>/<run_id>")
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--min-grade", type=float, default=DEFAULT_MIN_GRADE, help="lowest grade counted as relevant")
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAP_SAMPLES, help="bootstrap resamples for the 95%% CI")
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
        help="ad-hoc run only; a benchmark version takes it from its manifest",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate chunks and gold labels (and the benchmark version) without loading models or Qdrant",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.top_k < 10:
        raise SystemExit("--top-k must be at least 10 because the benchmark reports HitRate@10/MRR@10")

    benchmark = None
    if args.benchmark:
        from labor_rag.evaluation.benchmark_version import BenchmarkError, resolve

        if not args.testset:
            raise SystemExit("--benchmark needs --testset")
        try:
            benchmark = resolve(args.benchmark, args.testset)
        except BenchmarkError as exc:
            raise SystemExit(f"ERROR {exc}")
        for warning in benchmark["warnings"]:
            print(f"WARN  {warning}")
        chunks_path, questions_path = benchmark["chunks_path"], benchmark["questions_path"]
        print(f"Benchmark {args.benchmark}/{args.testset} (collections {benchmark['collection_prefix']}_*)")
    else:
        chunks_path, questions_path = args.chunks, args.questions
        print("Ad-hoc run: not tied to a frozen benchmark version")

    chunks, questions = load_and_validate_dataset(chunks_path, questions_path, args.min_grade)
    print(f"Validated {len(chunks)} chunks and {len(questions)} gold questions")
    if args.validate_only:
        return 0
    run_benchmark(
        chunks_path=chunks_path,
        questions_path=questions_path,
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
        min_grade=args.min_grade,
        benchmark=benchmark,
        bootstrap_samples=args.bootstrap,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
