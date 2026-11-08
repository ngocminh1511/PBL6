"""Inspect real vector hits, ontology paths and appendix payloads without an LLM."""
from __future__ import annotations

import os
from dataclasses import asdict
from time import perf_counter
from urllib.parse import quote

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from labor_rag.appendices.runtime import AppendixCatalog, usable
from .hybrid_retrieve import Evidence, HybridRetriever, MODEL_NAME, NEO4J_DATABASE, DATASET_ID, in_force


PATH_FIELDS = """
[n IN nodes(path) | n {.id, .document_id, .document_number, .article_number,
    .appendix_id, .appendix_number, .artifact_id, .file_name, .ten, labels: labels(n)}] AS nodes,
[r IN relationships(path) | {source: startNode(r).id, target: endNode(r).id,
    type: type(r)}] AS edges
"""
# Undirected traversal also finds the implementing circular from a base-law hit.
# Only SourceComponent intermediates are allowed: never fan out via a document.
APPENDIX_PATHS = """
UNWIND $seeds AS seed
MATCH (s:SourceComponent {dataset_id: $dataset, document_id: seed.document_id,
                          article_number: seed.article_number})
WHERE s.clause_number IS NULL AND s.point_number IS NULL
MATCH path=(s)-[:CITES_COMPONENT|IMPLEMENTS_COMPONENT*1..2]-(a:Appendix {dataset_id: $dataset})
WHERE all(n IN nodes(path) WHERE n.dataset_id = $dataset)
  AND all(n IN nodes(path)[0..-1] WHERE n:SourceComponent)
RETURN seed.chunk_id AS seed_chunk_id, a.appendix_id AS appendix_id,
""" + PATH_FIELDS + """
UNION
UNWIND $direct_ids AS appendix_id
MATCH path=(s:SourceComponent {dataset_id: $dataset})-[:CITES_COMPONENT]->
           (a:Appendix {dataset_id: $dataset, appendix_id: appendix_id})
RETURN null AS seed_chunk_id, a.appendix_id AS appendix_id,
""" + PATH_FIELDS + """
ORDER BY appendix_id, seed_chunk_id
LIMIT 100
"""

APPENDIX_PROVENANCE = """
MATCH path=(source)-[:CONTAINS|SOURCE_COMPONENT]->(a:Appendix {dataset_id: $dataset})
WHERE a.appendix_id IN $appendix_ids AND source.dataset_id = $dataset
  AND (source:VanBan OR source:SourceArtifact)
RETURN a.appendix_id AS appendix_id,
""" + PATH_FIELDS


class RetrievalStageError(RuntimeError):
    def __init__(self, stage: str, cause: Exception):
        self.stage = stage
        self.error_type = type(cause).__name__
        super().__init__(f"{stage}: {self.error_type}")


