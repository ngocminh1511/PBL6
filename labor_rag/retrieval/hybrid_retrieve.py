"""Hybrid retrieval: vector search on Qdrant (semantic match) + 1-hop graph
expansion on Neo4j (CONTAINS/PART_OF for chapter context, REFERS_TO for
explicitly cross-referenced provisions). Corresponds to the "Vector
Retrieval + Graph Retrieval -> Hybrid Retrieval" stage of the pipeline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_ld_v4_bkai")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "labor_rag_pw"))
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
DATASET_ID = os.getenv("DATASET_ID", "lao_dong_v4")


@dataclass
class Evidence:
    mapc: str
    ten: str
    citation: str | None
    breadcrumb: str
    text: str
    source: str  # "vector" | "graph:REFERS_TO" | "graph:PART_OF"
    score: float = 0.0


class HybridRetriever:
    def __init__(self) -> None:
        self.model = SentenceTransformer(MODEL_NAME)
        self.qdrant = QdrantClient(url=QDRANT_URL, api_key=os.getenv("QDRANT_API_KEY") or None)
        self.neo4j = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    def close(self) -> None:
        self.neo4j.close()

    def vector_search(self, query: str, top_k: int = 8) -> list[Evidence]:
        vector = self.model.encode(query, normalize_embeddings=True).tolist()
        hits = self.qdrant.query_points(collection_name=COLLECTION, query=vector, limit=top_k).points
        return [
            Evidence(
                mapc=h.payload["mapc"],
                ten=h.payload["ten"],
                citation=h.payload["citation"],
                breadcrumb=h.payload["breadcrumb"],
                text=h.payload["text"],
                source="vector",
                score=h.score,
            )
            for h in hits
        ]

    def graph_expand(self, mapcs: list[str], limit_per_node: int = 5) -> list[Evidence]:
        """1-hop REFERS_TO expansion from a set of seed Dieu MAPCs, restricted
        to nodes that actually have content (content_available=True) since
        stub nodes outside the ingested domain have no text to show yet."""
        query = """
        UNWIND $mapcs AS seed
        MATCH (a:Dieu {id: seed})-[:REFERS_TO]->(b:Dieu {content_available: true})
        WHERE $dataset_id IS NULL
           OR (a.dataset_id = $dataset_id AND b.dataset_id = $dataset_id)
        RETURN DISTINCT b.id AS mapc, b.ten AS ten, b.citation AS citation
        LIMIT $limit
        """
        with self.neo4j.session(database=NEO4J_DATABASE) as session:
            rows = session.run(
                query,
                mapcs=mapcs,
                limit=limit_per_node * len(mapcs),
                dataset_id=DATASET_ID,
            )
            return [
                Evidence(
                    mapc=r["mapc"],
                    ten=r["ten"],
                    citation=r["citation"],
                    breadcrumb="",
                    text="",  # filled in by hydrate_from_qdrant()
                    source="graph:REFERS_TO",
                )
                for r in rows
            ]

    def hydrate_from_qdrant(self, evidences: list[Evidence]) -> None:
        """Fill in breadcrumb/text for graph-expanded evidence (which only
        has id/ten/citation from Neo4j) by looking up the same mapc's chunk
        payload in Qdrant via a scroll filter."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        for ev in evidences:
            if ev.text:
                continue
            points, _ = self.qdrant.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(must=[FieldCondition(key="mapc", match=MatchValue(value=ev.mapc))]),
                limit=1,
                with_payload=True,
            )
            if points:
                ev.breadcrumb = points[0].payload["breadcrumb"]
                ev.text = points[0].payload["text"]

    def retrieve(self, query: str, top_k: int = 8, graph_limit_per_node: int = 3) -> list[Evidence]:
        vector_hits = self.vector_search(query, top_k=top_k)
        seed_mapcs = [e.mapc for e in vector_hits]
        graph_hits = self.graph_expand(seed_mapcs, limit_per_node=graph_limit_per_node)
        self.hydrate_from_qdrant(graph_hits)

        seen = {e.mapc for e in vector_hits}
        merged = list(vector_hits)
        for e in graph_hits:
            if e.mapc not in seen and e.text:
                merged.append(e)
                seen.add(e.mapc)
        return merged


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    retriever = HybridRetriever()
    try:
        query = "Người lao động thử việc có được trả lương không?"
        results = retriever.retrieve(query)
        print(f"Query: {query}\n")
        for e in results:
            print(f"[{e.source}] {e.ten} (score={e.score:.3f})")
            print(f"  {e.breadcrumb}")
            print(f"  {e.citation}")
            print()
    finally:
        retriever.close()
