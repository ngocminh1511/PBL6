"""Remove a loaded PDF document and give its place back to Phap dien.

A PDF shares its document_id with the Phap dien source document it repeats
(e.g. "45-2019-qh14"), and indexing it (services/ingestion.py) may have:

- written its chunks over the Phap dien chunks of the same Dieu (same
  chunk_id, merge.py decides per Dieu);
- added graph nodes and edges (its own Dieu, amendment events, "replaces")
  and overwritten properties of shared nodes, e.g. VanBan.valid_to of a
  document it replaces, which sync_validity copied to effective_to_date.

Removal undoes that against the versioned Phap dien projection (LAO_DONG_DIR),
which uploads never modify:

1. graph: nodes of the document and their neighbours absent from Phap dien
   are deleted, edges absent from Phap dien are deleted, shared nodes get
   their Phap dien properties back;
2. vector store: the document's chunks with source "pdf" are deleted and the
   Phap dien chunks of the same document are written back (embedded before
   anything is deleted); effective_to_date follows the restored VanBan nodes;
3. local files: data/interim/pdf_chunks/{document_id}_*.jsonl.

Steps run in that order and stop at the first failure, so a retry is safe.
"""
from __future__ import annotations

import json
from contextlib import closing, nullcontext
from pathlib import Path

from labor_rag.config import LAO_DONG_DIR

PDF_SOURCE = "pdf"


class DocumentRemovalError(RuntimeError):
    """A store could not be updated; the message names the step."""


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _edge_key(source, edge_type, target, predicate) -> tuple:
    return (source, edge_type, target, predicate or f"local:{edge_type}")


class PhapDienBase:
    """The versioned Phap dien projection: what the stores hold without any PDF."""

    def __init__(self, kg_dir: Path = LAO_DONG_DIR):
        self.nodes = {node["id"]: node for node in _rows(kg_dir / "kg_nodes.jsonl")}
        self.edges = {_edge_key(e["source"], e["type"], e["target"], e.get("predicate_iri"))
                      for e in _rows(kg_dir / "kg_edges.jsonl")}
        self.chunks_path = kg_dir / "chunks.jsonl"

    def chunks_of(self, document_id: str) -> list[dict]:
        return [chunk for chunk in _rows(self.chunks_path) if chunk.get("document_id") == document_id]


def remove_graph(session, dataset_id: str, document_id: str, base: PhapDienBase) -> dict:
    """Undo the graph writes of a PDF; returns counts and the VanBan whose validity changed."""
    rows = session.run(
        """
        MATCH (n:Entity {dataset_id:$dataset, document_id:$document})
        OPTIONAL MATCH (n)-[r]-(m:Entity {dataset_id:$dataset})
        RETURN n.id AS id, properties(n) AS props,
               elementId(r) AS rel, type(r) AS type, r.predicate_iri AS predicate,
               startNode(r).id AS source, endNode(r).id AS target,
               m.id AS other, properties(m) AS other_props
        """,
        dataset=dataset_id, document=document_id,
    )
    nodes: dict[str, dict] = {}
    rels: dict[str, tuple] = {}
    for row in rows:
        nodes[row["id"]] = row["props"]
        if row["rel"] is not None:
            rels[row["rel"]] = _edge_key(row["source"], row["type"], row["target"], row["predicate"])
            nodes.setdefault(row["other"], row["other_props"])

    # A neighbour outside Phap dien that belongs to another document is a stub
    # (a target of an amendment, a replaced document): removed only if orphaned.
    delete, stubs = [], []
    for node_id, props in nodes.items():
        if node_id in base.nodes:
            continue
        other = (props or {}).get("document_id")
        (stubs if other and other != document_id else delete).append(node_id)
    extra_rels = [rel for rel, key in rels.items() if key not in base.edges]
    def stored(node):  # Neo4j keeps no null properties
        return {key: value for key, value in {**node, "dataset_id": dataset_id}.items() if value is not None}

    reset = {node_id: props for node_id, props in nodes.items()
             if node_id in base.nodes and props != stored(base.nodes[node_id])}

    session.run("MATCH ()-[r]->() WHERE elementId(r) IN $rels DELETE r", rels=extra_rels)
    session.run("MATCH (n:Entity {dataset_id:$dataset}) WHERE n.id IN $ids DETACH DELETE n",
                dataset=dataset_id, ids=delete)
    orphans = session.run(
        "MATCH (n:Entity {dataset_id:$dataset}) WHERE n.id IN $ids AND NOT (n)--() "
        "WITH n, n.id AS id DELETE n RETURN id", dataset=dataset_id, ids=stubs)
    removed_stubs = [row["id"] for row in orphans]
    items = [{**base.nodes[node_id], "dataset_id": dataset_id} for node_id in reset]
    session.run("UNWIND $items AS item MATCH (n:Entity {id:item.id, dataset_id:item.dataset_id}) SET n = item",
                items=items)

    validity = {}
    for node_id, props in reset.items():
        restored = base.nodes[node_id]
        if restored.get("label") == "VanBan" and restored.get("document_id") \
                and (props or {}).get("valid_to") != restored.get("valid_to"):
            validity[restored["document_id"]] = restored.get("valid_to")
    return {"deleted_nodes": len(delete) + len(removed_stubs), "deleted_edges": len(extra_rels),
            "reset_nodes": len(reset), "validity": validity}


