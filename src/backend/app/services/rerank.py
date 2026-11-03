from typing import List, Tuple
from src.backend.app.models.schemas import EvidenceItem, StepRerankTrace

class RerankService:
    def rerank(
        self, query: str, evidences: List[EvidenceItem], top_n: int = 5
    ) -> Tuple[List[EvidenceItem], StepRerankTrace]:
        if len(evidences) <= top_n:
            trace = StepRerankTrace(
                retained_count=len(evidences),
                pruned_count=0,
                pruned_citations=[]
            )
            return evidences, trace

        try:
            # We convert EvidenceItem to Evidence dataclass for labor_rag.retrieval.rerank
            from labor_rag.retrieval.hybrid_retrieve import Evidence
            from labor_rag.retrieval.rerank import rerank as labor_rerank

            raw_evidences = [
                Evidence(
                    chunk_id=e.chunk_id,
                    mapc=e.mapc,
                    ten=e.ten,
                    text=e.text,
                    source=e.source,
                    score=e.score,
                    document_id=e.document_id,
                    meta_dieu=e.meta_dieu,
                    meta_khoan=e.meta_khoan,
                    meta_de_muc=e.meta_de_muc
                )
                for e in evidences
            ]
            picked = labor_rerank(query, raw_evidences, top_n=top_n)
            picked_chunk_ids = {p.chunk_id for p in picked}
            
            retained = [e for e in evidences if e.chunk_id in picked_chunk_ids][:top_n]
            pruned = [e.citation for e in evidences if e.chunk_id not in picked_chunk_ids]
        except Exception as exc:
            print(f"[RerankService] Reranking exception: {exc}, using top_n slice.")
            retained = evidences[:top_n]
            pruned = [e.citation for e in evidences[top_n:]]

        trace = StepRerankTrace(
            retained_count=len(retained),
            pruned_count=len(pruned),
            pruned_citations=pruned[:4]
        )
        return retained, trace

rerank_service = RerankService()

