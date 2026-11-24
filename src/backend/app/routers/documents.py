import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from src.backend.app.dependencies import get_current_user, get_db
from src.backend.app.models.database import IngestionTask, DocumentRecord, User
from src.backend.app.models.schemas import (
    DocumentRemovalResponse,
    IngestionTaskSummary,
    OcrRevisionResponse,
    ReopenRequest,
    ConfirmRequest,
    DocumentResponse,
    DocumentASTResponse,
    IngestionTaskResponse,
    OCRPageDetail,
    OCRPageUpdateRequest,
    OCRPreviewSummary,
    TaskChangesResponse,
    UploadResponse,
    CursorPage,
    GraphResponse,
)
from src.backend.app.services.runtime import get_runtime
from src.backend.app.services.corpus import Corpus
from src.backend.app.services.graph import build_graph
from src.backend.app.utils.pagination import encode_cursor, decode_cursor

router = APIRouter(prefix="/documents", tags=["Documents"])

def _count_ast_stats(tree: dict | None) -> tuple[int, int, int]:
    if not isinstance(tree, dict):
        return (0, 0, 0)
    articles = clauses = points = 0
    stack = [tree]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        t = str(node.get("type") or "").lower()
        if node.get("point_number") or t in {"diem", "point"}:
            points += 1
        elif node.get("clause_number") or t in {"khoan", "clause"}:
            clauses += 1
        elif node.get("article_number") or t in {"dieu", "article"}:
            articles += 1
        children = node.get("children")
        if isinstance(children, list):
            stack.extend(children)
    return (articles, clauses, points)


@router.get("/list", response_model=CursorPage[DocumentResponse])
def list_documents(domain: Literal["all", "lao_dong", "khac"] = "all",
    document_type: Literal["all", "phap_dien_html", "pdf"] = "all",
    search: str = "", cursor: str | None = None, limit: int = Query(10, ge=1, le=50), runtime=Depends(get_runtime)):
    records = dict(Corpus().documents)
    if runtime.database.available:
        with runtime.database.session() as db:
            for row in db.query(DocumentRecord).filter(DocumentRecord.document_type == "pdf").all():
                item = DocumentResponse.model_validate(row).model_dump()
                a_cnt, c_cnt, p_cnt = _count_ast_stats(row.ast_tree_json)
                if a_cnt or c_cnt or p_cnt:
                    item["articles_count"] = a_cnt
                    item["clauses_count"] = c_cnt
                    item["points_count"] = p_cnt
                records[row.id] = item
    values = sorted(records.values(), key=lambda row: row["id"])
    if domain != "all":
        values = [v for v in values if v.get("domain") == domain]
    if document_type != "all":
        values = [v for v in values if v.get("document_type") == document_type]
    if search:
        from labor_rag.ingest.chunk_schema import ascii_fold
        needle = ascii_fold(search).lower()
        values = [v for v in values if needle in ascii_fold(" ".join(str(v.get(k) or "")
                  for k in ["id", "title", "document_number"])).lower()]
    total = len(values)
    decoded = decode_cursor(cursor)
    if decoded:
        values = [v for v in values if v["id"] > decoded[1]]
    page = values[:limit]
    more = len(values) > limit
    return CursorPage(items=page, total_count=total, has_more=more,
        next_cursor=encode_cursor(datetime(1970, 1, 1), page[-1]["id"]) if more else None)

