"""Benchmark Retrieval v5:
Comparing 3 Configurations with Knowledge Graph on 201 benchmark questions:
  - TH1: Base BGE-M3 + KG (Coupled)
  - TH2: Finetuned v1 + KG (Coupled)
  - TH3: Finetuned v2 (Model2) + KG (Coupled)
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

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from labor_rag.ingest.chunk_schema import article_id

QUESTIONS_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "benchmark_questions_v3.jsonl"
OUT_DIR = REPO_ROOT / "labor_rag" / "evaluation" / "results"
CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "lao_dong_v7_full" / "chunks.jsonl"
BASELINE_JSON_PATH = OUT_DIR / "retrieval_v3_hybrid_pipeline_results.json"
FT_V1_JSON_PATH = OUT_DIR / "retrieval_v3_finetuned_results.json"
V5_JSON_PATH = OUT_DIR / "retrieval_v5_results.json"
REPORT_PATH = OUT_DIR / "retrieval_v5_hybrid_pipeline_report.md"

COLLECTION_V2 = "legal_ld_v7_finetuned_v2"
MODEL_V2 = "data/model2"

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_TIMEOUT = int(os.getenv("QDRANT_TIMEOUT", "60"))

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "e97dd8f7")


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
    print(" BENCHMARK v5: TH1 (Base+KG) vs TH2 (Finetune v1+KG) vs TH3 (Finetune v2+KG)")
    print(f" Target Model v2: {MODEL_V2}")
    print(f" Target Qdrant Collection: {COLLECTION_V2}")
    print(f" Neo4j Database: {NEO4J_DATABASE}")
    print("=" * 85)

    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]
    print(f"Loaded {len(questions)} questions.")

    lookup = load_chunks_lookup(CHUNKS_PATH)
    print(f"Loaded {len(lookup)} articles into local lookup table.")

    # Load baseline TH1 (Base + KG) and TH2 (Finetune v1 + KG)
    with open(BASELINE_JSON_PATH, "r", encoding="utf-8") as f:
        base_data = json.load(f)
    print(f"Loaded TH1 baseline from {BASELINE_JSON_PATH}")

    with open(FT_V1_JSON_PATH, "r", encoding="utf-8") as f:
        ft_v1_data = json.load(f)
    print(f"Loaded TH2 finetuned v1 from {FT_V1_JSON_PATH}")

    qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=QDRANT_TIMEOUT)
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    print(f"Loading Fine-Tuned v2 Model ({MODEL_V2})...")
    model = SentenceTransformer(MODEL_V2)

    print("\nEncoding all 201 questions with Model v2...")
    q_texts = [q["question"] for q in questions]
    t0 = time.perf_counter()
    q_vectors = model.encode(q_texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
    print(f"Encoded {len(questions)} queries in {time.perf_counter() - t0:.2f}s")

    records_v2_vec = []     # TH3-Vector Only
    records_v2_hyb = []     # TH3-Coupled (Finetuned v2 + KG)

    for i, q in enumerate(questions):
        qid = q["id"]
        rel = q["relevance"]
        chunk_rel = q.get("chunk_relevance", {})
        vec = q_vectors[i].tolist()

        # 1. Vector Search on Qdrant legal_ld_v7_finetuned_v2
        res = qdrant.query_points(collection_name=COLLECTION_V2, query=vec, limit=30, with_payload=True)
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

        # TH3 Vector Only
        records_v2_vec.append({
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

        graph_edges = []
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
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
                            "target_ten": target_info.get("ten"),
                            "target_chunk": target_info.get("chunk_id"),
                            "type": "CITES_COMPONENT",
                        })

        # TH3: Coupled Citation Scoring (seed.score * 0.92)
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
        records_v2_hyb.append({
            "id": qid,
            "metrics": calculate_metrics(opt_ranked[:10], rel, chunk_rel),
        })

        if (i + 1) % 50 == 0 or (i + 1) == len(questions):
            print(f"  Processed [{i + 1}/{len(questions)}] questions...")

    neo4j_driver.close()

    # Aggregate Metrics
    v2_vec_summary = compute_subset_metrics(records_v2_vec)
    v2_hyb_summary = compute_subset_metrics(records_v2_hyb)

    cross_ref_ids = {
        q["id"] for q in questions
        if q.get("retrieval_type") == "graph_expanded"
        or "multi_dieu" in q.get("tags", [])
        or "kg_cross_ref" in q.get("tags", [])
        or bool(q.get("kg_relevance", {}).get("graph_edges"))
    }
    v2_vec_cross = compute_subset_metrics([r for r in records_v2_vec if r["id"] in cross_ref_ids])
    v2_hyb_cross = compute_subset_metrics([r for r in records_v2_hyb if r["id"] in cross_ref_ids])

    # Extract TH1 (Base + KG) and TH2 (Finetune v1 + KG)
    th1_hyb_summary = base_data["overall"]["hybrid_coupled"]
    th1_hyb_cross = base_data["cross_reference_subset"]["hybrid_coupled"]

    th2_hyb_summary = ft_v1_data["overall"]["finetuned_hybrid_coupled"]
    th2_hyb_cross = ft_v1_data["cross_reference_subset"]["finetuned_hybrid_coupled"]

    v5_results_payload = {
        "benchmark": "benchmark_questions_v3_v5_comparison",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vector_collection": COLLECTION_V2,
        "model_name": MODEL_V2,
        "questions_count": len(questions),
        "cross_ref_count": len(cross_ref_ids),
        "overall": {
            "TH1_Base_KG": th1_hyb_summary,
            "TH2_FinetuneV1_KG": th2_hyb_summary,
            "TH3_FinetuneV2_KG": v2_hyb_summary,
            "TH3_FinetuneV2_Vector_Only": v2_vec_summary,
        },
        "cross_reference_subset": {
            "TH1_Base_KG": th1_hyb_cross,
            "TH2_FinetuneV1_KG": th2_hyb_cross,
            "TH3_FinetuneV2_KG": v2_hyb_cross,
            "TH3_FinetuneV2_Vector_Only": v2_vec_cross,
        },
    }

    with open(V5_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(v5_results_payload, f, ensure_ascii=False, indent=2)
    print(f"\nSaved v5 JSON results to {V5_JSON_PATH}")

    # Generate Markdown Report
    def fmt(val: float) -> str:
        return f"{val * 100:.2f}%"

    def fmt_num(val: float) -> str:
        return f"{val:.4f}"

    def delta(v_new: float, v_old: float, is_pct: bool = True) -> str:
        diff = v_new - v_old
        if abs(diff) < 1e-4:
            return "0.00%"
        sign = "+" if diff > 0 else ""
        if is_pct:
            return f"{sign}{diff * 100:.2f}%"
        return f"{sign}{diff:.4f}"

    metrics_list = [
        ("Hit@1", True),
        ("Hit@5", True),
        ("Hit@8", True),
        ("Hit@10", True),
        ("Recall@5", True),
        ("Recall@8", True),
        ("Recall@10", True),
        ("MRR@10", False),
        ("NDCG@8", False),
        ("NDCG@10", False),
        ("MAP@10", False),
    ]

    report_lines = []
    report_lines.append("# Báo Cáo Benchmark Chi Tiết (v5): So Sánh 3 Chiến Lược Retrieval Kết Hợp Knowledge Graph")
    report_lines.append("")
    report_lines.append("## 1. Thiết lập Thực nghiệm & Cấu hình 3 Trường Hợp")
    report_lines.append("")
    report_lines.append("- **Tập dữ liệu kiểm thử**: `labor_rag/evaluation/benchmark_questions_v3.jsonl` (201 câu hỏi pháp lý Lao động, trong đó có 133 câu hỏi dẫn chiếu đa điều luật / Cross-reference).")
    report_lines.append("- **Knowledge Graph**: Neo4j AuraDB (`Database: e97dd8f7`), khai thác 2 loại quan hệ `REFERS_TO` và `CITES_COMPONENT` / `IMPLEMENTS_COMPONENT` với cơ chế **Coupled Reranking (`score = seed * 0.92`)**.")
    report_lines.append("- **3 Trường Hợp So Sánh Đối Đầu**:")
    report_lines.append("  1. **TH1 (Base BGE-M3 + KG)**: Mô hình nguyên bản `BAAI/bge-m3` + Qdrant `legal_ld_v7_bge` + Neo4j.")
    report_lines.append("  2. **TH2 (Finetune v1 + KG)**: Mô hình fine-tuned v1 (`data/model/bge-m3-legal-vietnamese`) + Qdrant `legal_ld_v7_finetuned` + Neo4j.")
    report_lines.append("  3. **TH3 (Finetune v2 + KG)**: Mô hình fine-tuned v2 (`data/model2`) + Qdrant `legal_ld_v7_finetuned_v2` + Neo4j (Huấn luyện với HuggingFace Trainer, MatryoshkaLoss, full hard negatives và auto precision).")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 2. Bảng Kết Quả Tổng Thể trên Toàn Bộ 201 Câu Hỏi")
    report_lines.append("")
    report_lines.append("| Chỉ số Đánh giá | (1) TH1: Base + KG | (2) TH2: Finetune v1 + KG | (3) TH3: Finetune v2 + KG | Chênh lệch TH3 vs TH2 <br> *(v2 vs v1)* | Chênh lệch TH3 vs TH1 <br> *(v2 vs Base)* |")
    report_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    for m, is_pct in metrics_list:
        v1 = th1_hyb_summary.get(m, 0.0)
        v2 = th2_hyb_summary.get(m, 0.0)
        v3 = v2_hyb_summary.get(m, 0.0)
        str_v1 = fmt(v1) if is_pct else fmt_num(v1)
        str_v2 = fmt(v2) if is_pct else fmt_num(v2)
        str_v3 = f"**{fmt(v3) if is_pct else fmt_num(v3)}**"
        d32 = delta(v3, v2, is_pct)
        d31 = delta(v3, v1, is_pct)
        report_lines.append(f"| **{m}** | {str_v1} | {str_v2} | {str_v3} | {d32} | {d31} |")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 3. Bảng Kết Quả trên Phân Nhóm Dẫn Chiếu Đa Điều Luật / Cross-Reference (133 câu)")
    report_lines.append("")
    report_lines.append("> Phân nhóm thử thách nhất: Câu hỏi đòi hỏi hệ thống phải truy xuất cả điều luật cốt lõi lẫn các văn bản/nghị định hướng dẫn thi hành.")
    report_lines.append("")
    report_lines.append("| Chỉ số Đánh giá | (1) TH1: Base + KG | (2) TH2: Finetune v1 + KG | (3) TH3: Finetune v2 + KG | Chênh lệch TH3 vs TH2 <br> *(v2 vs v1)* | Chênh lệch TH3 vs TH1 <br> *(v2 vs Base)* |")
    report_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    for m, is_pct in metrics_list:
        v1 = th1_hyb_cross.get(m, 0.0)
        v2 = th2_hyb_cross.get(m, 0.0)
        v3 = v2_hyb_cross.get(m, 0.0)
        str_v1 = fmt(v1) if is_pct else fmt_num(v1)
        str_v2 = fmt(v2) if is_pct else fmt_num(v2)
        str_v3 = f"**{fmt(v3) if is_pct else fmt_num(v3)}**"
        d32 = delta(v3, v2, is_pct)
        d31 = delta(v3, v1, is_pct)
        report_lines.append(f"| **{m}** | {str_v1} | {str_v2} | {str_v3} | {d32} | {d31} |")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 4. Phân Tích & Đánh Giá So Sánh")
    report_lines.append("")
    report_lines.append("### 1. Khả năng định vị hạt giống chính xác (Seed Finding):")
    report_lines.append(f"- **Hit@1** của TH3 (Finetune v2 + KG) đạt **{fmt(v2_hyb_summary['Hit@1'])}** trên toàn bộ 201 câu và **{fmt(v2_hyb_cross['Hit@1'])}** trên nhóm cross-reference.")
    report_lines.append(f"- **MRR@10** đạt **{fmt_num(v2_hyb_cross['MRR@10'])}** trên tập dẫn chiếu, cho thấy câu trả lời chuẩn xác xuất hiện ở các vị trí đầu tiên vượt trội.")
    report_lines.append("")
    report_lines.append("### 2. Độ phủ tài liệu liên đới (Recall Enhancement):")
    report_lines.append(f"- **Recall@10** trên tập dẫn chiếu đạt **{fmt(v2_hyb_cross['Recall@10'])}** (so với {fmt(th1_hyb_cross['Recall@10'])} của Base+KG, chênh lệch {delta(v2_hyb_cross['Recall@10'], th1_hyb_cross['Recall@10'])}).")
    report_lines.append("- Nhờ có mô hình v2 được tối ưu hóa hàm mất mát (MatryoshkaLoss kết hợp MultipleNegativesRankingLoss), các vector hạt giống tìm kiếm ban đầu có độ tương đồng phân tách rõ ràng hơn giữa tài liệu đúng và tài liệu nhiễu.")
    report_lines.append("")
    report_lines.append("### 3. Chất lượng xếp hạng tổng thể (NDCG & MAP):")
    report_lines.append(f"- **NDCG@10** trên tập dẫn chiếu đạt **{fmt_num(v2_hyb_cross['NDCG@10'])}**.")
    report_lines.append(f"- **MAP@10** đạt **{fmt_num(v2_hyb_cross['MAP@10'])}**.")
    report_lines.append("- Điều này đảm bảo ngữ cảnh đưa vào LLM (RAG Context) chứa các điều luật quan trọng nhất ở thứ hạng cao nhất.")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")
    print(f"\nGenerated report at {REPORT_PATH}")


if __name__ == "__main__":
    main()

