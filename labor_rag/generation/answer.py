"""Generate the final answer from retrieved Legal Evidence, requiring the
LLM to cite Dieu/Khoan/Diem for every claim."""
from __future__ import annotations

from labor_rag.generation.llm_client import complete
from labor_rag.retrieval.hybrid_retrieve import Evidence

SYSTEM = (
    "Bạn là trợ lý tư vấn pháp luật lao động Việt Nam. "
    "Chỉ trả lời dựa trên các điều luật được cung cấp dưới đây, không dùng kiến thức "
    "ngoài phạm vi này. Với mỗi ý trả lời, PHẢI trích dẫn rõ số Điều (và Khoản/Điểm nếu "
    "có) cùng tên văn bản, đúng như phần trong ngoặc vuông. Nếu các điều luật được cung cấp "
    "không đủ để trả lời, nói rõ là chưa tìm thấy quy định liên quan trong phạm vi dữ "
    "liệu hiện có, không suy đoán. Phần \"Được sửa đổi bởi\" dưới một điều luật là quy định "
    "sửa đổi chưa có trong nội dung điều đó: ở phần bị sửa, áp dụng quy định sửa đổi thay cho "
    "nội dung gốc và trích dẫn cả văn bản sửa đổi. "
    "Với bằng chứng phụ lục, trích dẫn 'Phụ lục <số> <số hiệu văn bản>'. "
    "Bằng chứng chỉ có metadata biểu mẫu hoặc thông báo thiếu nội dung không đủ để suy ra danh mục hay nội dung mẫu. "
    "Nếu thiếu nguồn phụ lục, nói rõ giới hạn đó. Giao diện cung cấp nút tải file; không tự đặt URL tải."
)


def render(evidence: Evidence) -> str:
    # "[Điều 35 khoản 4-5 Nghị định số 145/2020/NĐ-CP] Trợ cấp thôi việc" (docs/structural_jsonl.md, section 9)
    lines = [f"[{evidence.citation}] {evidence.ten}", f"Nội dung: {evidence.text}"]
    for amendment in evidence.amendments:
        change = f" ({amendment.change})" if amendment.change else ""
        lines += [f"Được sửa đổi bởi [{amendment.citation}]{change}:", amendment.text]
    return "\n".join(lines)


def generate_answer(query: str, evidences: list[Evidence], *, context_notes: list[str] | None = None) -> str:
    context = "\n\n".join(render(e) for e in evidences)
    if context_notes:
        context += "\n\nGiới hạn nguồn dữ liệu:\n" + "\n".join(context_notes)
    user = f"Các điều luật liên quan:\n{context}\n\nCâu hỏi: {query}\n\nTrả lời:"
    return complete(SYSTEM, user, max_tokens=1500)
