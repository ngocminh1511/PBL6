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
from src.backend.app.repositories.redis import redis_repo
from src.backend.app.services.query_rewrite import query_rewrite_service
from src.backend.app.services.retrieval import retrieval_service
from src.backend.app.services.rerank import rerank_service
from src.backend.app.services.llm import llm_service
from src.backend.app.services.verification import verification_service

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
def ask_legal_question(
    req: ChatAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    start_time = time.time()
    repo = ChatRepository(db)

    # 1. Get or create session
    session_id = req.session_id
    if not session_id:
        title_snippet = req.question[:45] + "..." if len(req.question) > 45 else req.question
        new_session = repo.create_session(
            user_id=current_user.id,
            title=title_snippet,
            domain=req.domain or "all",
            retrieval_mode=req.retrieval_mode.value if req.retrieval_mode else "hybrid"
        )
        session_id = new_session.id
    else:
        session = repo.get_session(session_id, user_id=current_user.id)
        if not session:
            new_session = repo.create_session(
                user_id=current_user.id,
                title=req.question[:45],
                domain=req.domain or "all"
            )
            session_id = new_session.id

    # 2. Record user query
    user_msg = repo.add_message(session_id=session_id, role="user", content=req.question)

    # 3. Fetch prior history for conversational LexRAG rewrite
    past_messages = repo.get_messages(session_id)[:-1]  # exclude just-added
    history_turns = [{"role": m.role, "content": m.content} for m in past_messages[-6:]]

    # Step 1: Query Rewrite
    standalone_query, trace_step1 = query_rewrite_service.rewrite(
        session_id=session_id,
        history=history_turns,
        current_question=req.question
    )

    # Step 2: Hybrid Retrieval
    evidences, trace_step2 = retrieval_service.retrieve(
        query=standalone_query,
        mode=req.retrieval_mode,
        top_k=req.top_k or 8
    )

    # Step 3: Rerank & Pruning
    retained_evidences, trace_step3 = rerank_service.rerank(
        query=standalone_query,
        evidences=evidences,
        top_n=req.rerank_top_n or 5
    )

    # Step 4: Answer Generation
    answer_text = llm_service.generate_legal_answer(
        query=standalone_query,
        evidences=retained_evidences
    )

    # Step 5: Citation Verification
    citation_check, trace_step4 = verification_service.verify(
        answer=answer_text,
        evidences=retained_evidences
    )

    # Execution time
    exec_time_ms = int((time.time() - start_time) * 1000)

    # Build Explainable Pipeline Trace
    pipeline_trace = PipelineTrace(
        trace_id=f"TR-{uuid.uuid4().hex[:6].upper()}",
        execution_time_ms=exec_time_ms,
        step1_query_rewrite=trace_step1,
        step2_hybrid_retrieval=trace_step2,
        step3_rerank=trace_step3,
        step4_verification=trace_step4
    )

    # 4. Save Assistant Message with full explainability metadata
    asst_msg = repo.add_message(
        session_id=session_id,
        role="assistant",
        content=answer_text,
        standalone_query=standalone_query,
        pipeline_trace=pipeline_trace.model_dump(),
        legal_evidence=[e.model_dump() for e in retained_evidences],
        citation_check=citation_check.model_dump(),
        execution_time_ms=exec_time_ms
    )

    # Update cache
    all_turns = history_turns + [
        {"role": "user", "content": req.question},
        {"role": "assistant", "content": answer_text}
    ]
    redis_repo.set_session_context(session_id, all_turns)

    return ChatAskResponse(
        session_id=session_id,
        user_message=ChatMessageResponse.model_validate(user_msg),
        assistant_message=ChatMessageResponse.model_validate(asst_msg)
    )