class DocumentDomainUpdate(BaseModel):
    domain: Literal["lao_dong", "khac"]


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document_domain_route(document_id: str, body: DocumentDomainUpdate, runtime=Depends(get_runtime),
                                 current_user: User = Depends(get_current_user)):
    from labor_rag.services.ingestion import update_document_domain
    corpus_doc = Corpus().documents.get(document_id)
    has_db_doc = False
    if runtime.database.available:
        with runtime.database.session() as db:
            db_doc = db.get(DocumentRecord, document_id)
            if db_doc is not None:
                if db_doc.document_type != "pdf":
                    raise HTTPException(422, "Chỉ hỗ trợ đổi lĩnh vực cho văn bản PDF.")
                has_db_doc = True
    if not has_db_doc:
        if corpus_doc is None:
            raise HTTPException(404, "Không tìm thấy văn bản.")
        if corpus_doc.get("document_type") != "pdf":
            raise HTTPException(422, "Chỉ hỗ trợ đổi lĩnh vực cho văn bản PDF.")

    with runtime.operation(serialized=False):
        try:
            update_document_domain(runtime.settings, document_id, body.domain)
        except Exception as exc:
            raise HTTPException(503, f"Chưa đồng bộ được lĩnh vực lên Qdrant ({type(exc).__name__}).") from None

    if has_db_doc and runtime.database.available:
        with runtime.database.session() as db:
            db_doc = db.get(DocumentRecord, document_id)
            db_doc.domain = body.domain
            db.commit()
            db.refresh(db_doc)
            item = DocumentResponse.model_validate(db_doc).model_dump()
            a_cnt, c_cnt, p_cnt = _count_ast_stats(db_doc.ast_tree_json)
            if a_cnt or c_cnt or p_cnt:
                item["articles_count"] = a_cnt
                item["clauses_count"] = c_cnt
                item["points_count"] = p_cnt
    else:
        item = {**corpus_doc, "domain": body.domain}

    Corpus.cache_clear()
    return DocumentResponse(**item)


@router.delete("/{document_id}", response_model=DocumentRemovalResponse)
async def remove_document_route(document_id: str, request: Request, current_user: User = Depends(get_current_user)):
    """Remove a loaded PDF; the Phap dien version of the same Dieu takes its place again."""
    from labor_rag.services.removal import DocumentRemovalError
    try:
        result, state = await run_in_threadpool(request.app.state.ingestion.remove_document, document_id)
    except DocumentRemovalError as exc:
        raise HTTPException(503, str(exc)) from None
    if state == "not_found":
        raise HTTPException(404, "Không tìm thấy văn bản.")
    if state == "not_pdf":
        raise HTTPException(422, "Chỉ gỡ được văn bản nạp từ PDF; đề mục Pháp điển là dữ liệu gốc.")
    return result


@router.get("/{document_id}/ast", response_model=DocumentASTResponse)
def get_ast(document_id: str, runtime=Depends(get_runtime)):
    if runtime.database.available:
        with runtime.database.session() as db:
            doc = db.get(DocumentRecord, document_id)
            if doc and doc.ast_tree_json:
                return DocumentASTResponse(document_id=doc.id, title=doc.title, ast_tree=doc.ast_tree_json)
    tree = Corpus().tree(document_id)
    if tree is None:
        raise HTTPException(404, "Văn bản chưa có cấu trúc trong kho.")
    return DocumentASTResponse(document_id=document_id, title=tree["title"], ast_tree=tree)

