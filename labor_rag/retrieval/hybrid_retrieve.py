"""Hybrid retrieval: vector search on Qdrant (semantic match) + 1-hop graph
expansion on Neo4j (CONTAINS/PART_OF for chapter context, REFERS_TO for the
Dieu Phap dien links, CITES_COMPONENT / IMPLEMENTS_COMPONENT for the khoan a
hit's khoan refer to in their text, e.g. "theo quy định tại khoản 3 Điều 147
của Bộ luật Lao động": only that khoan's text is added, not the whole Dieu). Corresponds to the "Vector
Retrieval + Graph Retrieval -> Hybrid Retrieval" stage of the pipeline.

Chunks follow schema v5 (docs/structural_jsonl.md): a long Dieu is stored as
parts "<doc>:d35:p1", ":p2", ...; vector hits are grouped per Dieu and only
provisions in force today are searched.

Amendments come from the graph: for each Dieu found, Neo4j gives the
amendments of its source Dieu (SourceComponent -[:HAS_AMENDMENT]->
AmendmentEvent -[:AMENDING_COMPONENT]-> the amending Dieu or khoan) dated
after the Dieu's version_date, i.e. not consolidated into its text yet. Their
chunks are attached as Evidence.amendments, so they stay with the Dieu
through reranking and the prompt can put them first
(docs/structural_jsonl.md, section 10).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import DatetimeRange, FieldCondition, Filter, IsNullCondition, MatchAny, MatchValue, PayloadField
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from labor_rag.ingest.chunk_schema import article_id, citation, join_parts, make_chunk_id, part_number

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
    version_date: str | None = None
    amendments: list["Evidence"] = field(default_factory=list)  # parts that amend this Dieu after version_date
    change: str | None = None  # on an amendment: "sửa đổi, bổ sung khoản 2"

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
            version_date=payload.get("version_date"),
        )


# Amendments of the source Dieu behind each hit, dated after the hit's
# version_date (the ones its text does not include yet).
PENDING_AMENDMENTS = """
UNWIND $keys AS key
MATCH (s:SourceComponent {dataset_id: $dataset_id, document_id: key.document_id, article_number: key.meta_dieu})
      -[:HAS_AMENDMENT]->(e:AmendmentEvent)-[:AMENDING_COMPONENT]->(c:SourceComponent)
WHERE e.date IS NOT NULL AND (key.version_date IS NULL OR e.date > key.version_date)
RETURN key.index AS index, e.date AS date, e.actions AS actions, e.scope AS scope,
       c.document_id AS document_id, c.article_number AS article_number, c.clause_number AS clause_number
ORDER BY index, date
"""

# Source Dieu / khoan / diem that the khoan of each hit (or the Dieu, for a
# hit that is a whole Dieu) refer to in their text.
REFERENCED_COMPONENTS = """
UNWIND $keys AS key
MATCH (c:SourceComponent {dataset_id: $dataset_id, document_id: key.document_id, article_number: key.meta_dieu})
WHERE c.point_number IS NULL AND (key.khoans IS NULL OR c.clause_number IS NULL OR c.clause_number IN key.khoans)
MATCH (c)-[r:CITES_COMPONENT|IMPLEMENTS_COMPONENT]->(t:SourceComponent)
WHERE t.article_number IS NOT NULL AND NOT (t.document_id = key.document_id AND t.article_number = key.meta_dieu)
OPTIONAL MATCH (k:SourceComponent)-[:CONTAINS]->(t) WHERE t.point_number IS NOT NULL
RETURN DISTINCT key.index AS index, 1 AS hop, type(r) AS relation, t.document_id AS document_id,
       t.article_number AS article_number, t.clause_number AS clause_number, t.point_number AS point_number,
       coalesce(t.text, k.text) AS text
UNION
UNWIND $keys AS key
MATCH (c:SourceComponent {dataset_id: $dataset_id, document_id: key.document_id, article_number: key.meta_dieu})
WHERE c.point_number IS NULL AND (key.khoans IS NULL OR c.clause_number IS NULL OR c.clause_number IN key.khoans)
MATCH (c)-[r:CITES_COMPONENT|IMPLEMENTS_COMPONENT]->(t:SourceComponent)
WHERE t.article_number IS NOT NULL AND NOT (t.document_id = key.document_id AND t.article_number = key.meta_dieu)
// Hop 2: follow intra-article citations within the same Dieu
MATCH (t)-[r2:CITES_COMPONENT]->(t2:SourceComponent)
WHERE t2.document_id = t.document_id AND t2.article_number = t.article_number
  AND NOT (t2.clause_number = t.clause_number AND coalesce(t2.point_number, '') = coalesce(t.point_number, ''))
