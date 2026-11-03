import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.backend.app.config import settings
from src.backend.app.dependencies import get_current_user, get_db
from src.backend.app.models.database import User, IngestionTask, DocumentRecord
from src.backend.app.models.schemas import (
    DocumentResponse, DocumentASTResponse, IngestionTaskResponse, UploadResponse, CursorPage
)
from src.backend.app.repositories.postgres import DocumentRepository, TaskRepository
from src.backend.app.services.ingestion import ingestion_service

router = APIRouter(prefix="/documents", tags=["Legal Documents"])

@router.get("/list", response_model=CursorPage[DocumentResponse])
def list_documents(
    domain: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    repo = DocumentRepository(db)
    items, next_cursor, has_more, total = repo.list_documents_cursor(
        domain=domain, search=search, cursor=cursor, limit=limit
    )
    return CursorPage[DocumentResponse](
        items=[DocumentResponse.model_validate(d) for d in items],
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total
    )

@router.get("/{document_id}/ast", response_model=DocumentASTResponse)
def get_document_ast(document_id: str, db: Session = Depends(get_db)):
    repo = DocumentRepository(db)
    doc = repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy văn bản quy phạm")
    
    return DocumentASTResponse(
        document_id=doc.id,
        title=doc.title,
        ast_tree=doc.ast_tree_json or {}
    )

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("pdf"),
    domain: str = Form("lao_dong"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    dest_path = settings.UPLOAD_DIR / file.filename
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    task_repo = TaskRepository(db)
    doc_id = Path(file.filename).stem.lower().replace(" ", "_")
    task = IngestionTask(
        document_id=doc_id,
        file_name=file.filename,
        document_type=document_type,
        status="pending",
        progress=0.0,
        current_step="Tải lên thành công. Bắt đầu xếp hàng xử lý..."
    )
    task = task_repo.create(task)

    # Launch background processing pipeline
    ingestion_service.process_file_background(
        task_id=task.id,
        file_path=dest_path,
        document_type=document_type,
        domain=domain
    )

    return UploadResponse(
        task_id=task.id,
        document_id=doc_id,
        message="Văn bản đã được tải lên và đang tiến hành xử lý ngầm (Hierarchy Parsing & Embedding)."
    )

@router.get("/tasks/{task_id}/progress", response_model=IngestionTaskResponse)
def get_task_progress(task_id: str, db: Session = Depends(get_db)):
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Nhiệm vụ không tồn tại")
    return IngestionTaskResponse.model_validate(task)

@router.get("/tasks/{task_id}/stream")
async def stream_task_progress(task_id: str, db: Session = Depends(get_db)):
    """Server-Sent Events (SSE) progress stream for live progress bar."""
    async def event_generator():
        task_repo = TaskRepository(db)
        while True:
            db.expire_all()
            task = task_repo.get_by_id(task_id)
            if not task:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            payload = {
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "embedded_chunks": task.embedded_chunks,
                "total_chunks": task.total_chunks,
                "error_message": task.error_message
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if task.status in ["completed", "failed"]:
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