@router.get("/{document_id}/graph", response_model=GraphResponse)
def get_graph(document_id: str, article_number: str | None = Query(None, max_length=40), runtime=Depends(get_runtime)):
    from labor_rag.services.neo4j import create_neo4j_driver
    with runtime.operation(serialized=False):
        config = runtime.settings
        try:
            with create_neo4j_driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
                connection_timeout=5, max_transaction_retry_time=0) as driver:
                with driver.session(database=config.NEO4J_DATABASE) as session:
                    records = session.run("""
                        MATCH (n:Entity {dataset_id:$dataset, document_id:$document})
                        WHERE $article IS NULL OR n.article_number=$article
                        WITH n LIMIT 20
                        OPTIONAL MATCH (n)-[r]-(m:Entity {dataset_id:$dataset})
                        RETURN n,m,r LIMIT 50
                    """, dataset=config.DATASET_ID, document=document_id, article=article_number)
                    nodes, relations = {}, {}
                    for record in records:
                        for key in ["n", "m"]:
                            node = record[key]
                            if node is not None:
                                identity = node.get("id") or node.element_id
                                nodes[identity] = {"labels": list(node.labels), "props": dict(node)}
                        relation = record["r"]
                        if relation is not None:
                            relations[relation.element_id] = {"type": relation.type,
                                "source": relation.start_node.get("id") or relation.start_node.element_id,
                                "target": relation.end_node.get("id") or relation.end_node.element_id}
            graph = build_graph(nodes, list(relations.values()), focus_document=document_id)
            return {"status": "connected", **graph,
                    "warnings": ["Giới hạn 50 kết quả đồ thị."] if len(relations) == 50 else []}
        except Exception as exc:
            raise HTTPException(503, "Neo4j chưa truy vấn được (" + type(exc).__name__ + ").") from None

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_document(request: Request, file: UploadFile = File(...),
    document_type: Literal["pdf", "phap_dien_html"] = Form("pdf"),
    domain: Literal["lao_dong", "khac"] = Form("lao_dong"), de_muc_id: str | None = Form(None),
    pause_for_review: bool = Form(True),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    config = request.app.state.runtime.settings
    filename = Path((file.filename or "").replace(chr(92), "/")).name
    suffix = Path(filename).suffix.lower()
    if (document_type == "pdf" and suffix != ".pdf") or (document_type == "phap_dien_html" and suffix not in {".html", ".htm"}):
        raise HTTPException(422, "Định dạng file không khớp loại tài liệu.")
    if document_type == "phap_dien_html" and domain == "khac":
        raise HTTPException(422, "Bộ Pháp điển hiện chỉ hỗ trợ lĩnh vực Lao động; với lĩnh vực khác vui lòng chọn tài liệu PDF / OCR.")
    identity = str(uuid.uuid4())
    directory = config.UPLOAD_DIR.resolve() / identity
    directory.mkdir(parents=True, exist_ok=True)
    destination = (directory / filename).resolve()
    if not destination.is_relative_to(directory):
        raise HTTPException(422, "Tên file không hợp lệ.")
    try:
        size = 0
        with destination.open("wb") as output:
            while block := await file.read(1024 * 1024):
                size += len(block)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "File vượt giới hạn tải lên.")
                output.write(block)
        if size == 0:
            raise HTTPException(422, "File rỗng.")
        task = IngestionTask(id=identity, file_name=filename, document_type=document_type,
            status="pending", progress=0, current_step="Đang chờ xử lý.")
        db.add(task)
        db.commit()
        await run_in_threadpool(request.app.state.ingestion.submit,
                                identity, destination, document_type, de_muc_id, domain, pause_for_review)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return UploadResponse(task_id=identity, message="Đã xếp hàng nạp tài liệu.")

def _task_response(ingestion_svc, task: IngestionTask) -> IngestionTaskResponse:
    payload = IngestionTaskResponse.model_validate(task)
    preview = ingestion_svc.get_ocr_preview(task.id)
    summary = (task.result or {}).get("ocr_summary") if isinstance(task.result, dict) else None
    if preview is not None:
        if summary:
            if preview.get("heuristic_score") is None:
                preview["heuristic_score"] = summary.get("heuristic_score")
            if preview.get("articles_count") is None:
                preview["articles_count"] = summary.get("articles_count")
            if not preview.get("warnings") and summary.get("warnings"):
                preview["warnings"] = list(summary.get("warnings") or [])
        payload.ocr_preview = OCRPreviewSummary.model_validate(preview)
    elif summary:
        payload.ocr_preview = OCRPreviewSummary(
            total_pages=summary.get("total_pages", 0),
            processed_pages=summary.get("total_pages", 0),
            text_pages=summary.get("text_pages", 0),
            ocr_pages=summary.get("ocr_pages", 0),
            empty_pages=summary.get("empty_pages", 0),
            avg_confidence=summary.get("avg_confidence"),
            heuristic_score=summary.get("heuristic_score"),
            articles_count=summary.get("articles_count"),
            warnings=list(summary.get("warnings") or []),
            recent_pages=[],
        )
    return payload