def remove_pdf_document(settings, document_id: str, *, base: PhapDienBase | None = None,
                        client=None, driver=None, embedder=None) -> dict:
    """Remove the PDF version of a document from the graph, the vector store and local files."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct
    from labor_rag.ingest.chunk_schema import point_id
    from labor_rag.ingest.embed_and_index import indexed_chunks
    from labor_rag.ingest.merge import plan_upsert

    base = base or PhapDienBase()
    collection = settings.QDRANT_COLLECTION
    result = {"document_id": document_id, "graph": None, "deleted_chunks": 0, "restored_chunks": 0,
              "removed_files": [], "warnings": []}

    try:
        owned = driver is None
        if owned:
            from labor_rag.services.neo4j import create_neo4j_driver
            driver = create_neo4j_driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                                         connection_timeout=10)
        with closing(driver) if owned else nullcontext():
            with driver.session(database=settings.NEO4J_DATABASE) as session:
                graph = remove_graph(session, settings.DATASET_ID, document_id, base)
    except Exception as exc:
        raise DocumentRemovalError(f"Chưa gỡ được khỏi đồ thị Neo4j ({type(exc).__name__}: {exc}).") from exc
    validity = graph.pop("validity")
    result["graph"] = graph

    try:
        owned = client is None
        if owned:
            from qdrant_client import QdrantClient
            client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None,
                                  timeout=settings.QDRANT_TIMEOUT)
        with closing(client) if owned else nullcontext():
            existing = indexed_chunks(client, collection, [document_id])
            remaining = [chunk for chunk in existing if chunk.get("source") != PDF_SOURCE]
            plan = plan_upsert(remaining, base.chunks_of(document_id))
            points = []
            if plan.upsert:  # embed first: a failure here leaves the PDF in place
                if embedder is None:
                    from labor_rag.services.embedding import EmbeddingProvider
                    embedder = EmbeddingProvider(settings)
                vectors = embedder.encode([chunk["text"] for chunk in plan.upsert], batch_size=16)
                size = getattr(client.get_collection(collection).config.params.vectors, "size", None)
                if size is not None and len(vectors[0]) != size:
                    raise ValueError("Số chiều embedding không khớp collection.")
                points = [PointStruct(id=point_id(chunk["chunk_id"]), vector=list(map(float, vector)),
                                      payload={**chunk, "dataset_id": settings.DATASET_ID})
                          for chunk, vector in zip(plan.upsert, vectors)]
            written = {chunk["chunk_id"] for chunk in plan.upsert}
            pdf_points = [point_id(chunk["chunk_id"]) for chunk in existing if chunk.get("source") == PDF_SOURCE]
            stale = [point_id(chunk_id) for chunk_id in plan.delete if chunk_id not in written]
            if pdf_points or stale:
                from qdrant_client.models import PointIdsList
                client.delete(collection, points_selector=PointIdsList(points=pdf_points + stale), wait=True)
            for start in range(0, len(points), 64):
                client.upsert(collection, points=points[start:start + 64], wait=True)
            for doc, valid_to in validity.items():
                selector = Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=doc))])
                client.set_payload(collection, payload={"effective_to_date": valid_to}, points=selector, wait=True)
    except Exception as exc:
        raise DocumentRemovalError(
            f"Đã gỡ khỏi đồ thị nhưng chưa cập nhật được Qdrant ({type(exc).__name__}: {exc}). Hãy thử gỡ lại.") from exc
    result["deleted_chunks"] = len(pdf_points)
    result["restored_chunks"] = len(points)
    if validity:
        result["warnings"].append("Đã khôi phục hiệu lực của: " + ", ".join(sorted(validity)) + ".")

    pdf_dir = settings.INTERIM_DIR / "pdf_chunks"
    for path in sorted(pdf_dir.glob(f"{document_id}_*.jsonl")) if pdf_dir.exists() else []:
        path.unlink()
        result["removed_files"].append(path.name)
    return result
