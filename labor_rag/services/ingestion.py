"""Legal uploads use the same ontology, chunk IDs and version merge as the CLI."""
import hashlib
import json
from contextlib import closing
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from labor_rag.config import LAO_DONG_DIR, LAO_DONG_ABOX_PATH, SCHEMA_V4_PATH, INTERIM_DIR


class IngestionInputError(ValueError):
    """Safe, user-facing validation failure."""


def jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def document_tree(document):
    """Normalize OCR's actual hierarchy to the common UI tree."""
    def node(item, kind):
        number = getattr(item, kind + "_number", "")
        title = getattr(item, kind + "_title", "") or getattr(item, "title", "")
        children = []
        for child_kind, field in [("part", "parts"), ("chapter", "chapters"), ("section", "sections"),
                                   ("article", "articles"), ("clause", "clauses"), ("point", "points")]:
            children.extend(node(child, child_kind) for child in getattr(item, field, []))
        return {"id": getattr(item, kind + "_id", document.document_id), "type": kind,
                "title": " ".join(v for v in [number, title] if v),
                "text": getattr(item, "text", "") or getattr(item, "full_text", ""),
                "children": children}
    return node(document, "document")


def store_artifact(path, store, role):
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    remote = store.upload_verified(path, digest, filename=path.name)
    return {"artifact_id": "upload-" + digest, "sha256": digest, "bytes": len(payload),
            "file_name": path.name, "format": path.suffix.lstrip(".").lower(), "role": role,
            "path": str(path.resolve()),
            "storage_backend": "r2", "r2": remote}