@router.get("/tasks/{task_id}/progress", response_model=IngestionTaskResponse)
def task_progress(task_id: str, request: Request, db: Session = Depends(get_db)):
    task = db.get(IngestionTask, task_id)
    if task is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    return _task_response(request.app.state.ingestion, task)

@router.get("/tasks", response_model=CursorPage[IngestionTaskSummary])
def list_tasks(request: Request, state: str | None = Query(None, max_length=30),
               document_id: str | None = Query(None, max_length=100),
               cursor: str | None = None, limit: int = Query(20, ge=1, le=100)):
    """Every upload, newest first, with what became of it (running, awaiting review, indexed, removed...)."""
    decoded = decode_cursor(cursor)
    rows, total, more = request.app.state.ingestion.list_tasks(
        state=state, document_id=document_id, cursor=decoded, limit=limit)
    return CursorPage(items=rows, total_count=total, has_more=more,
                      next_cursor=encode_cursor(rows[-1]["created_at"], rows[-1]["id"]) if more and rows else None)

@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, request: Request, current_user: User = Depends(get_current_user)):
    """Delete an upload, its OCR text and revisions; the indexed document must be removed first."""
    state = request.app.state.ingestion.delete_task(task_id)
    if state == "not_found":
        raise HTTPException(404, "Tác vụ không tồn tại.")
    if state == "busy":
        raise HTTPException(409, "Lượt nạp đang chạy; hủy hoặc chờ xong rồi xóa.")
    if state == "in_corpus":
        raise HTTPException(409, "Văn bản của lượt nạp này vẫn đang trong kho; gỡ văn bản khỏi kho trước khi xóa lượt nạp.")
    return Response(status_code=204)

@router.get("/tasks/{task_id}/revisions", response_model=list[OcrRevisionResponse])
def task_revisions(task_id: str, request: Request):
    revisions = request.app.state.ingestion.list_revisions(task_id)
    if revisions is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    return revisions

@router.post("/tasks/{task_id}/revisions", response_model=IngestionTaskResponse)
def reopen_task(task_id: str, request: Request, body: ReopenRequest | None = None,
                current_user: User = Depends(get_current_user)):
    """A new draft to correct an indexed (or removed) document; the corpus changes only on confirm."""
    task, state = request.app.state.ingestion.reopen(task_id, body.from_revision_id if body else None)
    if state == "not_found":
        raise HTTPException(404, "Tác vụ không tồn tại.")
    if state == "not_pdf":
        raise HTTPException(422, "Chỉ mở lại được lượt nạp PDF.")
    if state == "busy":
        raise HTTPException(409, "Lượt nạp đang chạy; chờ xong rồi mở lại.")
    if state == "draft_exists":
        raise HTTPException(409, "Lượt nạp đã có một bản nháp đang sửa.")
    if state == "no_revision":
        raise HTTPException(404, "Không tìm thấy bản rà soát để sao chép.")
    return _task_response(request.app.state.ingestion, task)

@router.get("/tasks/{task_id}/ocr-page/{page_number}", response_model=OCRPageDetail)
def task_ocr_page(task_id: str, page_number: int, request: Request, revision: str | None = Query(None, max_length=36),
                  db: Session = Depends(get_db)):
    if db.get(IngestionTask, task_id) is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    page = request.app.state.ingestion.get_ocr_page_text(task_id, page_number, revision)
    if page is None:
        raise HTTPException(404, "Chưa có nội dung OCR cho trang này.")
    return OCRPageDetail.model_validate(page)

