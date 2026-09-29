"""Conversation-aware query rewriting: turn the latest user turn plus prior
history into one standalone query, so retrieval doesn't need conversation
state. Corresponds to the "Conversation Context -> Query Rewrite ->
Standalone Query" stage of the pipeline.
"""
from __future__ import annotations

from generation.llm_client import complete

SYSTEM = (
    "Bạn viết lại câu hỏi pháp luật lao động Việt Nam thành một câu hỏi độc lập "
    "(standalone), đầy đủ ngữ cảnh, dựa trên lịch sử hội thoại trước đó. "
    "Chỉ trả về đúng câu hỏi đã viết lại, không thêm giải thích, không thêm tiền tố."
)


def rewrite_query(history: list[dict], current_question: str) -> str:
    """history: list of {"role": "user"|"assistant", "content": str}, oldest first."""
    if not history:
        return current_question

    convo = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
    user = (
        f"Lịch sử hội thoại:\n{convo}\n\n"
        f"Câu hỏi hiện tại (có thể phụ thuộc ngữ cảnh phía trên): {current_question}\n\n"
        "Viết lại câu hỏi hiện tại thành một câu hỏi độc lập, đầy đủ ngữ cảnh:"
    )
    return complete(SYSTEM, user, max_tokens=256).strip()
