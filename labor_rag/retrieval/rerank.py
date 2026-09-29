"""LLM-based rerank + prune: cut the hybrid candidate set down to the
top-N most relevant provisions before they're used as "Legal Evidence" in
the answer prompt.
"""
from __future__ import annotations

import json
import re

from generation.llm_client import complete
from retrieval.hybrid_retrieve import Evidence

SYSTEM = (
    "Bạn là chuyên gia pháp luật lao động Việt Nam. Nhiệm vụ: chọn ra các điều luật "
    "liên quan trực tiếp nhất để trả lời câu hỏi, xếp theo độ liên quan giảm dần."
)


def rerank(query: str, evidences: list[Evidence], top_n: int = 5) -> list[Evidence]:
    if len(evidences) <= top_n:
        return evidences

    listing = "\n\n".join(
        f"{i}. [{e.mapc}] {e.ten}\n{e.text[:400]}" for i, e in enumerate(evidences)
    )
    user = (
        f"Câu hỏi: {query}\n\n"
        f"Danh sách điều luật ứng viên:\n{listing}\n\n"
        f"Trả về CHỈ MỘT JSON array chứa tối đa {top_n} chỉ số (index, bắt đầu từ 0) "
        "của các điều liên quan nhất, xếp theo độ liên quan giảm dần. "
        'Ví dụ: [0, 3, 1]. Không giải thích gì thêm.'
    )
    raw = complete(SYSTEM, user, max_tokens=200)
    match = re.search(r"\[[\d,\s]*\]", raw)
    if not match:
        return evidences[:top_n]
    try:
        indices = json.loads(match.group(0))
    except json.JSONDecodeError:
        return evidences[:top_n]

    picked = [evidences[i] for i in indices if isinstance(i, int) and 0 <= i < len(evidences)]
    return picked or evidences[:top_n]
