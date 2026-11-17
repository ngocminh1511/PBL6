import os
import sys
import json
import re
from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_ld_v5_bge")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "labor_rag_pw"))

driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
qdrant = QdrantClient(url=QDRANT_URL, api_key=os.getenv("QDRANT_API_KEY") or None)

# Query meaningful pairs where src != tgt
query = """
MATCH (a:Dieu)-[r:REFERS_TO]->(b:Dieu)
WHERE a.content_available = true AND b.content_available = true AND a.id <> b.id
RETURN a.id AS src_mapc, a.ten AS src_ten, b.id AS tgt_mapc, b.ten AS tgt_ten
LIMIT 200
"""

with driver.session() as s:
    records = [dict(r) for r in s.run(query)]

print(f"Retrieved {len(records)} candidate edges")

def get_chunk_info(mapc):
    points, _ = qdrant.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(must=[FieldCondition(key="mapc", match=MatchValue(value=mapc))]),
        limit=5,
        with_payload=True
    )
    if not points:
        return None, None, None, None
    p = points[0].payload
    chunk_id = p.get("chunk_id")
    # Base chunk id without :p1
    base_chunk_id = re.sub(r":p\d+$", "", chunk_id) if chunk_id else None
    text = p.get("text", "")
    de_muc = p.get("meta_de_muc", "20.2")
    return base_chunk_id, text, de_muc, p.get("document_id")

valid_pairs = []
seen = set()

for r in records:
    pair_key = (r["src_mapc"], r["tgt_mapc"])
    if pair_key in seen:
        continue
    seen.add(pair_key)
    
    src_chunk, src_text, de_muc, src_doc = get_chunk_info(r["src_mapc"])
    tgt_chunk, tgt_text, _, tgt_doc = get_chunk_info(r["tgt_mapc"])
    
    if src_chunk and tgt_chunk:
        valid_pairs.append({
            "src_mapc": r["src_mapc"],
            "src_ten": r["src_ten"],
            "src_chunk": src_chunk,
            "src_text_snippet": src_text[:120].replace("\n", " "),
            "tgt_mapc": r["tgt_mapc"],
            "tgt_ten": r["tgt_ten"],
            "tgt_chunk": tgt_chunk,
            "tgt_text_snippet": tgt_text[:120].replace("\n", " "),
            "de_muc": de_muc or "20.2"
        })
    if len(valid_pairs) >= 60:
        break

print(f"Found {len(valid_pairs)} fully hydrated valid pairs in Qdrant & Neo4j.")
with open("labor_rag/evaluation/results/candidate_kg_pairs.json", "w", encoding="utf-8") as f:
    json.dump(valid_pairs, f, ensure_ascii=False, indent=2)
print("Saved candidate pairs to labor_rag/evaluation/results/candidate_kg_pairs.json")

driver.close()
