import time
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from src.backend.app.dependencies import get_current_user, get_db
from src.backend.app.models.database import User, ChatSession, ChatMessage
from src.backend.app.models.schemas import (
    ChatSessionCreate, ChatSessionResponse, ChatMessageResponse,
    SessionDetailResponse, ChatAskRequest, ChatAskResponse,
    CursorPage, PipelineTrace
)
from src.backend.app.repositories.postgres import ChatRepository
from fastapi import Request
from src.backend.app.services.chat import answer_question

router = APIRouter(prefix="/chat", tags=["Legal Chat"])

@router.get("/sessions", response_model=CursorPage[ChatSessionResponse])
def list_sessions(
    cursor: Optional[str] = Query(None),
    limit: int = Query(15, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    repo = ChatRepository(db)
    items, next_cursor, has_more, total = repo.list_sessions_cursor(current_user.id, cursor=cursor, limit=limit)

    session_responses = []
    for s in items:
        resp = ChatSessionResponse.model_validate(s)
        resp.message_count = len(s.messages)
        if s.messages:
            resp.last_message_preview = s.messages[-1].content[:60] + "..."
        session_responses.append(resp)

    return CursorPage[ChatSessionResponse](
        items=session_responses,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total
    )

@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(
    req: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    repo = ChatRepository(db)
    session = repo.create_session(
        user_id=current_user.id,
        title=req.title or "Phiên tra cứu mới",
        domain=req.domain or "all",
        retrieval_mode=req.retrieval_mode.value if req.retrieval_mode else "hybrid"
    )
    return ChatSessionResponse.model_validate(session)

@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    repo = ChatRepository(db)
    session = repo.get_session(session_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Phiên hỏi đáp không tồn tại")

    messages = repo.get_messages(session_id)
    return SessionDetailResponse(
        session=ChatSessionResponse.model_validate(session),
        messages=[ChatMessageResponse.model_validate(m) for m in messages]
    )

@router.post("/ask", response_model=ChatAskResponse)
def ask_legal_question(req: ChatAskRequest, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return answer_question(req, current_user, db, request.app.state.runtime)


legacy_router = APIRouter(tags=["Compatibility"])

@legacy_router.post("/chat")
def legacy_chat(req: ChatAskRequest, request: Request,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = answer_question(req, current_user, db, request.app.state.runtime)
    message = result.assistant_message
    return {"session_id": result.session_id, "answer": message.content,
            "standalone_query": message.standalone_query,
            "evidence": [e.model_dump() for e in message.legal_evidence or []],
            "citation_check": message.citation_check,
            "attachments": message.attachments, "warnings": message.warnings}
