"""Hybrid retrieval: vector search on Qdrant (semantic match) + 1-hop graph
expansion on Neo4j (CONTAINS/PART_OF for chapter context, REFERS_TO for
explicitly cross-referenced provisions). Corresponds to the "Vector
Retrieval + Graph Retrieval -> Hybrid Retrieval" stage of the pipeline.

Chunks follow schema v5 (docs/structural_jsonl.md): a long Dieu is stored as
parts "<doc>:d35:p1", ":p2", ...; vector hits are grouped per Dieu and only
provisions in force today are searched.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import DatetimeRange, FieldCondition, Filter, IsNullCondition, MatchValue, PayloadField
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from labor_rag.ingest.chunk_schema import article_id, citation, join_parts, part_number

load_dotenv()

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
COLLECTION = os.getenv("QDRANT_COLLECTION", "legal_ld_v5_bge")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "labor_rag_pw"))
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
DATASET_ID = os.getenv("DATASET_ID", "lao_dong_v5")
# Parts of one Dieu collapse into one hit, so fetch a few extra.
OVERFETCH = 2


@dataclass
class Evidence:
    chunk_id: str
    mapc: str | None
    ten: str
    text: str
    source: str  # "vector" | "graph:REFERS_TO" | "graph:PART_OF"
    score: float = 0.0
    document_id: str | None = None
    meta_dieu: str | None = None
    meta_khoan: str | None = None
    meta_de_muc: str | None = None

    @property
    def citation(self) -> str:
        """'Điều 35 khoản 4-5 Nghị định số 145/2020/NĐ-CP'."""
        return citation(vars(self))

    @classmethod
    def from_payload(cls, payload: dict, source: str, score: float = 0.0) -> "Evidence":
        return cls(
            chunk_id=payload["chunk_id"],
            mapc=payload.get("mapc"),
            ten=payload.get("ten") or "",
            text=payload.get("text") or "",
            source=source,
            score=score,
            document_id=payload.get("document_id"),
            meta_dieu=payload.get("meta_dieu"),
            meta_khoan=payload.get("meta_khoan"),
            meta_de_muc=payload.get("meta_de_muc"),
        )


def in_force(today: date | None = None) -> Filter:
    """still_valid AND (effective_from_date <= today OR effective_from_date IS NULL)."""
    today = today or date.today()
    return Filter(
        must=[
            FieldCondition(key="still_valid", match=MatchValue(value=True)),
            Filter(
                should=[
                    FieldCondition(key="effective_from_date", range=DatetimeRange(lte=today.isoformat())),
                    IsNullCondition(is_null=PayloadField(key="effective_from_date")),
                ]
            ),
        ]
    )


class HybridRetriever:
    def __init__(self) -> None:
        self.model = SentenceTransformer(MODEL_NAME)
        self.qdrant = QdrantClient(
            url=QDRANT_URL, api_key=os.getenv("QDRANT_API_KEY") or None, timeout=int(os.getenv("QDRANT_TIMEOUT", "60"))
        )
        self.neo4j = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    def close(self) -> None:
        self.neo4j.close()

    def vector_search(self, query: str, top_k: int = 8) -> list[Evidence]:
        """Top-k Dieu: parts of one Dieu count once, with their best score."""
        vector = self.model.encode(query, normalize_embeddings=True).tolist()
        hits = self.qdrant.query_points(
            collection_name=COLLECTION, query=vector, query_filter=in_force(), limit=top_k * OVERFETCH
        ).points
        best: dict[str, Evidence] = {}
        for h in hits:  # sorted by score, so the first part seen is the best one
            key = article_id(h.payload["chunk_id"])
            if key not in best:
                best[key] = Evidence.from_payload(h.payload, "vector", h.score)
        return list(best.values())[:top_k]

    def graph_expand(self, mapcs: list[str], limit_per_node: int = 5) -> list[Evidence]:
        """1-hop REFERS_TO expansion from a set of seed Dieu MAPCs, restricted
        to nodes that actually have content (content_available=True) since
        stub nodes outside the ingested domain have no text to show yet."""
        query = """
        UNWIND $mapcs AS seed
        MATCH (a:Dieu {id: seed})-[:REFERS_TO]->(b:Dieu {content_available: true})
        WHERE $dataset_id IS NULL
           OR (a.dataset_id = $dataset_id AND b.dataset_id = $dataset_id)
        RETURN DISTINCT b.id AS mapc, b.ten AS ten
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
                    chunk_id="",  # filled in by hydrate_from_qdrant()
                    mapc=r["mapc"],
                    ten=r["ten"],
                    text="",
                    source="graph:REFERS_TO",
                )
                for r in rows
            ]

    def hydrate_from_qdrant(self, evidences: list[Evidence]) -> None:
        """Fill in the chunk fields of graph-expanded evidence (which only has
        mapc/ten from Neo4j) from Qdrant, joining every part of a split Dieu.
        Evidence whose Dieu is not in force stays empty."""
        for ev in evidences:
            if ev.text:
                continue
            points, _ = self.qdrant.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(must=[FieldCondition(key="mapc", match=MatchValue(value=ev.mapc)), in_force()]),
                limit=64,
                with_payload=True,
            )
            if not points:
                continue
            payloads = sorted((p.payload for p in points), key=lambda payload: part_number(payload["chunk_id"]))
            hydrated = Evidence.from_payload(payloads[0], ev.source, ev.score)
            hydrated.chunk_id = article_id(hydrated.chunk_id)
            hydrated.meta_khoan = None
            hydrated.text = join_parts([payload["text"] for payload in payloads])
            vars(ev).update(vars(hydrated))

    def retrieve(self, query: str, top_k: int = 8, graph_limit_per_node: int = 3) -> list[Evidence]:
        vector_hits = self.vector_search(query, top_k=top_k)
        seed_mapcs = [e.mapc for e in vector_hits if e.mapc]
        graph_hits = self.graph_expand(seed_mapcs, limit_per_node=graph_limit_per_node)
        self.hydrate_from_qdrant(graph_hits)

        seen = {article_id(e.chunk_id) for e in vector_hits}
        merged = list(vector_hits)
        for e in graph_hits:
            if e.text and e.chunk_id not in seen:
                merged.append(e)
                seen.add(e.chunk_id)
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
            print(f"  {e.citation}  ({e.chunk_id})")
            print()
    finally:
        retriever.close()
