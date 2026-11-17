"""Session persistence around the shared RAG pipeline."""
from fastapi import HTTPException
from labor_rag.services.chat import PipelineError, evidence_dict
from src.backend.app.models.schemas import ChatAskResponse, ChatMessageResponse
from src.backend.app.repositories.postgres import ChatRepository


def answer_question(req, user, db, runtime):
    with runtime.operation():
        repo = ChatRepository(db)
        if req.session_id:
            session = repo.get_session(req.session_id, user_id=user.id)
            if session is None:
                raise HTTPException(404, "Phiên hỏi đáp không tồn tại.")
        else:
            session = repo.create_session(user.id, req.question[:60], req.domain,
                req.retrieval_mode.value if req.retrieval_mode else "hybrid")
        history = [{"role": m.role, "content": m.content} for m in repo.get_messages(session.id)[-20:]]
        try:
            result = runtime.chat().ask(req.question, history=history, top_k=req.top_k,
                rerank_top_n=req.rerank_top_n,
                mode=req.retrieval_mode.value if req.retrieval_mode else session.retrieval_mode)
        except PipelineError as exc:
            raise HTTPException(503, f"Bước {exc.stage} chưa hoàn tất ({exc.error_type}).") from None
        except Exception as exc:
            raise HTTPException(503, f"Hỏi đáp chưa hoàn tất ({type(exc).__name__}).") from None
        result["pipeline_trace"]["config_version"] = runtime.version
        user_msg = repo.add_message(session.id, "user", req.question)
        assistant = repo.add_message(session.id, "assistant", result["answer"],
            standalone_query=result["standalone_query"], pipeline_trace=result["pipeline_trace"],
            legal_evidence=[evidence_dict(e, runtime.catalog) for e in result["evidence"]],
            citation_check=result["citation_check"], execution_time_ms=result["execution_time_ms"],
            attachments=result["attachments"], warnings=result["warnings"])
        return ChatAskResponse(session_id=session.id,
            user_message=ChatMessageResponse.model_validate(user_msg),
            assistant_message=ChatMessageResponse.model_validate(assistant))
