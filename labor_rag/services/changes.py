"""What confirming a reviewed PDF would change, before anything is written.

It builds the chunks of the reviewed OCR pages exactly as indexing does
(services/ingestion.py), reads the chunks already indexed for the same
document and runs the same merge decision (ingest/merge.py), per Dieu:

- new: only in the PDF; replaced: the PDF wins and its text differs;
- metadata: same text, only payload fields change; unchanged: identical;
- kept: the indexed version is newer, so indexing will refuse the PDF;
- missing: indexed but not found in the PDF (often an OCR miss), kept as is.

An amending document also lists, per khoan, the Dieu of other documents it
amends (ingest/amending.py), with the current indexed text of each target.
Nothing here writes to the vector store or the graph.
"""
from __future__ import annotations

from contextlib import closing, nullcontext

from labor_rag.config import LAO_DONG_DIR
from labor_rag.services.ingestion import IngestionInputError, reviewed_extraction

ACTION_LABELS = {"sua_doi": "Sửa đổi", "bo_sung": "Bổ sung", "bai_bo": "Bãi bỏ", "thay_cum_tu": "Thay cụm từ"}
INSTRUCTION_LIMIT = 2000


def _label(chunk: dict) -> str:
    return f"Điều {chunk['meta_dieu']}" if chunk.get("meta_dieu") else str(chunk.get("ten") or "Phụ lục")


def _text(parts: list[dict]) -> str:
    return "\n".join(str(part.get("text") or "") for part in parts)


def _article_status(key, new_groups, old_groups, plan) -> str:
    if key not in old_groups:
        return "new"
    if key not in new_groups:
        return "missing"
    if key in plan.kept:
        return "kept"
    if key in plan.unchanged:
        return "unchanged"
    refreshed = {chunk["chunk_id"] for chunk in plan.refresh}
    if any(part["chunk_id"] in refreshed for part in new_groups[key]):
        return "metadata"
    return "replaced"


def build_reviewed_chunks(settings, task_id: str, path, domain: str):
    """(document, chunks) of the reviewed pages, as finalize_extracted builds them."""
    from labor_rag.ingest.chunk_schema import TokenCounter
    from labor_rag.ingest.pdf_to_chunks import KgIndex, document_to_chunks
    from labor_rag.ocr.pipeline import build_processed_document

    work = settings.INTERIM_DIR / "ingestion" / task_id
    document = build_processed_document(reviewed_extraction(work, path)).document
    if not document.metadata.so_hieu or not list(document.iter_articles()):
        raise IngestionInputError("Chưa nhận diện được số hiệu hoặc Điều luật nào từ nội dung đã rà soát.")
    kg = KgIndex.load(LAO_DONG_DIR) if domain == "lao_dong" and (LAO_DONG_DIR / "kg_nodes.jsonl").exists() else None
    chunks, _ = document_to_chunks(document, kg=kg, count=TokenCounter(settings.EMBEDDING_MODEL))
    for chunk in chunks:
        chunk["domain"] = domain
    return document, chunks


def amendments_of(document) -> tuple[list[dict], list[dict]]:
    """(amended Dieu of other documents, documents this one replaces)."""
    from labor_rag.ingest.amending import replaced_documents
    from labor_rag.ingest.chunk_schema import nfc
    from labor_rag.ingest.pdf_to_chunks import amending_units, article_body, iter_articles

    amendments, replaced, seen = [], [], set()
    for _, _, _, article in iter_articles(document):
        source = nfc(f"{article.article_number}. {article.article_title}".strip(". "))
        for targets, khoan, body in amending_units(article) or []:
            for target in targets:
                amendments.append({
                    "source_article": source,
                    "source_clause": f"Khoản {khoan}" if khoan else None,
                    "actions": [ACTION_LABELS.get(action, action) for action in target.actions],
                    "target_document": f"{target.document.kind} {target.document.number}",
                    "target_document_id": target.document.document_id,
                    "target_article_id": target.article,
                    "target_article": f"Điều {target.dieu}",
                    "scope": target.scope,
                    "instruction": body[:INSTRUCTION_LIMIT],
                })
        for ref in replaced_documents(article.article_title, nfc(article_body(article)), document.document_id):
            if ref.document_id not in seen:
                seen.add(ref.document_id)
                replaced.append({"document": f"{ref.kind} {ref.number}", "document_id": ref.document_id})
    return amendments, replaced


def preview_changes(settings, task_id: str, path, domain: str = "lao_dong", *, client=None) -> dict:
    """The per-Dieu change list of a task awaiting review; the store is only read.

    ``store`` is "connected" when the indexed side was read, "unavailable"
    otherwise; then each Dieu's status is None rather than guessed.
    """
    from labor_rag.ingest.embed_and_index import indexed_chunks
    from labor_rag.ingest.merge import group_by_article, plan_upsert

    document, chunks = build_reviewed_chunks(settings, task_id, path, domain)
    amendments, replaced = amendments_of(document)
    result = {
        "document_id": document.document_id,
        "document_number": document.metadata.so_hieu,
        "title": document.title or document.metadata.so_hieu,
        "version_date": chunks[0].get("version_date") if chunks else None,
        "store": "connected",
        "store_error": None,
        "articles": [],
        "amendments": amendments,
        "replaced_documents": replaced,
        "warnings": [],
    }
    targets = sorted({item["target_document_id"] for item in amendments} | {item["document_id"] for item in replaced})
    try:
        owned = client is None  # a client passed in belongs to the caller
        if owned:
            from qdrant_client import QdrantClient
            client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None,
                                  timeout=settings.QDRANT_TIMEOUT)
        with closing(client) if owned else nullcontext():
            existing = indexed_chunks(client, settings.QDRANT_COLLECTION, [document.document_id])
            others = indexed_chunks(client, settings.QDRANT_COLLECTION, targets) if targets else []
    except Exception as exc:  # the comparison is unavailable, the parsed side is still shown
        result.update(store="unavailable", store_error=f"{type(exc).__name__}: {exc}")
        existing = others = None

    new_groups = group_by_article(chunks)
    old_groups = group_by_article(existing or [])
    plan = plan_upsert(existing, chunks) if existing is not None else None
    if plan is not None:
        result["warnings"] = plan.warnings
    keys = list(new_groups) + [key for key in old_groups if key not in new_groups]
    for key in keys:
        new_parts, old_parts = new_groups.get(key, []), old_groups.get(key, [])
        sample = (new_parts or old_parts)[0]
        result["articles"].append({
            "article_id": key,
            "label": _label(sample),
            "title": str(sample.get("ten") or ""),
            "status": _article_status(key, new_groups, old_groups, plan) if plan is not None else None,
            "new_text": _text(new_parts) if new_parts else None,
            "old_text": _text(old_parts) if old_parts else None,
            "old_source": old_parts[0].get("source") if old_parts else None,
            "old_version_date": old_parts[0].get("version_date") if old_parts else None,
        })

    indexed_targets = group_by_article(others or [])
    indexed_documents = {chunk.get("document_id") for chunk in others or []}
    for item in amendments:
        parts = indexed_targets.get(item["target_article_id"], [])
        item["target_indexed"] = bool(parts) if others is not None else None
        item["current_text"] = _text(parts) if parts else None
    for item in replaced:
        item["indexed"] = item["document_id"] in indexed_documents if others is not None else None
    return result
