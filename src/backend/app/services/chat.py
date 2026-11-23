"""Session persistence around the shared RAG pipeline."""
import logging

from fastapi import HTTPException
from labor_rag.services.chat import PipelineError, evidence_dict
from labor_rag.generation.usage import collect_usage, usage_stage
from src.backend.app.models.schemas import ChatAskResponse, ChatMessageResponse
from src.backend.app.repositories.postgres import ChatRepository
from src.backend.app.services.configuration import failure_message


logger = logging.getLogger(__name__)


class ChatRequestError(HTTPException):
    def __init__(self, detail, token_usage):
        super().__init__(503, detail)
        self.token_usage = token_usage


VIETNAMESE_LETTERS = set("ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ")
TITLE_LIMIT = 60


def is_vietnamese(text: str) -> bool:
    return any(char in VIETNAMESE_LETTERS for char in text.lower())


def question_title(question: str, limit: int = TITLE_LIMIT) -> str:
    """The question itself, cut at a word boundary: the fallback session title."""
    text = " ".join(question.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return cut.rstrip(" ,.;:?!") + "…"


def usable_title(title: str, question: str) -> bool:
    """Reject titles in another language than a Vietnamese question, or of no use as a name."""
    words = title.split()
    if not 1 <= len(words) <= 12 or len(title) > TITLE_LIMIT:
        return False
    return is_vietnamese(title) or not is_vietnamese(question)


def generate_session_title(runtime, question: str) -> str:
    """Generate a concise 3-6 word session title based on the first user question."""
    prompt = (
        "Hãy đặt một tiêu đề ngắn gọn (khoảng 3 đến 6 từ, chuẩn tiếng Việt có dấu) tóm tắt nội dung câu hỏi sau đây "
        "để làm tên phiên hội thoại pháp luật. "
        "Ví dụ: 'Quyền đơn phương chấm dứt HĐLĐ', 'Thời hạn báo trước nghỉ việc', 'Chế độ thai sản năm 2024'.\n"
        "Chỉ trả về đúng tiêu đề ngắn, không dùng dấu ngoặc kép, không thêm lời dẫn.\n\n"
        f"Câu hỏi: {question}"
    )
    try:
        with usage_stage("session_title"):
            pipeline = runtime.chat()
            title = pipeline.llm.complete("Bạn là trợ lý pháp luật chuyên đặt tên phiên tra cứu ngắn gọn.", prompt, max_tokens=30, reasoning="off").strip()
        title = title.strip('"\':\n\r').split('\n')[0].strip().strip('"\'.')
        if usable_title(title, question):
            return title
    except Exception:
        pass
    return question_title(question)


def answer_question(req, user, db, runtime):
    with runtime.operation(), collect_usage() as usage:
        repo = ChatRepository(db)
        if req.session_id:
            session = repo.get_session(req.session_id, user_id=user.id)
            if session is None:
                raise HTTPException(404, "Phiên hỏi đáp không tồn tại.")
        else:
            short_title = generate_session_title(runtime, req.question)
            session = repo.create_session(user.id, short_title, req.domain,
                req.retrieval_mode.value if req.retrieval_mode else "hybrid")
        history_messages = repo.get_messages(session.id)
        if not history_messages and session.title in {"Phiên tra cứu mới", "Phiên hỏi đáp mới", "Phiên mới"}:
            short_title = generate_session_title(runtime, req.question)
            repo.update_session(session.id, user_id=user.id, title=short_title)
        history = [{"role": m.role, "content": m.content} for m in history_messages[-20:]]
        try:
            result = runtime.chat().ask(req.question, history=history, top_k=req.top_k,
                rerank_top_n=req.rerank_top_n,
                mode=req.retrieval_mode.value if req.retrieval_mode else session.retrieval_mode)
        except PipelineError as exc:
            code, message = failure_message(exc.cause)
            logger.warning("Chat stage %s failed (%s, %s)", exc.stage, exc.error_type, code)
            raise ChatRequestError(f"Bước {exc.stage} chưa hoàn tất: {message} ({exc.error_type}).", usage.snapshot()) from None
        except Exception as exc:
            code, message = failure_message(exc)
            logger.warning("Chat initialization failed (%s, %s)", type(exc).__name__, code)
            raise ChatRequestError(f"Hỏi đáp chưa hoàn tất: {message} ({type(exc).__name__}).", usage.snapshot()) from None
        if result.get("pipeline_trace"):
            result["pipeline_trace"]["config_version"] = runtime.version
        user_msg = repo.add_message(session.id, "user", req.question)
        assistant = repo.add_message(session.id, "assistant", result["answer"],
            standalone_query=result["standalone_query"], pipeline_trace=result["pipeline_trace"],
            legal_evidence=[evidence_dict(e, runtime.catalog) for e in result["evidence"]],
            citation_check=result["citation_check"], execution_time_ms=result["execution_time_ms"],
            attachments=result["attachments"], warnings=result["warnings"], token_usage=usage.snapshot())
        return ChatAskResponse(session_id=session.id,
            user_message=ChatMessageResponse.model_validate(user_msg),
            assistant_message=ChatMessageResponse.model_validate(assistant))
