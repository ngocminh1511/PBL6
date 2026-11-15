import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from src.backend.app.dependencies import get_current_user, get_db
from src.backend.app.models.database import IngestionTask, DocumentRecord, User
from src.backend.app.models.schemas import DocumentResponse, DocumentASTResponse, IngestionTaskResponse, UploadResponse, CursorPage, GraphResponse
from src.backend.app.services.runtime import get_runtime
from src.backend.app.services.corpus import Corpus
from src.backend.app.services.graph import build_graph
from src.backend.app.utils.pagination import encode_cursor, decode_cursor

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.get("/list", response_model=CursorPage[DocumentResponse])
def list_documents(domain: Literal["all", "lao_dong"] = "all", search: str = "",
    cursor: str | None = None, limit: int = Query(10, ge=1, le=50), runtime=Depends(get_runtime)):
    records = dict(Corpus().documents)
    if runtime.database.available:
        with runtime.database.session() as db:
            records.update({row.id: DocumentResponse.model_validate(row).model_dump()
                            for row in db.query(DocumentRecord).all()})
    values = sorted(records.values(), key=lambda row: row["id"], reverse=True)
    if search:
        from labor_rag.ingest.chunk_schema import ascii_fold
        needle = ascii_fold(search).lower()
        values = [v for v in values if needle in ascii_fold(" ".join(str(v.get(k) or "")
                  for k in ["id", "title", "document_number"])).lower()]
    total = len(values)
    decoded = decode_cursor(cursor)
    if decoded:
        values = [v for v in values if v["id"] < decoded[1]]
    page = values[:limit]
    more = len(values) > limit
    return CursorPage(items=page, total_count=total, has_more=more,
        next_cursor=encode_cursor(datetime(1970, 1, 1), page[-1]["id"]) if more else None)

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
    from neo4j import GraphDatabase
    with runtime.operation(serialized=False):
        config = runtime.settings
        try:
            with GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
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
    domain: Literal["lao_dong"] = Form("lao_dong"), de_muc_id: str | None = Form(None),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    config = request.app.state.runtime.settings
    filename = Path((file.filename or "").replace(chr(92), "/")).name
    suffix = Path(filename).suffix.lower()
    if (document_type == "pdf" and suffix != ".pdf") or (document_type == "phap_dien_html" and suffix not in {".html", ".htm"}):
        raise HTTPException(422, "Định dạng file không khớp loại tài liệu.")
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
                                identity, destination, document_type, de_muc_id)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return UploadResponse(task_id=identity, message="Đã xếp hàng nạp tài liệu.")

@router.get("/tasks/{task_id}/progress", response_model=IngestionTaskResponse)
def task_progress(task_id: str, db: Session = Depends(get_db)):
    task = db.get(IngestionTask, task_id)
    if task is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    return IngestionTaskResponse.model_validate(task)

@router.get("/tasks/{task_id}/stream")
async def task_stream(task_id: str, request: Request, db: Session = Depends(get_db)):
    if db.get(IngestionTask, task_id) is None:
        raise HTTPException(404, "Tác vụ không tồn tại.")
    async def events():
        while not await request.is_disconnected():
            with request.app.state.database.session() as session:
                task = session.get(IngestionTask, task_id)
                payload = IngestionTaskResponse.model_validate(task)
                yield "data: " + payload.model_dump_json() + "\n\n"
                if task.status in {"completed", "failed"}:
                    break
            await asyncio.sleep(1)
    return StreamingResponse(events(), media_type="text/event-stream")
