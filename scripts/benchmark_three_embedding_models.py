"""Benchmark Retrieval: Comparing 3 Base Embedding Models with Knowledge Graph
Models compared:
  1. BAAI/bge-m3 (1024 dims)
  2. bkai-foundation-models/vietnamese-bi-encoder (768 dims)
  3. sentence-transformers/paraphrase-multilingual-mpnet-base-v2 (768 dims)
All evaluated on labor_rag/evaluation/benchmark_questions_v3.jsonl (201 questions, 133 cross-reference)
under Base Vector Only vs Base + KG (Coupled Reranking, score = seed * 0.92).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")
os.environ["HF_HOME"] = r"D:\PBL6_v2\hf_cache"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
sys.stdout.reconfigure(encoding="utf-8")

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from labor_rag.ingest.chunk_schema import article_id

QUESTIONS_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "benchmark_questions_v3.jsonl"
OUT_DIR = REPO_ROOT / "labor_rag" / "evaluation" / "results"
CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "lao_dong_v7_full" / "chunks.jsonl"
KG_NODES_PATH = REPO_ROOT / "data" / "processed" / "lao_dong_v7_full" / "kg_nodes.jsonl"
KG_EDGES_PATH = REPO_ROOT / "data" / "processed" / "lao_dong_v7_full" / "kg_edges.jsonl"

BGE_JSON_PATH = OUT_DIR / "retrieval_v3_hybrid_pipeline_results.json"
BKAI_JSON_PATH = OUT_DIR / "retrieval_bkai_vs_bge_results.json"
THREE_MODELS_JSON = OUT_DIR / "retrieval_three_models_comparison_results.json"
REPORT_PATH = OUT_DIR / "retrieval_three_models_comparison_report.md"

COLLECTION_MPNET = "legal_ld_v7_mpnet"
MODEL_MPNET = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "60"))

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "e97dd8f7")


class KnowledgeGraphEngine:
    """Graph traversal engine with Neo4j driver and self-contained JSONL fallback."""

    def __init__(self, uri: str, user: str, password: str, database: str, nodes_path: Path, edges_path: Path):
        self.use_neo4j = False
        self.driver = None
        self.database = database

        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session(database=database) as session:
                session.run("RETURN 1").consume()
            self.driver = driver
            self.use_neo4j = True
            print("Successfully connected to Neo4j AuraDB.")
        except Exception as e:
            print(f"Neo4j AuraDB unreachable ({e}). Loading Knowledge Graph locally from JSONL...")
            self._load_local_graph(nodes_path, edges_path)

    def _load_local_graph(self, nodes_path: Path, edges_path: Path):
        t0 = time.perf_counter()
        self.dieu_nodes: dict[str, dict[str, Any]] = {}
        self.source_components: dict[str, dict[str, str]] = {}

        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                n = json.loads(line)
                lbl = n.get("label")
                if lbl == "Dieu":
                    self.dieu_nodes[n["id"]] = {
                        "ten": n.get("ten", ""),
                        "content_available": bool(n.get("content_available", False)),
                    }
                elif lbl == "SourceComponent":
                    doc = n.get("document_id")
                    art = n.get("article_number")
                    if doc and art:
                        self.source_components[n["id"]] = {
                            "document_id": doc,
                            "article_number": str(art),
                        }

        self.refers_to: dict[str, list[tuple[str, str]]] = {}
        self.cites_comp: dict[tuple[str, str], list[tuple[str, str]]] = {}

        with open(edges_path, "r", encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                t = e.get("type")
                src = e.get("source")
                tgt = e.get("target")

                if t == "REFERS_TO" and src in self.dieu_nodes and tgt in self.dieu_nodes and src != tgt:
                    if self.dieu_nodes[tgt]["content_available"]:
                        self.refers_to.setdefault(src, []).append((tgt, self.dieu_nodes[tgt]["ten"]))

                elif t in ("CITES_COMPONENT", "IMPLEMENTS_COMPONENT") and src in self.source_components and tgt in self.source_components:
                    s_comp = self.source_components[src]
                    t_comp = self.source_components[tgt]
                    s_key = (s_comp["document_id"], s_comp["article_number"])
                    t_val = (t_comp["document_id"], t_comp["article_number"])
                    if s_key != t_val:
                        self.cites_comp.setdefault(s_key, []).append(t_val)

        print(f"Loaded local Knowledge Graph ({len(self.dieu_nodes)} Dieu, {len(self.refers_to)} REFERS_TO, {len(self.cites_comp)} CITES) in {time.perf_counter() - t0:.2f}s")

    def query_graph(self, seeds: list[str], ref_keys: list[dict[str, Any]], vec_deduped: list[dict[str, Any]], lookup: dict) -> list[dict[str, Any]]:
        graph_edges = []
        if self.use_neo4j and self.driver:
            with self.driver.session(database=self.database) as session:
                if seeds:
                    cypher_refers = """
                    UNWIND $seeds AS s_id
                    MATCH (a:Dieu {id: s_id})-[:REFERS_TO]->(b:Dieu {content_available: true})
                    WHERE b.id <> a.id
                    RETURN DISTINCT a.id AS seed, b.id AS target_mapc, b.ten AS target_ten
                    LIMIT 15
                    """
                    for r in session.run(cypher_refers, seeds=seeds):
                        graph_edges.append({
                            "seed": r["seed"],
                            "target_mapc": r["target_mapc"],
                            "target_ten": r["target_ten"],
                            "target_chunk": "",
                            "type": "REFERS_TO",
                        })

                if ref_keys:
                    cypher_cites = """
                    UNWIND $keys AS key
                    MATCH (c:SourceComponent {document_id: key.document_id, article_number: key.meta_dieu})
                    MATCH (c)-[r:CITES_COMPONENT|IMPLEMENTS_COMPONENT]->(t:SourceComponent)
                    WHERE t.article_number IS NOT NULL AND NOT (t.document_id = key.document_id AND t.article_number = key.meta_dieu)
                    RETURN DISTINCT key.index AS seed_idx, t.document_id AS target_doc, t.article_number AS target_dieu
                    LIMIT 15
                    """
                    for r in session.run(cypher_cites, keys=ref_keys):
                        target_doc = r["target_doc"]
                        target_dieu = str(r["target_dieu"])
                        target_info = lookup.get((target_doc, target_dieu), {})
                        if target_info:
                            seed_item = vec_deduped[r["seed_idx"]]
                            graph_edges.append({
                                "seed": seed_item.get("mapc"),
                                "target_mapc": target_info.get("mapc"),
                                "target_chunk": target_info.get("chunk_id"),
                                "target_ten": target_info.get("ten"),
                                "type": "CITES_COMPONENT",
                            })
        else:
            # Local in-memory graph traversal
            seen_refers = set()
            for s_id in seeds:
                for tgt_mapc, tgt_ten in self.refers_to.get(s_id, []):
                    pair = (s_id, tgt_mapc)
                    if pair not in seen_refers:
                        seen_refers.add(pair)
                        graph_edges.append({
                            "seed": s_id,
                            "target_mapc": tgt_mapc,
                            "target_ten": tgt_ten,
                            "target_chunk": "",
                            "type": "REFERS_TO",
                        })
                        if len(graph_edges) >= 15:
                            break
                if len(graph_edges) >= 15:
                    break

            seen_cites = set()
            cites_count = 0
            for key in ref_keys:
                s_key = (key["document_id"], str(key["meta_dieu"]))
                for t_doc, t_art in self.cites_comp.get(s_key, []):
                    pair = (key["index"], t_doc, t_art)
                    if pair not in seen_cites:
                        seen_cites.add(pair)
                        target_info = lookup.get((t_doc, t_art), {})
                        if target_info:
                            seed_item = vec_deduped[key["index"]]
                            graph_edges.append({
                                "seed": seed_item.get("mapc"),
                                "target_mapc": target_info.get("mapc"),
                                "target_chunk": target_info.get("chunk_id"),
                                "target_ten": target_info.get("ten"),
                                "type": "CITES_COMPONENT",
                            })
                            cites_count += 1
                            if cites_count >= 15:
                                break
                if cites_count >= 15:
                    break

        return graph_edges

    def close(self):
        if self.driver:
            self.driver.close()


def load_chunks_lookup(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    lookup = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            doc_id = c.get("document_id")
            dieu = c.get("meta_dieu")
            if doc_id and dieu:
                key = (doc_id, str(dieu))
                if key not in lookup:
                    lookup[key] = {
                        "mapc": c.get("mapc"),
                        "chunk_id": article_id(c.get("chunk_id", "")),
                        "ten": c.get("ten", ""),
                    }
    return lookup


def calculate_metrics(results: list[dict[str, Any]], relevance: dict[str, Any], chunk_relevance: dict[str, Any] | None = None) -> dict[str, Any]:
    gold_mapcs = {str(m): float(g) for m, g in relevance.items() if float(g) > 0}
    gold_chunks = {article_id(str(c)): float(g) for c, g in (chunk_relevance or {}).items() if float(g) > 0}

    total_relevant = len(gold_mapcs) if gold_mapcs else len(gold_chunks)
    if total_relevant == 0:
        return {}

    first_rank = None
    retrieved_relevant_5 = 0
    retrieved_relevant_8 = 0
    retrieved_relevant_10 = 0

    for idx, res in enumerate(results[:10], start=1):
        m = res.get("mapc")
        c = article_id(res.get("chunk_id", ""))

        is_hit = False
        if m and m in gold_mapcs:
            is_hit = True
        elif c and c in gold_chunks:
            is_hit = True

        if is_hit:
            if first_rank is None:
                first_rank = idx
            if idx <= 5:
                retrieved_relevant_5 += 1
            if idx <= 8:
                retrieved_relevant_8 += 1
            retrieved_relevant_10 += 1

    hit_at_1 = 1.0 if (len(results) >= 1 and (results[0].get("mapc") in gold_mapcs or article_id(results[0].get("chunk_id", "")) in gold_chunks)) else 0.0
    hit_at_5 = 1.0 if any((r.get("mapc") in gold_mapcs or article_id(r.get("chunk_id", "")) in gold_chunks) for r in results[:5]) else 0.0
    hit_at_8 = 1.0 if any((r.get("mapc") in gold_mapcs or article_id(r.get("chunk_id", "")) in gold_chunks) for r in results[:8]) else 0.0
    hit_at_10 = 1.0 if any((r.get("mapc") in gold_mapcs or article_id(r.get("chunk_id", "")) in gold_chunks) for r in results[:10]) else 0.0

    recall_at_5 = min(1.0, retrieved_relevant_5 / total_relevant)
    recall_at_8 = min(1.0, retrieved_relevant_8 / total_relevant)
    recall_at_10 = min(1.0, retrieved_relevant_10 / total_relevant)
    mrr_at_10 = (1.0 / first_rank) if first_rank is not None and first_rank <= 10 else 0.0

    def ndcg_k(k: int) -> float:
        dcg = 0.0
        for idx, r in enumerate(results[:k], start=1):
            m = r.get("mapc")
            c = article_id(r.get("chunk_id", ""))
            grade = gold_mapcs.get(m, gold_chunks.get(c, 0.0))
            if grade > 0:
                dcg += (2 ** grade - 1) / math.log2(idx + 1)

        ideal_grades = sorted(list(gold_mapcs.values()) or list(gold_chunks.values()), reverse=True)[:k]
        idcg = sum((2 ** g - 1) / math.log2(rank + 1) for rank, g in enumerate(ideal_grades, start=1))
        return (dcg / idcg) if idcg > 0 else 0.0

    ap = 0.0
    num_rel = 0
    for idx, res in enumerate(results[:10], start=1):
        m = res.get("mapc")
        c = article_id(res.get("chunk_id", ""))
        if (m and m in gold_mapcs) or (c and c in gold_chunks):
            num_rel += 1
            ap += num_rel / idx
    map_at_10 = (ap / total_relevant) if total_relevant > 0 else 0.0

    return {
        "hit_at_1": hit_at_1,
        "hit_at_5": hit_at_5,
        "hit_at_8": hit_at_8,
        "hit_at_10": hit_at_10,
        "recall_at_5": recall_at_5,
        "recall_at_8": recall_at_8,
        "recall_at_10": recall_at_10,
        "mrr_at_10": mrr_at_10,
        "ndcg_at_5": ndcg_k(5),
        "ndcg_at_8": ndcg_k(8),
        "ndcg_at_10": ndcg_k(10),
        "map_at_10": map_at_10,
        "first_rank": first_rank,
    }


def compute_subset_metrics(query_records: list[dict[str, Any]]) -> dict[str, float]:
    if not query_records:
        return {}
    return {
        "count": len(query_records),
        "Hit@1": round(mean(r["metrics"]["hit_at_1"] for r in query_records), 4),
        "Hit@5": round(mean(r["metrics"]["hit_at_5"] for r in query_records), 4),
        "Hit@8": round(mean(r["metrics"]["hit_at_8"] for r in query_records), 4),
        "Hit@10": round(mean(r["metrics"]["hit_at_10"] for r in query_records), 4),
        "Recall@5": round(mean(r["metrics"]["recall_at_5"] for r in query_records), 4),
        "Recall@8": round(mean(r["metrics"]["recall_at_8"] for r in query_records), 4),
        "Recall@10": round(mean(r["metrics"]["recall_at_10"] for r in query_records), 4),
        "MRR@10": round(mean(r["metrics"]["mrr_at_10"] for r in query_records), 4),
        "NDCG@5": round(mean(r["metrics"]["ndcg_at_5"] for r in query_records), 4),
        "NDCG@8": round(mean(r["metrics"]["ndcg_at_8"] for r in query_records), 4),
        "NDCG@10": round(mean(r["metrics"]["ndcg_at_10"] for r in query_records), 4),
        "MAP@10": round(mean(r["metrics"]["map_at_10"] for r in query_records), 4),
    }


def main():
    print("=" * 85)
    print(" BENCHMARK: BGE-M3 vs BKAI vs Multilingual-MPNet with Knowledge Graph")
    print(f" Target Model: {MODEL_MPNET}")
    print(f" Target Qdrant Collection: {COLLECTION_MPNET}")
    print("=" * 85)

    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]
    print(f"Loaded {len(questions)} questions.")

    lookup = load_chunks_lookup(CHUNKS_PATH)
    print(f"Loaded {len(lookup)} articles into local lookup table.")

    # Load baseline BGE-M3 and BKAI
    with open(BGE_JSON_PATH, "r", encoding="utf-8") as f:
        bge_data = json.load(f)
    print(f"Loaded BGE-M3 baseline from {BGE_JSON_PATH}")

    with open(BKAI_JSON_PATH, "r", encoding="utf-8") as f:
        bkai_data = json.load(f)
    print(f"Loaded BKAI baseline from {BKAI_JSON_PATH}")

    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=QDRANT_TIMEOUT)
    graph_engine = KnowledgeGraphEngine(
        NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE, KG_NODES_PATH, KG_EDGES_PATH
    )

    print(f"Loading MPNet Model ({MODEL_MPNET})...")
    model = SentenceTransformer(MODEL_MPNET)

    print("\nEncoding all 201 questions with MPNet model...")
    q_texts = [q["question"] for q in questions]
    t0 = time.perf_counter()
    q_vectors = model.encode(q_texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
    print(f"Encoded {len(questions)} queries in {time.perf_counter() - t0:.2f}s")

    records_mpnet_vec = []     # MPNet Vector Only
    records_mpnet_hyb = []     # MPNet + KG Coupled

    for i, q in enumerate(questions):
        qid = q["id"]
        rel = q["relevance"]
        chunk_rel = q.get("chunk_relevance", {})
        vec = q_vectors[i].tolist()

        # 1. Vector Search on Qdrant legal_ld_v7_mpnet
        res = qdrant.query_points(collection_name=COLLECTION_MPNET, query=vec, limit=30, with_payload=True)
        vec_deduped = []
        seen_vec = set()
        for p in res.points:
            pay = p.payload or {}
            m = pay.get("mapc")
            cid = article_id(pay.get("chunk_id", ""))
            key = cid or m
            if not key or key in seen_vec:
                continue
            seen_vec.add(key)
            vec_deduped.append({
                "mapc": m,
                "chunk_id": cid,
                "score": float(p.score),
                "ten": pay.get("ten", ""),
                "document_id": pay.get("document_id", ""),
                "meta_dieu": pay.get("meta_dieu", ""),
                "source": "vector",
            })

        # MPNet Vector Only
        records_mpnet_vec.append({
            "id": qid,
            "metrics": calculate_metrics(vec_deduped[:10], rel, chunk_rel),
        })

        # 2. Graph Traversal from Top Seeds
        seeds = [v["mapc"] for v in vec_deduped[:5] if v.get("mapc")]
        ref_keys = [
            {"index": idx, "document_id": v["document_id"], "meta_dieu": str(v["meta_dieu"])}
            for idx, v in enumerate(vec_deduped[:5])
            if v.get("document_id") and v.get("meta_dieu")
        ]

        graph_edges = graph_engine.query_graph(seeds, ref_keys, vec_deduped, lookup)

        # Coupled Citation Scoring (seed.score * 0.92)
        candidates_opt = {v["chunk_id"] or v["mapc"]: dict(v) for v in vec_deduped[:10]}
        seed_scores = {v["mapc"]: v["score"] for v in vec_deduped[:3] if v.get("mapc")}

        for g in graph_edges:
            k = g["target_chunk"] or g["target_mapc"]
            seed_s = seed_scores.get(g["seed"], vec_deduped[0]["score"] * 0.90 if vec_deduped else 0.70)
            coupled_s = round(seed_s * 0.92, 4)
            if k in candidates_opt:
                if coupled_s > candidates_opt[k]["score"]:
                    candidates_opt[k]["score"] = coupled_s
                    candidates_opt[k]["source"] = "hybrid:vector+kg"
            else:
                candidates_opt[k] = {
                    "mapc": g["target_mapc"],
                    "chunk_id": g["target_chunk"],
                    "score": coupled_s,
                    "ten": g["target_ten"],
                    "source": f"graph:{g['type']}",
                }
        opt_ranked = sorted(candidates_opt.values(), key=lambda x: x["score"], reverse=True)
        records_mpnet_hyb.append({
            "id": qid,
            "metrics": calculate_metrics(opt_ranked[:10], rel, chunk_rel),
        })

        if (i + 1) % 50 == 0 or (i + 1) == len(questions):
            print(f"  Processed [{i + 1}/{len(questions)}] questions...")

    graph_engine.close()

    # Aggregate Metrics
    mpnet_vec_summary = compute_subset_metrics(records_mpnet_vec)
    mpnet_hyb_summary = compute_subset_metrics(records_mpnet_hyb)

    cross_ref_ids = {
        q["id"] for q in questions
        if q.get("retrieval_type") == "graph_expanded"
        or "multi_dieu" in q.get("tags", [])
        or "kg_cross_ref" in q.get("tags", [])
        or bool(q.get("kg_relevance", {}).get("graph_edges"))
    }
    mpnet_vec_cross = compute_subset_metrics([r for r in records_mpnet_vec if r["id"] in cross_ref_ids])
    mpnet_hyb_cross = compute_subset_metrics([r for r in records_mpnet_hyb if r["id"] in cross_ref_ids])

    # Extract Baseline TH1 BGE-M3 & BKAI
    bge_vec_summary = bge_data["overall"]["vector_only"]
    bge_hyb_summary = bge_data["overall"]["hybrid_coupled"]
    bge_vec_cross = bge_data["cross_reference_subset"]["vector_only"]
    bge_hyb_cross = bge_data["cross_reference_subset"]["hybrid_coupled"]

    bkai_vec_summary = bkai_data["overall"]["BKAI_Vector_Only"]
    bkai_hyb_summary = bkai_data["overall"]["BKAI_Base_KG"]
    bkai_vec_cross = bkai_data["cross_reference_subset"]["BKAI_Vector_Only"]
    bkai_hyb_cross = bkai_data["cross_reference_subset"]["BKAI_Base_KG"]

    three_models_payload = {
        "benchmark": "benchmark_three_embedding_models",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "questions_count": len(questions),
        "cross_ref_count": len(cross_ref_ids),
        "overall": {
            "BGE_Vector_Only": bge_vec_summary,
            "BGE_Base_KG": bge_hyb_summary,
            "BKAI_Vector_Only": bkai_vec_summary,
            "BKAI_Base_KG": bkai_hyb_summary,
            "MPNet_Vector_Only": mpnet_vec_summary,
            "MPNet_Base_KG": mpnet_hyb_summary,
        },
        "cross_reference_subset": {
            "BGE_Vector_Only": bge_vec_cross,
            "BGE_Base_KG": bge_hyb_cross,
            "BKAI_Vector_Only": bkai_vec_cross,
            "BKAI_Base_KG": bkai_hyb_cross,
            "MPNet_Vector_Only": mpnet_vec_cross,
            "MPNet_Base_KG": mpnet_hyb_cross,
        },
    }

    with open(THREE_MODELS_JSON, "w", encoding="utf-8") as f:
        json.dump(three_models_payload, f, ensure_ascii=False, indent=2)
    print(f"\nSaved 3-models comparison JSON to {THREE_MODELS_JSON}")

    # Console display
    def fmt(val: float) -> str:
        return f"{val * 100:.2f}%"

    print("\n" + "=" * 90)
    print(" KẾT QUẢ SO SÁNH 3 MÔ HÌNH EMBEDDING TRƯỜNG HỢP (BASE + KG) TRÊN 201 CÂU HỎI:")
    print("=" * 90)
    print(f" Hit@1:     BGE-M3: {fmt(bge_hyb_summary['Hit@1'])}  |  BKAI: {fmt(bkai_hyb_summary['Hit@1'])}  |  MPNet: {fmt(mpnet_hyb_summary['Hit@1'])}")
    print(f" Hit@5:     BGE-M3: {fmt(bge_hyb_summary['Hit@5'])}  |  BKAI: {fmt(bkai_hyb_summary['Hit@5'])}  |  MPNet: {fmt(mpnet_hyb_summary['Hit@5'])}")
    print(f" Recall@5:  BGE-M3: {fmt(bge_hyb_summary['Recall@5'])}  |  BKAI: {fmt(bkai_hyb_summary['Recall@5'])}  |  MPNet: {fmt(mpnet_hyb_summary['Recall@5'])}")
    print(f" Recall@10: BGE-M3: {fmt(bge_hyb_summary['Recall@10'])}  |  BKAI: {fmt(bkai_hyb_summary['Recall@10'])}  |  MPNet: {fmt(mpnet_hyb_summary['Recall@10'])}")
    print(f" MRR@10:    BGE-M3: {bge_hyb_summary['MRR@10']:.4f}  |  BKAI: {bkai_hyb_summary['MRR@10']:.4f}  |  MPNet: {mpnet_hyb_summary['MRR@10']:.4f}")
    print(f" NDCG@10:   BGE-M3: {bge_hyb_summary['NDCG@10']:.4f}  |  BKAI: {bkai_hyb_summary['NDCG@10']:.4f}  |  MPNet: {mpnet_hyb_summary['NDCG@10']:.4f}")
    print(f" MAP@10:    BGE-M3: {bge_hyb_summary['MAP@10']:.4f}  |  BKAI: {bkai_hyb_summary['MAP@10']:.4f}  |  MPNet: {mpnet_hyb_summary['MAP@10']:.4f}")
    print("=" * 90)


if __name__ == "__main__":
    main()