class IngestionPipeline:
    def __init__(self, settings, store, *, embedder=None):
        from labor_rag.services.embedding import EmbeddingProvider
        self.settings = settings
        self.store = store
        self.embedder = embedder or EmbeddingProvider(settings)

    def run(self, path, task_id, document_type, *, de_muc_id=None, progress=None):
        from labor_rag.ingest.pdf_to_chunks import KgIndex, document_to_chunks
        from labor_rag.ingest.chunk_schema import TokenCounter
        from labor_rag.ingest.ontology_to_jsonl import project
        progress = progress or (lambda *args, **kwargs: None)
        config = self.settings
        work = config.INTERIM_DIR / "ingestion" / task_id
        work.mkdir(parents=True, exist_ok=True)
        kg = KgIndex.load(LAO_DONG_DIR)
        abox_dir = work / "abox"
        abox_dir.mkdir(exist_ok=True)
        progress(10, "parsing", "Đang phân tích tài liệu.")
        trees = {}
        warnings = []
        if document_type == "pdf":
            from labor_rag.ocr.pipeline import process_document
            from labor_rag.ingest.pdf_abox import document_abox
            document = process_document(path).document
            if not document.metadata.so_hieu or not list(document.iter_articles()):
                raise IngestionInputError("PDF thiếu số hiệu hoặc cấu trúc Điều luật; cần kiểm tra nguồn OCR.")
            chunks, warnings = document_to_chunks(document, kg=kg, count=TokenCounter(config.EMBEDDING_MODEL))
            builder, _ = document_abox(document, kg)
            if builder is None:
                raise IngestionInputError("Không dựng được ABox cho PDF.")
            abox_path = abox_dir / (document.document_id + ".ttl")
            builder.serialize(abox_path)
            trees[document.document_id] = document_tree(document)
            (work / "document.json").write_text(document.model_dump_json(indent=2), encoding="utf-8")
            projection_source = LAO_DONG_ABOX_PATH
        elif document_type == "phap_dien_html":
            from labor_rag.ingest.parse_demuc_html import parse_demuc_nodes
            from labor_rag.ingest.build_abox import AboxBuilder
            from labor_rag.ingest.pdf_abox import graph_index
            tree = parse_demuc_nodes(path)
            # Resolve metadata from the versioned projection, so a fresh clone
            # and Docker do not depend on ignored data/interim/*.json files.
            source_nodes = jsonl(LAO_DONG_DIR / "kg_nodes.jsonl")
            topics = [node for node in source_nodes if node.get("label") == "ChuDe"]
            topic_name = topics[0].get("ten", "Lao động") if topics else "Lao động"
            known = {"20." + str(node["ontology_vlpd__itemNumber"]): node
                     for node in source_nodes if node.get("label") == "DeMuc"
                     and node.get("ontology_vlpd__itemNumber") is not None}
            code = de_muc_id or tree.get("de_muc_so")
            item = known.get(code)
            if item is None:
                raise IngestionInputError("Cần mã đề mục Pháp điển Lao động hợp lệ, ví dụ 20.2.")
            tree["de_muc_id"] = code
            builder = AboxBuilder()
            builder.index = graph_index(kg)
            builder.index_de_muc(tree)
            builder.add_de_muc(path, 20, topic_name, int(item["ontology_vlpd__itemNumber"]), item["ten"], tree)
            abox_path = work / "phap_dien.ttl"
            builder.serialize(abox_path)
            projection_source = abox_path
            chunks = []
        else:
            raise IngestionInputError("Chỉ hỗ trợ PDF và HTML Pháp điển.")
        progress(30, "chunking", "Đang dựng ABox và projection schema v5.")
        projection = work / "projection"
        project(SimpleNamespace(abox=projection_source, pdf_abox_dir=abox_dir,
            schema=SCHEMA_V4_PATH, out_dir=projection, dataset_id=config.DATASET_ID,
            max_tokens=1024 if document_type == "phap_dien_html" else 0, text_variant="full"))
        if document_type == "phap_dien_html":
            chunks = jsonl(projection / "chunks.jsonl")
        if not chunks:
            raise IngestionInputError("Tài liệu không tạo được chunk hợp lệ.")
        ids = sorted({c["document_id"] for c in chunks})
        nodes, edges = jsonl(projection / "kg_nodes.jsonl"), jsonl(projection / "kg_edges.jsonl")
        # All durable objects are content-addressed; retries cannot overwrite an unrelated source.
        artifacts = [store_artifact(path, self.store, "source"),
                     store_artifact(abox_path, self.store, "ontology")]
        if (work / "document.json").exists():
            artifacts.append(store_artifact(work / "document.json", self.store, "hierarchy"))
        progress(45, "embedding", "Đang embedding và chuẩn bị cập nhật cloud.", total_chunks=len(chunks))
        indexed = self.index(chunks, projection, progress)
        warnings.extend(indexed["warnings"])
        documents = []
        for document_id in ids:
            own_nodes = [n for n in nodes if n.get("document_id") == document_id]
            own_ids = {n["id"] for n in own_nodes}
            document = next((n for n in own_nodes if n.get("label") == "VanBan"), {})
            own_chunks = [c for c in chunks if c["document_id"] == document_id]
            tree = trees.get(document_id) or {
                "id": document_id, "type": "document", "title": document.get("ten") or document_id,
                "children": [{"id": c["chunk_id"], "type": "article", "title": c.get("ten", ""),
                    "text": c["text"], "children": []} for c in own_chunks],
            }
            documents.append({"id": document_id, "title": document.get("ten") or own_chunks[0].get("meta_de_muc") or document_id,
                "document_number": document.get("document_number"),
                "effective_from_date": document.get("effective_date"),
                "chunks_count": len(own_chunks), "nodes_count": len(own_nodes),
                "edges_count": sum(e["source"] in own_ids for e in edges),
                "ast_tree_json": tree, "document_type": document_type, "domain": "lao_dong",
                "status": "completed", "file_path": artifacts[0]["artifact_id"]})
        return {"document_ids": ids, "documents": documents, "artifacts": artifacts,
                "warnings": warnings, "total_chunks": len(chunks),
                "embedded_chunks": indexed["embedded_chunks"],
                "reused_chunks": len(chunks) - indexed["embedded_chunks"]}

    def index(self, chunks, projection, progress):
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct, PointIdsList
        from labor_rag.ingest.chunk_schema import point_id
        from labor_rag.ingest.embed_and_index import indexed_chunks, PAYLOAD_INDEXES, sync_validity
        from labor_rag.ingest.merge import plan_upsert
        from labor_rag.ingest.load_neo4j import load_projection
        config = self.settings
        with closing(QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY or None,
                          timeout=config.QDRANT_TIMEOUT)) as client:
            # Uploads never create or recreate a collection.
            info = client.get_collection(config.QDRANT_COLLECTION)
            existing = indexed_chunks(client, config.QDRANT_COLLECTION, sorted({c["document_id"] for c in chunks}))
            plan = plan_upsert(existing, chunks)
            if plan.kept:
                raise IngestionInputError("Cloud đã có phiên bản mới hơn; không cập nhật tài liệu cũ.")
            points = []
            for start in range(0, len(plan.upsert), 16):
                batch = plan.upsert[start:start + 16]
                vectors = self.embedder.encode([c["text"] for c in batch], batch_size=16)
                params = info.config.params.vectors
                if not hasattr(params, "size") or len(vectors[0]) != params.size:
                    raise IngestionInputError("Số chiều embedding không khớp collection cloud.")
                points.extend(PointStruct(id=point_id(c["chunk_id"]), vector=v.tolist(),
                    payload={**c, "dataset_id": config.DATASET_ID}) for c, v in zip(batch, vectors))
                progress(45 + 30 * min(start + 16, len(plan.upsert)) / max(len(plan.upsert), 1),
                    "embedding", "Đang embedding.", embedded_chunks=min(start + 16, len(plan.upsert)))
            progress(80, "indexing", "Đang MERGE đồ thị Neo4j.")
            load_projection(SimpleNamespace(data_dir=projection, uri=config.NEO4J_URI,
                user=config.NEO4J_USER, password=config.NEO4J_PASSWORD, database=config.NEO4J_DATABASE,
                dataset_id=config.DATASET_ID, replace_dataset=False))
            for field, schema in PAYLOAD_INDEXES.items():
                client.create_payload_index(config.QDRANT_COLLECTION, field_name=field, field_schema=schema)
            for start in range(0, len(points), 64):
                client.upsert(config.QDRANT_COLLECTION, points=points[start:start + 64], wait=True)
            written = {c["chunk_id"] for c in plan.upsert}
            stale = [point_id(cid) for cid in plan.delete if cid not in written]
            if stale:
                client.delete(config.QDRANT_COLLECTION, points_selector=PointIdsList(points=stale), wait=True)
            for chunk in plan.refresh:
                client.set_payload(config.QDRANT_COLLECTION,
                    payload={**chunk, "dataset_id": config.DATASET_ID}, points=[point_id(chunk["chunk_id"])], wait=True)
            sync_validity(client, config.QDRANT_COLLECTION, projection)
        progress(95, "indexing", "Đã cập nhật Neo4j và Qdrant.")
        return {"warnings": plan.warnings, "embedded_chunks": len(plan.upsert)}
