import os
import sys
import json
import math
import time
from statistics import mean
from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# Redirect Hugging Face cache to D: drive
os.environ.setdefault("HF_HOME", r"D:\PBL6_v2\hf_cache")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "legal_ld_v5_bge")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "labor_rag_pw")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
model = SentenceTransformer(MODEL_NAME)

# Load first 20 questions
with open("labor_rag/evaluation/results/benchmark_questions_v3.jsonl", "r", encoding="utf-8") as f:
    questions = [json.loads(line) for line in f]

print(f"Total questions in v3: {len(questions)}")

# Test a cross reference question like kg_ref_01 or ld_ref_145
sample_q = next(q for q in questions if q["id"] == "ld_ref_145")
print("Testing query:", sample_q["question"])
print("Relevance gold:", sample_q["relevance"])

vec = model.encode(sample_q["question"], normalize_embeddings=True).tolist()
hits = qdrant.query_points(collection_name=COLLECTION_NAME, query=vec, limit=20).points

best = {}
for h in hits:
    mapc = h.payload.get("mapc")
    if mapc and mapc not in best:
        best[mapc] = {
            "mapc": mapc,
            "chunk_id": h.payload.get("chunk_id"),
            "score": h.score,
            "ten": h.payload.get("ten", "")
        }

vec_top10 = list(best.values())[:10]
print("\n--- TH1 (Vector Only Top 5) ---")
for idx, r in enumerate(vec_top10[:5], 1):
    gold = sample_q["relevance"].get(r["mapc"], 0)
    print(f"  Rank {idx}: {r['mapc']} (score={r['score']:.4f}) | gold={gold} | {r['ten']}")

# Graph Expansion (REFERS_TO only, no siblings)
seed_mapcs = [r["mapc"] for r in vec_top10[:3]]
with driver.session() as s:
    cypher = """
    UNWIND $seeds AS seed_id
    MATCH (a:Dieu {id: seed_id})-[:REFERS_TO]->(b:Dieu {content_available: true})
    WHERE b.id <> a.id
    RETURN a.id AS seed, b.id AS target_mapc, b.ten AS target_ten
    LIMIT 6
    """
    records = s.run(cypher, seeds=seed_mapcs).data()

print(f"\nGraph discovered {len(records)} direct REFERS_TO edges from seeds {seed_mapcs}:")
for rec in records:
    print(f"  {rec['seed']} -[:REFERS_TO]-> {rec['target_mapc']} ({rec['target_ten']})")

# Hybrid fusion: Cited article gets coupled score (seed_score * 0.92)
candidates = {r["mapc"]: dict(r) for r in vec_top10}
seed_scores = {r["mapc"]: r["score"] for r in vec_top10}

for rec in records:
    tgt = rec["target_mapc"]
    seed_s = seed_scores.get(rec["seed"], 0.7)
    coupled_score = seed_s * 0.92
    if tgt in candidates:
        if coupled_score > candidates[tgt]["score"]:
            candidates[tgt]["score"] = coupled_score
    else:
        candidates[tgt] = {
            "mapc": tgt,
            "chunk_id": "",
            "score": coupled_score,
            "ten": rec["target_ten"] + " (KG-coupled)"
        }

hybrid_top10 = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)[:10]

print("\n--- TH2 (Vector + KG Top 5) ---")
for idx, r in enumerate(hybrid_top10[:5], 1):
    gold = sample_q["relevance"].get(r["mapc"], 0)
    print(f"  Rank {idx}: {r['mapc']} (score={r['score']:.4f}) | gold={gold} | {r['ten']}")

driver.close()
