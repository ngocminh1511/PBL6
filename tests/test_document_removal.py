"""Removing a loaded PDF: its chunks and graph writes go, the Phap dien
version of the same document comes back. Stores are in memory or faked."""
import json
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from labor_rag.ingest.chunk_schema import point_id
from labor_rag.services.removal import PhapDienBase, remove_pdf_document

DOC = "45-2019-qh14"


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def chunk(cid, text, source, **extra):
    return {"chunk_id": cid, "document_id": extra.pop("document_id", DOC), "text": text, "source": source,
            "version_date": "2021-01-01" if source == "phap_dien" else "2026-01-01",
            "meta_dieu": cid.rsplit(":d", 1)[-1], "ten": "", **extra}


class FakeSession:
    """The Cypher calls of remove_graph, over a dict graph."""

    def __init__(self, nodes, rels):
        self.nodes, self.rels = nodes, rels  # id -> props; element id -> (source, type, target, predicate)

    def run(self, query, **p):
        if "OPTIONAL MATCH" in query:
            rows = []
            for nid, props in self.nodes.items():
                if props.get("document_id") != p["document"]:
                    continue
                touching = [(rid, r) for rid, r in self.rels.items() if nid in (r[0], r[2])]
                for rid, (s, t, e, pred) in touching or [(None, (None, None, None, None))]:
                    other = e if s == nid else s
                    rows.append({"id": nid, "props": props, "rel": rid, "type": t, "predicate": pred,
                                 "source": s, "target": e, "other": other, "other_props": self.nodes.get(other)})
            return rows
        if "DELETE r" in query:
            for rid in p["rels"]:
                self.rels.pop(rid, None)
        elif "DETACH DELETE" in query:
            for nid in p["ids"]:
                self.nodes.pop(nid, None)
                self.rels = {k: r for k, r in self.rels.items() if nid not in (r[0], r[2])}
        elif "NOT (n)--()" in query:
            gone = [nid for nid in p["ids"] if not any(nid in (r[0], r[2]) for r in self.rels.values())]
            for nid in gone:
                self.nodes.pop(nid)
            return [{"id": nid} for nid in gone]
        elif "SET n = item" in query:
            for item in p["items"]:
                self.nodes[item["id"]] = dict(item)
        return []


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self, **kwargs):
        from contextlib import nullcontext
        return nullcontext(self._session)


class Embedder:
    def encode(self, texts, batch_size=16):
        return [[1.0, 0.0] for _ in texts]


