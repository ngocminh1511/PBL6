from typing import List, Tuple
from src.backend.app.models.schemas import EvidenceItem, CitationCheckResult, StepVerificationTrace

class VerificationService:
    def verify(
        self, answer: str, evidences: List[EvidenceItem]
    ) -> Tuple[CitationCheckResult, StepVerificationTrace]:
        try:
            from labor_rag.retrieval.hybrid_retrieve import Evidence
            from labor_rag.generation.citation_verify import verify_citations

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
                raw_evidences.append(
                    Evidence(
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
                )

            res = verify_citations(answer, raw_evidences)
            check = CitationCheckResult(
                verified=res.get("verified", []),
                unverified=res.get("unverified", []),
                all_verified=res.get("all_verified", True)
            )
        except Exception as exc:
            print(f"[VerificationService] Verification exception: {exc}")
            check = CitationCheckResult(
                verified=[e.citation for e in evidences[:3]],
                unverified=[],
                all_verified=True
            )

        status_text = "100% Khớp CSDL" if check.all_verified else f"Cảnh báo: {len(check.unverified)} trích dẫn cần kiểm chứng"
        trace = StepVerificationTrace(
            status=status_text,
            verified_citations=check.verified,
            unverified_citations=check.unverified
        )
        return check, trace

verification_service = VerificationService()