@router.put("/tasks/{task_id}/ocr-page/{page_number}", response_model=OCRPageDetail)
def update_task_ocr_page(task_id: str, page_number: int, body: OCRPageUpdateRequest, request: Request,
                         revision: str | None = Query(None, max_length=36),
                         current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(IngestionTask, task_id)
    if task is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    if task.status != "awaiting_review":
        raise HTTPException(409, "Chỉ có thể chỉnh sửa nội dung sau khi OCR hoàn tất và đang chờ kiểm tra.")
    from src.backend.app.services.ocr_revisions import RevisionLocked
    try:
        updated = request.app.state.ingestion.update_ocr_page_text(task_id, page_number, body.text, revision)
    except RevisionLocked:
        raise HTTPException(409, "Bản này chỉ đọc: chỉ sửa được bản nháp. Bấm 'Mở để sửa' để tạo bản nháp mới.") from None
    if updated is None:
        raise HTTPException(404, "Không tìm thấy trang OCR để cập nhật.")
    return OCRPageDetail.model_validate(updated)

@router.get("/tasks/{task_id}/pdf-page/{page_number}")
def task_pdf_page_image(task_id: str, page_number: int, request: Request, db: Session = Depends(get_db)):
    if db.get(IngestionTask, task_id) is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    png_bytes = request.app.state.ingestion.get_pdf_page_image(task_id, page_number)
    if png_bytes is None:
        raise HTTPException(404, "Không tìm thấy trang PDF yêu cầu.")
    return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})

@router.get("/tasks/{task_id}/changes", response_model=TaskChangesResponse)
async def task_changes(task_id: str, request: Request):
    """Per-Dieu comparison of the reviewed PDF with the indexed corpus, before confirming."""
    from labor_rag.services.ingestion import IngestionInputError
    try:
        changes, state = await run_in_threadpool(request.app.state.ingestion.preview_changes, task_id)
    except IngestionInputError as exc:
        raise HTTPException(422, str(exc))
    if state == "not_found":
        raise HTTPException(404, "Tác vụ không tồn tại.")
    if state == "invalid_state":
        raise HTTPException(409, "Chỉ so sánh được khi tác vụ đang chờ kiểm tra OCR.")
    if state == "missing_file":
        raise HTTPException(404, "Không tìm thấy file PDF gốc của tác vụ.")
    return changes

@router.post("/tasks/{task_id}/confirm", response_model=IngestionTaskResponse)
def confirm_task_review(task_id: str, request: Request, body: ConfirmRequest | None = None,
                        current_user: User = Depends(get_current_user)):
    """Index the draft; on a corrected review, body.prune lists the missing Dieu to delete."""
    task, state = request.app.state.ingestion.confirm_review(task_id, body.prune if body else None)
    if state == "not_found":
        raise HTTPException(404, "Tác vụ không tồn tại.")
    if state == "invalid_state":
        raise HTTPException(409, "Tác vụ không ở trạng thái chờ kiểm tra OCR.")
    if state == "missing_file":
        raise HTTPException(404, "Không tìm thấy file PDF gốc để tiếp tục lập chỉ mục.")
    return _task_response(request.app.state.ingestion, task)

@router.post("/tasks/{task_id}/cancel", response_model=IngestionTaskResponse)
def cancel_task(task_id: str, request: Request, current_user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    task = request.app.state.ingestion.cancel(task_id)
    if task is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    return _task_response(request.app.state.ingestion, task)

@router.get("/tasks/{task_id}/stream")
async def task_stream(task_id: str, request: Request, db: Session = Depends(get_db)):
    if db.get(IngestionTask, task_id) is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    async def events():
        while not await request.is_disconnected():
            with request.app.state.database.session() as session:
                task = session.get(IngestionTask, task_id)
                payload = _task_response(request.app.state.ingestion, task)
                yield "data: " + payload.model_dump_json() + "\n\n"
                if task.status in {"completed", "failed", "cancelled", "awaiting_review"}:
                    break
            await asyncio.sleep(1)
    return StreamingResponse(events(), media_type="text/event-stream")
