"""Find reference targets missing from vector retrieval; read-only, without an LLM.

This is a discovery audit, not an answer-quality benchmark. Candidate targets
must still be read to decide whether they are necessary for the question.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from labor_rag.ingest.chunk_schema import article_id
from labor_rag.retrieval.hybrid_retrieve import in_force, khoans_of


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(args):
    from qdrant_client import QdrantClient
    from labor_rag.ingest.embed_and_index import embed_local, embed_modal

    started = time.perf_counter()
    questions = jsonl(args.questions)
    corpus = ROOT / "data/processed" / args.dataset
    chunks = jsonl(corpus / "chunks.jsonl")
    nodes = {node["id"]: node for node in jsonl(corpus / "kg_nodes.jsonl")}
    indexed_articles = {article_id(c["chunk_id"]) for c in chunks}
    references = {}
    for edge in jsonl(corpus / "kg_edges.jsonl"):
        if edge["type"] not in {"CITES_COMPONENT", "IMPLEMENTS_COMPONENT"}:
            continue
        source, target = nodes.get(edge["source"], {}), nodes.get(edge["target"], {})
        if not all(n.get("document_id") and n.get("article_number") for n in [source, target]):
            continue
        src_id = f"{source['document_id']}:d{source['article_number']}"
        dst_id = f"{target['document_id']}:d{target['article_number']}"
        if src_id == dst_id or dst_id not in indexed_articles:
            continue
        references.setdefault(src_id, []).append({
            "source_node_id": edge["source"], "target_node_id": edge["target"],
            "source_article": src_id, "source_clause": source.get("clause_number"),
            "relation": edge["type"], "target_article": dst_id,
            "target_clause": target.get("clause_number"), "target_point": target.get("point_number"),
            "target_text": target.get("text") or "",
        })

    backend = os.getenv("QUERY_EMBEDDING_BACKEND") or os.getenv("EMBEDDING_BACKEND", "local")
    model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    collection = os.getenv("QDRANT_COLLECTION", "legal_ld_v5_bge")
    encode = embed_modal if backend == "modal" else embed_local
    print(f"Embedding {len(questions)} discovery questions, backend={backend}, model={model}", flush=True)
    vectors = {}
    for indices, batch in encode([q["question"] for q in questions], model, 32768, 64):
        vectors.update({index: vector.tolist() for index, vector in zip(indices, batch)})
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                          api_key=os.getenv("QDRANT_API_KEY") or None, timeout=30)
    as_of = date.fromisoformat(args.as_of)

    def search(index):
        question = questions[index]
        points = client.query_points(collection_name=collection, query=vectors[index],
            query_filter=in_force(as_of), limit=50, with_payload=True, with_vectors=False).points
        unique, seen = [], set()
        for raw_rank, point in enumerate(points, 1):
            payload = point.payload
            key = article_id(payload["chunk_id"])
            if key not in seen:
                unique.append({"article_id": key, "chunk_id": payload["chunk_id"],
                               "rank": len(unique) + 1, "raw_rank": raw_rank,
                               "score": point.score, "title": payload.get("ten"),
                               "meta_khoan": payload.get("meta_khoan"), "text": payload.get("text", "")})
                seen.add(key)
        # Match HybridRetriever.vector_search: overfetch 2*k then deduplicate.
        seeds = [hit for hit in unique if hit["raw_rank"] <= args.top_k * 2][:args.top_k]
        seed_ids = {hit["article_id"] for hit in seeds}
        ranks = {hit["article_id"]: hit["rank"] for hit in unique}
        expected = set(question.get("expected_targets", []))
        additions, seen_edges = [], set()
        for seed in seeds:
            clauses = khoans_of(seed["meta_khoan"])
            for edge in references.get(seed["article_id"], []):
                if clauses is not None and edge["source_clause"] is not None and edge["source_clause"] not in clauses:
                    continue
                if edge["target_article"] in seed_ids:
                    continue
                signature = (edge["source_node_id"], edge["target_node_id"], edge["relation"])
                if signature in seen_edges:
                    continue
                seen_edges.add(signature)
                additions.append({**edge, "source_vector_rank": seed["rank"],
                                  "target_vector_rank_in_top50_raw": ranks.get(edge["target_article"]),
                                  "expected_target": edge["target_article"] in expected})
        return {**question, "vector_top_k": seeds,
                "raw_top_k": [{"chunk_id": point.payload["chunk_id"], "score": point.score} for point in points[:args.top_k]],
                "ranks_in_top50_raw": {hit["article_id"]: hit["rank"] for hit in unique},
                "candidate_additions": additions,
                "expected_missing_targets_found_by_reference": sorted({e["target_article"] for e in additions if e["expected_target"]})}

    try:
        results = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = {pool.submit(search, i): i for i in range(len(questions))}
            for future in as_completed(pending):
                index = pending[future]
                try:
                    results[index] = future.result()
                except Exception as exc:
                    results[index] = {**questions[index], "error_type": type(exc).__name__}
                if len(results) % 10 == 0 or len(results) == len(questions):
                    print(f"Searched {len(results)}/{len(questions)} questions", flush=True)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(), "as_of": args.as_of,
            "dataset": args.dataset, "collection": collection, "embedding_model": model,
            "embedding_backend": backend, "top_k": args.top_k, "llm_used": False,
            "corpus_sha256": hashlib.sha256((corpus / "chunks.jsonl").read_bytes()).hexdigest(),
            "note": "Discovery only. Edges here come from the local ontology projection; selected cases must be confirmed against live Neo4j and Qdrant. Expected labels nominate candidates, not proof of answer relevance. No LLM or benchmark gold labels are modified.",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "questions": [results[i] for i in range(len(questions))],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        candidates = [q for q in report["questions"] if q.get("expected_missing_targets_found_by_reference")]
        print(f"Candidate questions with missing expected targets: {len(candidates)}", flush=True)
        for row in candidates:
            print(row["id"], row["expected_missing_targets_found_by_reference"], flush=True)
        print(f"Saved discovery report: {args.output}", flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", default="lao_dong_v5")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--as-of", default=date.today().isoformat())
    try:
        run(parser.parse_args())
    except Exception as exc:
        print(f"Audit stopped: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