class RetrievalInspector:
    def __init__(self, catalog: AppendixCatalog, retriever=None, *, settings=None):
        self.catalog = catalog
        from labor_rag.settings import Settings
        self.settings = settings or Settings()
        self.backend = self.settings.query_backend
        self.retriever = retriever or HybridRetriever(settings=self.settings)
        self.dataset_id = getattr(self.retriever, "dataset_id", self.settings.DATASET_ID)
        self.database = getattr(self.retriever, "database", self.settings.NEO4J_DATABASE)
        self.model_name = getattr(self.retriever, "model_name", self.settings.EMBEDDING_MODEL)

    def close(self):
        self.retriever.close()

    def evidence(self, payload, source, score=None, rank=None):
        item = Evidence.from_payload(payload, source, score or 0)
        result = {**asdict(item), "citation": item.citation, "score": score, "rank": rank}
        if item.appendix_id in self.catalog.items:
            result["view_url"] = self.catalog.public_item(self.catalog.items[item.appendix_id])["view_url"]
            if item.chunk_id in self.catalog.chunks:
                result["view_url"] += "?chunk_id=" + quote(item.chunk_id, safe="")
        return result

    def inspect(self, question: str, top_k: int = 8):
        started, timings, warnings = perf_counter(), {}, []

        def run(stage, action):
            before = perf_counter()
            try:
                return action()
            except Exception as exc:
                raise RetrievalStageError(stage, exc) from None
            finally:
                timings[stage] = round((perf_counter() - before) * 1000, 2)

        encoded = run("embedding", lambda: self.retriever.model.encode(question, normalize_embeddings=True))
        vector = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
        points = run("vector_search", lambda: self.retriever.qdrant.query_points(
            collection_name=self.retriever.collection, query=vector, query_filter=in_force(),
            limit=top_k, with_payload=True, with_vectors=False).points)
        vector_hits = [self.evidence(p.payload, "qdrant:vector", p.score, rank)
                       for rank, p in enumerate(points, 1)]
        seeds = [{"chunk_id": hit["chunk_id"], "document_id": hit["document_id"],
                  "article_number": str(hit["meta_dieu"])}
                 for hit in vector_hits if hit["document_id"] and hit["meta_dieu"]]
        direct_ids = sorted({hit["appendix_id"] for hit in vector_hits if hit["appendix_id"]})
        graph = {"status": "skipped", "paths": [], "provenance": [],
                 "cypher": APPENDIX_PATHS.strip(), "parameters": {"dataset": self.dataset_id, "seeds": seeds, "direct_ids": direct_ids}}

        def graph_lookup():
            with self.retriever.neo4j.session(database=self.database) as session:
                paths = [dict(row) for row in session.run(APPENDIX_PATHS, **graph["parameters"])]
                ids = sorted(set(direct_ids) | {row["appendix_id"] for row in paths})
                provenance = [dict(row) for row in session.run(
                    APPENDIX_PROVENANCE, dataset=self.dataset_id, appendix_ids=ids)] if ids else []
                return paths, provenance

        if seeds or direct_ids:
            try:
                graph["paths"], graph["provenance"] = run("ontology", graph_lookup)
                graph["status"] = "connected"
                if len(graph["paths"]) == 100:
                    warnings.append("Chỉ hiển thị tối đa 100 đường liên kết ontology.")
            except RetrievalStageError as exc:
                graph.update(status="unavailable", error_type=exc.error_type)
                warnings.append("Chưa truy vấn được Neo4j; các kết quả vector vẫn được giữ. Không suy ra liên kết ontology từ catalog local.")
        else:
            timings["ontology"] = 0

        linked_ids = {path["appendix_id"] for path in graph["paths"]}
        candidate_ids = sorted(set(direct_ids) | linked_ids)

        def fetch_chunks():
            chunks, offset = [], None
            while True:
                batch, offset = self.retriever.qdrant.scroll(
                    collection_name=self.retriever.collection,
                    scroll_filter=Filter(must=[in_force(),
                        FieldCondition(key="chunk_type", match=MatchValue(value="appendix")),
                        FieldCondition(key="appendix_id", match=MatchAny(any=candidate_ids))]),
                    limit=256, offset=offset, with_payload=True, with_vectors=False)
                chunks.extend(p.payload for p in batch)
                if offset is None:
                    return chunks

        payloads, fetch_status = [], "skipped"
        if candidate_ids:
            try:
                payloads = run("appendix_fetch", fetch_chunks)
                fetch_status = "completed"
            except RetrievalStageError as exc:
                fetch_status = "unavailable"
                warnings.append(f"Chưa lấy được các chunk phụ lục từ Qdrant ({exc.error_type}); không dùng nội dung local thay thế.")
        else:
            timings["appendix_fetch"] = 0

        appendices = []
        for appendix_id in candidate_ids:
            item = self.catalog.items.get(appendix_id)
            if item is None:
                warnings.append(f"{appendix_id}: chưa có metadata trong catalog local để xem/tải nguồn.")
            allowed = item is not None and usable(item)
            chunks = [self.evidence(p, "qdrant:appendix_id") for p in payloads
                      if p.get("appendix_id") == appendix_id and allowed]
            chunks.sort(key=lambda c: c["locator"].get("start", 0))
            direct_scores = [hit["score"] for hit in vector_hits if hit["appendix_id"] == appendix_id]
            appendices.append({
                **(self.catalog.public_item(item) if item else {"appendix_id": appendix_id}),
                "retrieved_via": (["vector"] if appendix_id in direct_ids else []) + (["ontology"] if appendix_id in linked_ids else []),
                "vector_score": max(direct_scores) if direct_scores else None,
                "eligible_for_retrieval": allowed, "chunks": chunks,
            })
        appendices.sort(key=lambda a: (-(a["vector_score"] if a["vector_score"] is not None else -1), a["appendix_id"]))
        timings["total"] = round((perf_counter() - started) * 1000, 2)
        return {"mode": "retrieval_only", "llm_used": False, "question": question,
                "embedding": {"backend": self.backend, "model": self.model_name, "dimensions": len(vector)},
                "collection": self.retriever.collection, "vector_hits": vector_hits, "graph": graph,
                "appendices": appendices, "appendix_fetch_status": fetch_status,
                "timings_ms": timings, "warnings": warnings}
