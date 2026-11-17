"""Intent evaluation and direct non-legal conversation handling."""
from __future__ import annotations

import re
from labor_rag.generation.llm_client import complete

SYSTEM_CLASSIFY = (
    "Bạn là chuyên gia phân loại ý định trong hệ thống Trợ lý Pháp luật Việt Nam.\n"
    "Nhiệm vụ: Xác định câu hỏi/yêu cầu của người dùng có thuộc phạm vi PHÁP LUẬT (cần tra cứu văn bản quy phạm pháp luật, luật lao động, quyền/nghĩa vụ, hợp đồng, tiền lương, kỷ luật, chế độ bảo hiểm, tranh chấp, quy định pháp lý...) hay là GIAO TIẾP THÔNG THƯỜNG / NGOÀI PHẠM VI PHÁP LUẬT (chào hỏi, cảm ơn, tạm biệt, hỏi thăm, tán gẫu, hỏi về đời sống, thời tiết, lập trình, toán học, câu hỏi ngoài lề...).\n\n"
    "Quy tắc phân loại:\n"
    "- LEGAL: Câu hỏi/yêu cầu liên quan đến pháp luật hoặc tình huống cần căn cứ pháp luật để giải đáp.\n"
    "- GENERAL: Câu chào hỏi, cảm ơn, xã giao hoặc chủ đề ngoài phạm vi pháp luật, phù hợp để trả lời trực tiếp mà không cần tra cứu điều luật.\n\n"
    "Chỉ trả lời đúng duy nhất một từ: LEGAL hoặc GENERAL."
)

SYSTEM_DIRECT = (
    "Bạn là Trợ lý AI Pháp luật Việt Nam (chuyên sâu về Bộ luật Lao động và các văn bản quy phạm pháp luật liên quan).\n"
    "Người dùng đang gửi câu chào hỏi, cảm ơn, xã giao hoặc câu hỏi ngoài phạm vi pháp luật.\n"
    "Hãy phản hồi một cách lịch sự, thân thiện, tự nhiên và súc tích bằng tiếng Việt; đồng thời khéo léo thể hiện rằng bạn là trợ lý chuyên sâu về pháp luật Việt Nam, luôn sẵn sàng giải đáp và tra cứu các quy định pháp luật khi người dùng cần."
)

GREETING_REGEX = re.compile(
    r"^(xin chào|chào bạn|chào|chào bot|chào trợ lý|chào em|chào anh|chào chị|"
    r"hello|hi|hey|alo|alô|"
    r"cảm ơn|cảm ơn bạn|cảm ơn trợ lý|thanks|thank you|"
    r"tạm biệt|bye|goodbye|"
    r"bạn là ai|bạn tên gì|bạn có thể làm gì|giới thiệu bản thân)"
    r"(\s+(bạn|nhé|nha|ạ|nhiều|ơi|nhiều nhé|nhiều nha|nha bạn))*[!?.~ ]*$",
    re.IGNORECASE
)


def is_legal_query(question: str, history: list[dict] | None = None) -> bool:
    """Evaluate whether the user question requires legal retrieval or can be answered directly."""
    clean_q = question.strip()
    if not clean_q:
        return False

    # Fast match for pure greetings and social chitchat without spending LLM tokens/latency
    if GREETING_REGEX.match(clean_q):
        return False

    convo_context = ""
    if history:
        recent = history[-4:]
        convo_context = "Ngữ cảnh hội thoại trước đó:\n" + "\n".join(
            f"{m['role']}: {m['content']}" for m in recent
        ) + "\n\n"

    user_prompt = (
        f"{convo_context}"
        f"Câu hỏi của người dùng: \"{clean_q}\"\n\n"
        "Phân loại (chỉ trả lời 'LEGAL' hoặc 'GENERAL'):"
    )

    try:
        decision = complete(SYSTEM_CLASSIFY, user_prompt, max_tokens=10).strip().upper()
        if "GENERAL" in decision and "LEGAL" not in decision:
            return False
        return True
    except Exception:
        # Fall back to standard legal pipeline on LLM failure or in unit tests
        return True


def generate_direct_answer(question: str, history: list[dict] | None = None) -> str:
    """Generate a direct conversational response without retrieving legal documents."""
    convo_context = ""
    if history:
        recent = history[-4:]
        convo_context = "\n".join(f"{m['role']}: {m['content']}" for m in recent) + "\n"

    user_prompt = f"{convo_context}user: {question}\nassistant:"
    try:
        return complete(SYSTEM_DIRECT, user_prompt, max_tokens=600).strip()
    except Exception:
        # Fallback friendly response if LLM completion is unavailable
        clean_q = question.strip().lower()
        if any(w in clean_q for w in ["chào", "hello", "hi", "hey"]):
            return "Xin chào bạn! Tôi là Trợ lý AI Pháp luật Việt Nam. Tôi luôn sẵn sàng hỗ trợ giải đáp các quy định pháp luật lao động, hợp đồng và chính sách liên quan. Bạn cần hỗ trợ thông tin gì ạ?"
        if any(w in clean_q for w in ["cảm ơn", "thanks"]):
            return "Rất vui được hỗ trợ bạn! Nếu có thêm bất kỳ thắc mắc pháp lý nào, bạn cứ tự nhiên đặt câu hỏi nhé."
        return "Xin chào! Tôi là Trợ lý AI chuyên tư vấn pháp luật Việt Nam. Tôi có thể giúp gì cho bạn về các quy định pháp luật, hợp đồng hoặc chế độ lao động hôm nay?"