@pytest.fixture
def world(tmp_path):
    kg = tmp_path / "kg"
    kg.mkdir()
    write_jsonl(kg / "kg_nodes.jsonl", [
        {"id": "vb45", "label": "VanBan", "document_id": DOC, "ten": "Bộ luật Lao động"},
        {"id": "vb10", "label": "VanBan", "document_id": "10-2012-qh13", "ten": "BLLĐ 2012"},
        {"id": "d1", "label": "SourceComponent", "document_id": DOC, "article_number": "1"},
    ])
    write_jsonl(kg / "kg_edges.jsonl", [{"source": "vb45", "type": "CONTAINS", "target": "d1",
                                         "predicate_iri": "p:contains"}])
    write_jsonl(kg / "chunks.jsonl", [chunk(f"{DOC}:d1", "Điều 1 Pháp điển.", "phap_dien"),
                                      chunk(f"{DOC}:d2", "Điều 2 Pháp điển.", "phap_dien")])
    pdf_dir = tmp_path / "interim" / "pdf_chunks"
    pdf_dir.mkdir(parents=True)
    for name in ["chunks", "hierarchical", "footnotes"]:
        (pdf_dir / f"{DOC}_{name}.jsonl").write_text("{}\n", encoding="utf-8")
    (pdf_dir / "124-2025-qh15_chunks.jsonl").write_text("{}\n", encoding="utf-8")

    store = QdrantClient(":memory:")
    store.create_collection("test", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    payloads = [
        chunk(f"{DOC}:d1", "Điều 1 từ PDF.", "pdf"),           # the PDF won Dieu 1
        chunk(f"{DOC}:d2", "Điều 2 Pháp điển.", "phap_dien"),   # untouched
        chunk(f"{DOC}:d3", "Điều 3 chỉ có trong PDF.", "pdf"),
        chunk("10-2012-qh13:d1", "BLLĐ 2012.", "phap_dien", document_id="10-2012-qh13",
              effective_to_date="2026-01-01"),
    ]
    store.upsert("test", points=[PointStruct(id=point_id(p["chunk_id"]), vector=[0.0, 1.0], payload=p)
                                 for p in payloads])
    session = FakeSession(
        nodes={"vb45": {"id": "vb45", "label": "VanBan", "document_id": DOC, "ten": "Từ PDF", "dataset_id": "ds"},
               "vb10": {"id": "vb10", "label": "VanBan", "document_id": "10-2012-qh13", "ten": "BLLĐ 2012",
                        "valid_to": "2026-01-01", "dataset_id": "ds"},
               "d1": {"id": "d1", "label": "SourceComponent", "document_id": DOC, "article_number": "1",
                      "dataset_id": "ds"},
               "d3": {"id": "d3", "label": "SourceComponent", "document_id": DOC, "dataset_id": "ds"},
               "ev": {"id": "ev", "label": "AmendmentEvent", "dataset_id": "ds"},
               "stub": {"id": "stub", "label": "VanBan", "document_id": "74-2014-qh13", "dataset_id": "ds"}},
        rels={"r1": ("vb45", "CONTAINS", "d1", "p:contains"), "r2": ("vb45", "CONTAINS", "d3", "p:contains"),
              "r3": ("vb45", "REPLACES", "vb10", "p:replaces"), "r4": ("d3", "HAS_AMENDMENT", "ev", "p:amend"),
              "r5": ("vb45", "REPLACES", "stub", "p:replaces")},
    )
    settings = SimpleNamespace(QDRANT_COLLECTION="test", DATASET_ID="ds", NEO4J_DATABASE="neo4j",
                               INTERIM_DIR=tmp_path / "interim")
    return settings, PhapDienBase(kg), store, session, pdf_dir


def payloads(store):
    points, _ = store.scroll("test", limit=100, with_payload=True)
    return {p.payload["chunk_id"]: p.payload for p in points}


def test_removal_restores_phap_dien_and_undoes_graph_writes(world):
    settings, base, store, session, pdf_dir = world
    result = remove_pdf_document(settings, DOC, base=base, client=store, driver=FakeDriver(session),
                                 embedder=Embedder())

    left = payloads(store)
    assert left[f"{DOC}:d1"]["text"] == "Điều 1 Pháp điển." and left[f"{DOC}:d1"]["source"] == "phap_dien"
    assert f"{DOC}:d3" not in left and left[f"{DOC}:d2"]["source"] == "phap_dien"
    assert left["10-2012-qh13:d1"]["effective_to_date"] is None  # the PDF no longer replaces it
    assert (result["deleted_chunks"], result["restored_chunks"]) == (2, 1)

    assert set(session.nodes) == {"vb45", "vb10", "d1"}  # d3, event and orphaned stub removed
    assert session.nodes["vb45"]["ten"] == "Bộ luật Lao động" and "valid_to" not in session.nodes["vb10"]
    assert set(session.rels) == {"r1"}
    assert sorted(result["removed_files"]) == [f"{DOC}_{n}.jsonl" for n in ["chunks", "footnotes", "hierarchical"]]
    assert (pdf_dir / "124-2025-qh15_chunks.jsonl").exists()


def test_a_failing_graph_leaves_the_vector_store_untouched(world):
    from labor_rag.services.removal import DocumentRemovalError
    settings, base, store, _, pdf_dir = world

    class Down:
        def session(self, **kwargs):
            raise ConnectionError("neo4j down")

    before = payloads(store)
    with pytest.raises(DocumentRemovalError, match="Neo4j"):
        remove_pdf_document(settings, DOC, base=base, client=store, driver=Down(), embedder=Embedder())
    assert payloads(store) == before and (pdf_dir / f"{DOC}_chunks.jsonl").exists()
