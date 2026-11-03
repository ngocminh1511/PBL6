"""End-to-end orchestrator: Conversation Context -> Query Rewrite ->
Hybrid Retrieval -> Rerank/Prune -> LLM Answer -> Citation Verification ->
Final Legal Answer + Dieu/Khoan/Diem Citation.

Usage:
  python -m labor_rag.app.chat      # interactive REPL, from the repository root
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.generation.answer import generate_answer
from labor_rag.generation.citation_verify import verify_citations
from labor_rag.retrieval.hybrid_retrieve import HybridRetriever
from labor_rag.retrieval.query_rewrite import rewrite_query
from labor_rag.retrieval.rerank import rerank


class LaborLawChat:
    def __init__(self, retriever=None) -> None:
        self.retriever = retriever or HybridRetriever()
        from labor_rag.appendices.runtime import AppendixCatalog
        self.appendices = AppendixCatalog()
        self.history: list[dict] = []

    def close(self) -> None:
        self.retriever.close()

    def ask(self, question: str, top_k: int = 8, rerank_top_n: int = 5) -> dict:
        standalone_query = rewrite_query(self.history, question)
        evidences = self.retriever.retrieve(standalone_query, top_k=top_k)
        pruned = rerank(standalone_query, evidences, top_n=rerank_top_n)
        pruned = self.appendices.augment(standalone_query, pruned, limit=6)
        answer = generate_answer(standalone_query, pruned, context_notes=self.appendices.last_warnings)
        citation_check = verify_citations(answer, pruned)

        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})

        return {
            "standalone_query": standalone_query,
            "evidence": pruned,
            "answer": answer,
            "citation_check": citation_check,
            "attachments": self.appendices.last_attachments,
            "warnings": self.appendices.last_warnings + ([self.retriever.graph_warning] if getattr(self.retriever, "graph_warning", None) else []),
        }


def main() -> None:
    chat = LaborLawChat()
    print("Chatbot Bộ luật Lao động (gõ 'exit' để thoát)\n")
    try:
        while True:
            question = input("Bạn: ").strip()
            if question.lower() in ("exit", "quit"):
                break
            if not question:
                continue
            result = chat.ask(question)
            print(f"\n[Standalone query] {result['standalone_query']}")
            print(f"\nTrợ lý: {result['answer']}\n")
            check = result["citation_check"]
            if check["unverified"]:
                print(f"⚠ Trích dẫn CHƯA xác minh được trong evidence: {check['unverified']}")
            print()
    finally:
        chat.close()


if __name__ == "__main__":
    main()
