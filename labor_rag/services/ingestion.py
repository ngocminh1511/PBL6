"""Legal uploads use the same ontology, chunk IDs and version merge as the CLI."""
import hashlib
import inspect
import json
from contextlib import closing
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from labor_rag.config import LAO_DONG_DIR, LAO_DONG_ABOX_PATH, SCHEMA_V4_PATH, INTERIM_DIR


class IngestionInputError(ValueError):
    """Safe, user-facing validation failure."""


class IngestionCancelledError(Exception):
    """Raised when the user requests cancellation of an active ingestion task."""


def jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def document_tree(document):
    """Normalize OCR's actual hierarchy to the common UI tree."""
    def strip_num(val, prefix):
        text = str(val or "").strip()
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
        return text or None

    def node(item, kind):
        number = getattr(item, kind + "_number", "")
        title = getattr(item, kind + "_title", "") or getattr(item, "title", "")
        text = "" if kind == "document" else (getattr(item, "text", "") or getattr(item, "full_text", ""))
        children = []
        for child_kind, field in [("part", "parts"), ("chapter", "chapters"), ("section", "sections"),
                                   ("article", "articles"), ("clause", "clauses"), ("point", "points")]:
            children.extend(node(child, child_kind) for child in getattr(item, field, []))
        payload = {
            "id": getattr(item, kind + "_id", document.document_id),
            "type": kind,
            "title": title if kind == "article" else (text[:90] if kind in {"clause", "point"} and not title else " ".join(v for v in [number, title] if v)),
            "text": text,
            "children": children,
        }
        if kind == "article":
            payload["article_number"] = strip_num(number, "Điều")
        elif kind == "clause":
            payload["clause_number"] = strip_num(number, "Khoản")
        elif kind == "point":
            payload["point_number"] = getattr(item, "point_label", None) or strip_num(number, "Điểm")
        return payload
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

    def _summarize_ocr(self, extraction, document=None, ocr_quality=None) -> dict:
        pages = getattr(extraction, "pages", []) if extraction else []
        return {
            "total_pages": getattr(extraction, "total_pages", 0) if extraction else 0,
            "text_pages": sum(1 for p in pages if p.method == "text"),
            "ocr_pages": len(getattr(extraction, "scanned_pages", [])) if extraction else 0,
            "empty_pages": sum(1 for p in pages if p.method in {"empty", "skipped"}),
            "avg_confidence": round(extraction.ocr_confidence, 4) if extraction and extraction.ocr_confidence is not None else None,
            "heuristic_score": (ocr_quality or {}).get("heuristic_score"),
            "articles_count": sum(1 for _ in document.iter_articles()) if document is not None else None,
            "warnings": list(getattr(extraction, "warnings", []) or []) if extraction else [],
        }

    def _pdf_page_writer(self, ocr_pages_file: Path, on_page):
        ocr_pages_file.write_text("", encoding="utf-8")

        def handle_page(page_text, total_pages: int):
            conf = round(page_text.confidence, 4) if page_text.confidence is not None else None
            full_entry = {
                "page_number": page_text.page_number + 1,
                "total_pages": total_pages,
                "method": page_text.method,
                "confidence": conf,
                "char_count": len(page_text.text),
                "text": page_text.text,
            }
            with ocr_pages_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(full_entry, ensure_ascii=False) + "\n")
            if on_page:
                on_page({
                    "page_number": full_entry["page_number"],
                    "total_pages": total_pages,
                    "method": page_text.method,
                    "confidence": conf,
                    "char_count": full_entry["char_count"],
                    "preview_text": page_text.text[:600].strip(),
                })

        return handle_page

    def extract_only(self, path, task_id, document_type="pdf", *, progress=None, cancel_check=None, on_page=None, on_ocr_summary=None):
        """Phase 1: extract raw text/OCR page by page into ocr_pages.jsonl and pause before chunking/indexing."""
        from labor_rag.ocr.pipeline import extract_document_pages

        if document_type != "pdf":
            raise IngestionInputError("Chỉ hỗ trợ tách pha kiểm tra OCR cho tài liệu PDF.")
        progress = progress or (lambda *args, **kwargs: None)

        def check_cancelled():
            if cancel_check and cancel_check():
                raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")

        check_cancelled()
        config = self.settings
        work = config.INTERIM_DIR / "ingestion" / task_id
        work.mkdir(parents=True, exist_ok=True)
        progress(10, "parsing", "Đang khởi tạo bộ đọc và phân tích tài liệu...")

        handle_page = self._pdf_page_writer(work / "ocr_pages.jsonl", on_page)

        def ocr_progress(msg: str, pct: float):
            check_cancelled()
            progress(round(10 + 0.18 * pct, 1), "parsing", f"Đang nhận dạng văn bản ({msg})...")

        extraction = extract_document_pages(path, settings=config, progress=ocr_progress, page_callback=handle_page)
        check_cancelled()
        summary = self._summarize_ocr(extraction)
        if on_ocr_summary:
            on_ocr_summary(summary)
        return {"ocr_summary": summary, "work_dir": str(work)}

    def finalize_extracted(self, path, task_id, document_type="pdf", *, domain="lao_dong", de_muc_id=None, progress=None, cancel_check=None, on_ocr_summary=None):
        """Phase 2: rebuild ExtractionResult from (optionally edited) ocr_pages.jsonl and index the document."""
        from labor_rag.ingest.pdf_to_chunks import KgIndex
        from labor_rag.ocr.extract import ExtractionResult, PageText
        from labor_rag.ocr.pipeline import build_processed_document

        if document_type != "pdf":
            raise IngestionInputError("Chỉ hỗ trợ xác nhận lập chỉ mục từ trang OCR cho tài liệu PDF.")
        progress = progress or (lambda *args, **kwargs: None)

        def check_cancelled():
            if cancel_check and cancel_check():
                raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")

        check_cancelled()
        config = self.settings
        work = config.INTERIM_DIR / "ingestion" / task_id
        pages_file = work / "ocr_pages.jsonl"
        if not pages_file.exists():
            raise IngestionInputError("Không tìm thấy dữ liệu trang OCR đã tách; vui lòng nạp lại file PDF.")
        entries = [json.loads(line) for line in pages_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        entries.sort(key=lambda item: int(item.get("page_number") or 0))
        pages = [
            PageText(
                page_number=max(0, int(item["page_number"]) - 1),
                text=str(item.get("text") or ""),
                method=str(item.get("method") or "text"),
                confidence=item.get("confidence"),
            )
            for item in entries
        ]
        if not pages:
            raise IngestionInputError("Dữ liệu trang OCR trống; vui lòng nạp lại file PDF.")
        extraction = ExtractionResult(source_name=Path(path).name, pages=pages)
        progress(30, "chunking", "Đang tách cấu trúc Chương, Mục, Điều, Khoản, Điểm từ nội dung đã kiểm tra...")
        processed = build_processed_document(extraction)
        check_cancelled()

        kg = KgIndex.load(LAO_DONG_DIR) if domain == "lao_dong" and (LAO_DONG_DIR / "kg_nodes.jsonl").exists() else None
        abox_dir = work / "abox"
        abox_dir.mkdir(exist_ok=True)
        return self._finish_pdf_ingestion(
            path,
            work,
            abox_dir,
            processed,
            task_id,
            domain,
            kg,
            progress,
            check_cancelled,
            on_ocr_summary=on_ocr_summary,
        )

    def _finish_pdf_ingestion(self, path, work, abox_dir, processed, task_id, domain, kg, progress, check_cancelled, on_ocr_summary=None):
        from labor_rag.ingest.chunk_schema import TokenCounter
        from labor_rag.ingest.pdf_abox import document_abox
        from labor_rag.ingest.pdf_to_chunks import document_to_chunks
        from labor_rag.ocr.export import export_hierarchical

        config = self.settings
        document = processed.document
        extraction = getattr(processed, "extraction", None)
        ocr_quality = getattr(processed, "ocr_quality", None) or {}
        warnings = list(getattr(extraction, "warnings", []) or []) if extraction is not None else []
        ocr_summary = self._summarize_ocr(extraction, document=document, ocr_quality=ocr_quality)
        if on_ocr_summary:
            on_ocr_summary(ocr_summary)
        progress(31, "chunking", "Đang tách cấu trúc Chương, Mục, Điều, Khoản, Điểm...")
        if not document.metadata.so_hieu or not list(document.iter_articles()):
            raise IngestionInputError("PDF thiếu số hiệu hoặc cấu trúc Điều luật; cần kiểm tra lại tài liệu nguồn.")
        chunks, chunk_warnings = document_to_chunks(document, kg=kg, count=TokenCounter(config.EMBEDDING_MODEL))
        warnings.extend(chunk_warnings)
        for chunk in chunks:
            chunk["domain"] = domain
        builder, _ = document_abox(document, kg)
        if builder is None:
            raise IngestionInputError("Không dựng được cấu trúc dữ liệu pháp lý cho PDF.")
        abox_path = abox_dir / (document.document_id + ".ttl")
        builder.serialize(abox_path)
        trees = {document.document_id: document_tree(document)}
        (work / "document.json").write_text(document.model_dump_json(indent=2), encoding="utf-8")

        pdf_chunks_dir = config.INTERIM_DIR / "pdf_chunks"
        pdf_chunks_dir.mkdir(parents=True, exist_ok=True)
        export_hierarchical(document, pdf_chunks_dir / f"{document.document_id}_hierarchical.jsonl")
        with (pdf_chunks_dir / f"{document.document_id}_chunks.jsonl").open("w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        if domain == "lao_dong" and LAO_DONG_ABOX_PATH.exists():
            projection_source = LAO_DONG_ABOX_PATH
            pdf_abox_arg = abox_dir
        else:
            projection_source = abox_path
            pdf_abox_arg = work / "empty_pdf_abox"

        return self._project_and_index(
            path,
            work,
            "pdf",
            domain,
            abox_path,
            projection_source,
            pdf_abox_arg,
            chunks,
            trees,
            warnings,
            ocr_summary,
            progress,
            check_cancelled,
        )

    def _project_and_index(self, path, work, document_type, domain, abox_path, projection_source, pdf_abox_arg, chunks, trees, warnings, ocr_summary, progress, check_cancelled):
        from labor_rag.ingest.ontology_to_jsonl import project

        config = self.settings
        check_cancelled()
        progress(32, "chunking", "Đang chuẩn hóa cấu trúc dữ liệu và lưu trữ bản gốc...")
        projection = work / "projection"
        project(SimpleNamespace(abox=projection_source, pdf_abox_dir=pdf_abox_arg,
            schema=SCHEMA_V4_PATH, out_dir=projection, dataset_id=config.DATASET_ID,
            max_tokens=1024 if document_type == "phap_dien_html" else 0, text_variant="full"))
        if document_type == "phap_dien_html":
            chunks = jsonl(projection / "chunks.jsonl")
            for chunk in chunks:
                chunk["domain"] = domain
        if not chunks:
            raise IngestionInputError("Tài liệu không tạo được đoạn nội dung hợp lệ.")
        check_cancelled()
        ids = sorted({c["document_id"] for c in chunks})
        nodes, edges = jsonl(projection / "kg_nodes.jsonl"), jsonl(projection / "kg_edges.jsonl")
        # All durable objects are content-addressed; retries cannot overwrite an unrelated source.
        artifacts = [store_artifact(path, self.store, "source"),
                     store_artifact(abox_path, self.store, "ontology")]
        if (work / "document.json").exists():
            artifacts.append(store_artifact(work / "document.json", self.store, "hierarchy"))
        check_cancelled()
        progress(45, "embedding", "Đang xử lý ngữ nghĩa văn bản phục vụ tìm kiếm...", total_chunks=len(chunks))
        indexed = self.index(chunks, projection, progress, cancel_check=cancel_check)
        warnings.extend(indexed["warnings"])
        documents = []
        for document_id in ids:
            own_nodes = [n for n in nodes if n.get("document_id") == document_id]
            own_ids = {n["id"] for n in own_nodes}
            document = next((n for n in own_nodes if n.get("label") == "VanBan"), {})
            own_chunks = [c for c in chunks if c["document_id"] == document_id]
            doc_title = document.get("ten") or own_chunks[0].get("meta_de_muc") or document_id
            tree = trees.get(document_id) or {
                "id": document_id, "type": "document", "title": doc_title,
                "children": [{"id": c["chunk_id"], "type": "article", "title": c.get("ten", ""),
                    "text": c["text"], "children": []} for c in own_chunks],
            }
            if not tree.get("title"):
                tree["title"] = doc_title
            documents.append({"id": document_id, "title": doc_title,
                "document_number": document.get("document_number"),
                "effective_from_date": document.get("effective_date"),
                "chunks_count": len(own_chunks), "nodes_count": len(own_nodes),
                "edges_count": sum(e["source"] in own_ids for e in edges),
                "ast_tree_json": tree, "document_type": document_type, "domain": domain,
                "status": "completed", "file_path": artifacts[0]["artifact_id"]})
        return {"document_ids": ids, "documents": documents, "artifacts": artifacts,
                "warnings": warnings, "total_chunks": len(chunks),
                "embedded_chunks": indexed["embedded_chunks"],
                "reused_chunks": len(chunks) - indexed["embedded_chunks"],
                "ocr_summary": ocr_summary}

    def run(self, path, task_id, document_type, *, domain="lao_dong", de_muc_id=None, progress=None, cancel_check=None, on_page=None, on_ocr_summary=None):
        from labor_rag.ingest.pdf_to_chunks import KgIndex
        progress = progress or (lambda *args, **kwargs: None)

        def check_cancelled():
            if cancel_check and cancel_check():
                raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")

        check_cancelled()
        config = self.settings
        work = config.INTERIM_DIR / "ingestion" / task_id
        work.mkdir(parents=True, exist_ok=True)
        kg = KgIndex.load(LAO_DONG_DIR) if domain == "lao_dong" and (LAO_DONG_DIR / "kg_nodes.jsonl").exists() else None
        abox_dir = work / "abox"
        abox_dir.mkdir(exist_ok=True)
        progress(10, "parsing", "Đang khởi tạo bộ đọc và phân tích tài liệu...")
        trees = {}
        warnings = []
        if document_type == "pdf":
            from labor_rag.ocr.pipeline import process_document

            handle_page = self._pdf_page_writer(work / "ocr_pages.jsonl", on_page)

            def ocr_progress(msg: str, pct: float):
                check_cancelled()
                progress(round(10 + 0.18 * pct, 1), "parsing", f"Đang nhận dạng văn bản ({msg})...")

            ocr_kwargs = {"settings": config, "progress": ocr_progress}
            params = inspect.signature(process_document).parameters
            if "page_callback" in params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
                ocr_kwargs["page_callback"] = handle_page
            processed = process_document(path, **ocr_kwargs)
            check_cancelled()
            return self._finish_pdf_ingestion(
                path,
                work,
                abox_dir,
                processed,
                task_id,
                domain,
                kg,
                progress,
                check_cancelled,
                on_ocr_summary=on_ocr_summary,
            )
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
            pdf_abox_arg = abox_dir
            chunks = []
        else:
            raise IngestionInputError("Chỉ hỗ trợ PDF và HTML Pháp điển.")
        return self._project_and_index(
            path,
            work,
            document_type,
            domain,
            abox_path,
            projection_source,
            pdf_abox_arg,
            chunks,
            trees,
            warnings,
            None,
            progress,
            check_cancelled,
        )

    def index(self, chunks, projection, progress, cancel_check=None):
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
                if cancel_check and cancel_check():
                    raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")
                batch = plan.upsert[start:start + 16]
                vectors = self.embedder.encode([c["text"] for c in batch], batch_size=16)
                params = info.config.params.vectors
                if not hasattr(params, "size") or len(vectors[0]) != params.size:
                    raise IngestionInputError("Số chiều embedding không khớp collection cloud.")
                points.extend(PointStruct(id=point_id(c["chunk_id"]), vector=v.tolist(),
                    payload={**c, "dataset_id": config.DATASET_ID}) for c, v in zip(batch, vectors))
                progress(round(45 + 30 * min(start + 16, len(plan.upsert)) / max(len(plan.upsert), 1), 1),
                    "embedding", "Đang tạo chỉ mục tìm kiếm ngữ nghĩa...", embedded_chunks=min(start + 16, len(plan.upsert)))
            if cancel_check and cancel_check():
                raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")
            progress(80, "indexing", "Đang cập nhật liên kết điều khoản vào kho dữ liệu...")
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
        progress(95, "indexing", "Đang hoàn tất đồng bộ kho dữ liệu tra cứu...")
        return {"warnings": plan.warnings, "embedded_chunks": len(plan.upsert)}


def update_document_domain(settings, document_id: str, domain: str) -> bool:
    """Update domain metadata on local OCR chunks and Qdrant points without re-running OCR."""
    updated = False
    chunks_path = settings.INTERIM_DIR / "pdf_chunks" / f"{document_id}_chunks.jsonl"
    if chunks_path.exists():
        lines = []
        for raw in chunks_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            item["domain"] = domain
            lines.append(json.dumps(item, ensure_ascii=False))
        chunks_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        updated = True
    if settings.QDRANT_URL:
        from qdrant_client import QdrantClient
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        with closing(QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None,
                                  timeout=settings.QDRANT_TIMEOUT)) as client:
            selector = Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
            if client.count(settings.QDRANT_COLLECTION, count_filter=selector, exact=True).count:
                client.set_payload(settings.QDRANT_COLLECTION, payload={"domain": domain}, points=selector, wait=True)
                updated = True
    return updated
