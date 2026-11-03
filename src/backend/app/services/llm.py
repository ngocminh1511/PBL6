from typing import List
from src.backend.app.models.schemas import EvidenceItem

class LLMService:
    def generate_legal_answer(self, query: str, evidences: List[EvidenceItem]) -> str:
        try:
            from labor_rag.retrieval.hybrid_retrieve import Evidence
            from labor_rag.generation.answer import generate_answer

            raw_evidences = []
            for e in evidences:
                amendments = [
                    Evidence(
                        chunk_id=a.chunk_id,
                        mapc=None,
                        ten="",
                        text=a.text,
                        source="amendment",
                        change=a.change
                    )
                    for a in e.amendments
                ]
                ev = Evidence(
                    chunk_id=e.chunk_id,
                    mapc=e.mapc,
                    ten=e.ten,
                    text=e.text,
                    source=e.source,
                    document_id=e.document_id,
                    meta_dieu=e.meta_dieu,
                    meta_khoan=e.meta_khoan,
                    meta_de_muc=e.meta_de_muc,
                    amendments=amendments
                )
                raw_evidences.append(ev)

            return generate_answer(query, raw_evidences)
        except Exception as exc:
            print(f"[LLMService] Generation error: {exc}")
            # Fallback informative message if API keys are not yet configured
            summary_points = "\n".join([f"- **{e.citation}** ({e.ten}): {e.text[:200]}..." for e in evidences[:3]])
            return (
                f"Căn cứ vào hệ thống quy định pháp luật lao động hiện hành:\n\n"
                f"{summary_points}\n\n"
                f"*(Lưu ý: Vui lòng cấu hình GEMINI_API_KEY / OPENAI_API_KEY trong Quản trị hệ thống để tạo câu trả lời tổng hợp chi tiết từ LLM.)*"
            )

llm_service = LLMService()

