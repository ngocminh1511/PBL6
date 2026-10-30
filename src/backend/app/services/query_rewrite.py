from typing import List, Dict, Tuple, Optional
from src.backend.app.models.schemas import StepQueryRewriteTrace
from src.backend.app.repositories.redis import redis_repo

class QueryRewriteService:
    def rewrite(
        self, session_id: Optional[str], history: List[Dict[str, str]], current_question: str
    ) -> Tuple[str, StepQueryRewriteTrace]:
        """Rewrites conversational turn into standalone query using LexRAG idea."""
        # Try retrieving context from Redis if history not passed directly
        if not history and session_id:
            cached_history = redis_repo.get_session_context(session_id)
            if cached_history:
                history = cached_history

        if not history:
            trace = StepQueryRewriteTrace(
                activated=False,
                original_query=current_question,
                standalone_query=current_question,
                pronoun_resolved="Không có lịch sử trước đó (Lượt đầu tiên)"
            )
            return current_question, trace

        try:
            from labor_rag.retrieval.query_rewrite import rewrite_query
            standalone = rewrite_query(history, current_question)
        except Exception as e:
            print(f"[QueryRewriteService] LLM rewrite failed: {e}")
            standalone = current_question

        # Extract pronoun clues if possible
        pronoun_clue = None
        for p in ["trường hợp đó", "trường hợp này", "quy định đó", "họ", "anh ấy", "cô ấy", "vậy"]:
            if p in current_question.lower():
                pronoun_clue = f"Phát hiện cụm đại từ: '{p}' -> Quy chiếu vào ngữ cảnh phiên hỏi đáp."
                break

        trace = StepQueryRewriteTrace(
            activated=True,
            original_query=current_question,
            standalone_query=standalone,
            pronoun_resolved=pronoun_clue or "Tự động chuẩn hóa câu hỏi độc lập."
        )
        return standalone, trace

query_rewrite_service = QueryRewriteService()