OPTIONAL MATCH (k2:SourceComponent)-[:CONTAINS]->(t2) WHERE t2.point_number IS NOT NULL
RETURN DISTINCT key.index AS index, 2 AS hop, type(r2) AS relation, t2.document_id AS document_id,
       t2.article_number AS article_number, t2.clause_number AS clause_number, t2.point_number AS point_number,
       coalesce(t2.text, k2.text) AS text
"""


def khoans_of(meta_khoan: str | None) -> list[str] | None:
    """'1-8' -> ['1', ..., '8']; '3' -> ['3']; None (a whole Dieu) -> None."""
    if not meta_khoan:
        return None
    start, _, end = str(meta_khoan).partition("-")
    if end and start.isdigit() and end.isdigit():
        return [str(number) for number in range(int(start), int(end) + 1)]
    return [start, end] if end else [start]


def referenced_evidence(row: dict, payloads: list[dict]) -> Evidence | None:
    """Evidence for one REFERENCED_COMPONENTS row: the referenced khoan's text
    (the whole Dieu when the reference names no khoan), with the chunk fields
    of the in-force Dieu; None when that Dieu is not indexed or not in force."""
    parts = sorted(
        (p for p in payloads if p.get("document_id") == row["document_id"] and p.get("meta_dieu") == row["article_number"]),
        key=lambda payload: part_number(payload["chunk_id"]),
    )
    if not parts:
        return None
    source = "graph:IMPLEMENTS" if row["relation"] == "IMPLEMENTS_COMPONENT" else "graph:CITES"
    evidence = Evidence.from_payload(parts[0], source)
    evidence.chunk_id = make_chunk_id(row["document_id"], row["article_number"])
    evidence.meta_khoan = row["clause_number"]
    evidence.text = (row.get("text") if row["clause_number"] else None) or join_parts([p["text"] for p in parts])
    if row.get("point_number"):
        evidence.change = f"điểm {row['point_number']}"
    return evidence


ACTION_WORDS = {"sua_doi": "sửa đổi", "bo_sung": "bổ sung", "bai_bo": "bãi bỏ", "thay_cum_tu": "thay cụm từ"}


def change_text(actions: list[str] | None, scope: str | None) -> str:
    """['sua_doi', 'bo_sung'] + 'khoản 2' -> 'sửa đổi, bổ sung khoản 2'."""
    words = ", ".join(ACTION_WORDS.get(action, action) for action in actions or [])
    return " ".join(part for part in [words, scope] if part)


def amending_parts(payloads: list[dict], document_id: str, article_number: str, clause_number: str | None) -> list[dict]:
    """Chunks of the amending Dieu, only its khoan when the graph names one, in order."""
    parts = [
        payload
        for payload in payloads
        if payload.get("document_id") == document_id
        and payload.get("meta_dieu") == article_number
        and (clause_number is None or payload.get("meta_khoan") == clause_number)
    ]
    return sorted(parts, key=lambda payload: part_number(payload["chunk_id"]))


def in_force(today: date | None = None) -> Filter:
    """still_valid AND (effective_from_date <= today OR IS NULL) AND
    (effective_to_date > today OR IS NULL): a replaced document stays in force
    until the day its replacement takes effect."""
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
            Filter(
                should=[
                    FieldCondition(key="effective_to_date", range=DatetimeRange(gt=today.isoformat())),
                    IsNullCondition(is_null=PayloadField(key="effective_to_date")),
                ]
            ),
        ]
    )


class HybridRetriever:
    def __init__(self, collection: str | None = None) -> None:
        self.model = SentenceTransformer(MODEL_NAME)
        self.collection = collection or os.getenv("QDRANT_COLLECTION", COLLECTION)
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
            collection_name=self.collection, query=vector, query_filter=in_force(), limit=top_k * OVERFETCH
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
                collection_name=self.collection,
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

    def in_force_payloads(self, document_ids: list[str]) -> list[dict]:
        """Every chunk in force of these documents."""
        payloads: list[dict] = []
        offset = None
        while True:
            points, offset = self.qdrant.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(must=[FieldCondition(key="document_id", match=MatchAny(any=document_ids)), in_force()]),
                limit=256,
                offset=offset,
                with_payload=True,
            )
            payloads += [point.payload for point in points if point.payload]
            if offset is None:
                return payloads

    def reference_expand(self, evidences: list[Evidence], limit_per_node: int = 5) -> list[Evidence]:
        """The khoan (or Dieu) that each hit refers to in its text, in force."""
        keys = [
            {"index": i, "document_id": ev.document_id, "meta_dieu": ev.meta_dieu, "khoans": khoans_of(ev.meta_khoan)}
            for i, ev in enumerate(evidences)
            if ev.document_id and ev.meta_dieu
        ]
        if not keys:
            return []
        with self.neo4j.session(database=NEO4J_DATABASE) as session:
            rows = [dict(row) for row in session.run(REFERENCED_COMPONENTS, keys=keys, dataset_id=DATASET_ID)]
        document_ids = sorted({row["document_id"] for row in rows if row["document_id"]})
        payloads = self.in_force_payloads(document_ids) if document_ids else []
        found: list[Evidence] = []
        per_hit: dict[int, int] = {}
        seen: set[tuple] = set()
        for row in rows:
            key = (row["document_id"], row["article_number"], row["clause_number"], row.get("point_number"))
            if key in seen or per_hit.get(row["index"], 0) >= limit_per_node:
                continue
            evidence = referenced_evidence(row, payloads)
            if evidence:
                seen.add(key)
                per_hit[row["index"]] = per_hit.get(row["index"], 0) + 1
                found.append(evidence)
        return found

    def pending_amendments(self, evidences: list[Evidence]) -> list[dict]:
        """Rows of PENDING_AMENDMENTS; `index` is the position in evidences."""
        keys = [
            {"index": i, "document_id": ev.document_id, "meta_dieu": ev.meta_dieu, "version_date": ev.version_date}
            for i, ev in enumerate(evidences)
            if ev.document_id and ev.meta_dieu
        ]
        if not keys:
            return []
        with self.neo4j.session(database=NEO4J_DATABASE) as session:
            return [dict(row) for row in session.run(PENDING_AMENDMENTS, keys=keys, dataset_id=DATASET_ID)]

    def attach_amendments(self, evidences: list[Evidence]) -> None:
        """Fill Evidence.amendments with the chunks (in force) of the pending amendments."""
        rows = self.pending_amendments(evidences)
        document_ids = sorted({row["document_id"] for row in rows if row["document_id"]})
        if not document_ids:
            return
        payloads = self.in_force_payloads(document_ids)
        for row in rows:
            parts = amending_parts(payloads, row["document_id"], row["article_number"], row["clause_number"])
            if not parts:
                continue  # the amending document is not indexed (or not in force)
            amendment = Evidence.from_payload(parts[0], "amendment")
            amendment.chunk_id = article_id(parts[0]["chunk_id"])
            amendment.meta_khoan = row["clause_number"]
            amendment.text = join_parts([part["text"] for part in parts])
            amendment.change = change_text(row["actions"], row["scope"])
            evidences[row["index"]].amendments.append(amendment)

    def retrieve(self, query: str, top_k: int = 8, graph_limit_per_node: int = 3) -> list[Evidence]:
        vector_hits = self.vector_search(query, top_k=top_k)
        seed_mapcs = [e.mapc for e in vector_hits if e.mapc]
        graph_hits = self.graph_expand(seed_mapcs, limit_per_node=graph_limit_per_node)
        self.hydrate_from_qdrant(graph_hits)
        # Khoan-level references first: they carry only the khoan cited.
        reference_hits = self.reference_expand(vector_hits, limit_per_node=graph_limit_per_node)

        seen = {article_id(e.chunk_id) for e in vector_hits}
        merged = list(vector_hits)
        for e in reference_hits + graph_hits:
            if e.text and article_id(e.chunk_id) not in seen:
                merged.append(e)
                seen.add(article_id(e.chunk_id))
        self.attach_amendments(merged)
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
            for amendment in e.amendments:
                print(f"  sửa đổi bởi {amendment.citation}  ({amendment.chunk_id})")
            print()
    finally:
        retriever.close()
