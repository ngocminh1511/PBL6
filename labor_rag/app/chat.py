"""End-to-end orchestrator: Conversation Context -> Query Rewrite ->
Hybrid Retrieval -> Rerank/Prune -> LLM Answer -> Citation Verification ->
Final Legal Answer + Dieu/Khoan/Diem Citation.

Usage:
  python -m app.chat                 # interactive REPL
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")

from generation.answer import generate_answer
from generation.citation_verify import verify_citations
from retrieval.hybrid_retrieve import HybridRetriever
from retrieval.query_rewrite import rewrite_query
from retrieval.rerank import rerank


class LaborLawChat:
    def __init__(self) -> None:
        self.retriever = HybridRetriever()
        self.history: list[dict] = []

    def close(self) -> None:
        self.retriever.close()

    def ask(self, question: str, top_k: int = 8, rerank_top_n: int = 5) -> dict:
        standalone_query = rewrite_query(self.history, question)
        evidences = self.retriever.retrieve(standalone_query, top_k=top_k)
        pruned = rerank(standalone_query, evidences, top_n=rerank_top_n)
        answer = generate_answer(standalone_query, pruned)
        citation_check = verify_citations(answer, pruned)

        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})

        return {
            "standalone_query": standalone_query,
            "evidence": pruned,
            "answer": answer,
            "citation_check": citation_check,
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
