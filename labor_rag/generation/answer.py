"""Generate the final answer from retrieved Legal Evidence, requiring the
LLM to cite Dieu/Khoan/Diem for every claim."""
from __future__ import annotations

from labor_rag.generation.llm_client import complete
from labor_rag.retrieval.hybrid_retrieve import Evidence

SYSTEM = (
    "Bạn là trợ lý tư vấn pháp luật lao động Việt Nam. "
    "Chỉ trả lời dựa trên các điều luật được cung cấp dưới đây, không dùng kiến thức "
    "ngoài phạm vi này. Với mỗi ý trả lời, PHẢI trích dẫn rõ số Điều (và Khoản/Điểm nếu "
    "có) cùng tên văn bản nguồn lấy từ phần 'Nguồn'. Nếu các điều luật được cung cấp "
    "không đủ để trả lời, nói rõ là chưa tìm thấy quy định liên quan trong phạm vi dữ "
    "liệu hiện có, không suy đoán."
)


def generate_answer(query: str, evidences: list[Evidence]) -> str:
    context = "\n\n".join(
        f"[{e.mapc}] {e.ten}\nNguồn: {e.citation}\nNội dung: {e.text}" for e in evidences
    )
    user = f"Các điều luật liên quan:\n{context}\n\nCâu hỏi: {query}\n\nTrả lời:"
    return complete(SYSTEM, user, max_tokens=1500)
