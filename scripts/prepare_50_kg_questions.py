import os
import sys
import json
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

query = """
MATCH (a:Dieu)-[r:REFERS_TO]->(b:Dieu)
WHERE a.content_available = true AND b.content_available = true
RETURN a.id AS src_mapc, a.ten AS src_ten, b.id AS tgt_mapc, b.ten AS tgt_ten
"""

with driver.session() as s:
    records = [dict(r) for r in s.run(query)]

print(f"Total candidate pairs with content_available in Neo4j: {len(records)}")

# Deduplicate pairs
unique_pairs = []
seen = set()
for r in records:
    key = (r["src_mapc"], r["tgt_mapc"])
    if key not in seen:
        seen.add(key)
        unique_pairs.append(r)

print(f"Unique candidate pairs: {len(unique_pairs)}")

# Sample first 15 pairs
for i, p in enumerate(unique_pairs[:15]):
    print(f"{i+1}. {p['src_mapc']} ({p['src_ten']}) -> {p['tgt_mapc']} ({p['tgt_ten']})")

driver.close()
