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

from labor_rag.settings import Settings
from labor_rag.retrieval.hybrid_retrieve import HybridRetriever
from labor_rag.appendices.runtime import AppendixCatalog
from labor_rag.services.chat import ChatPipeline


class LaborLawChat:
    def __init__(self, retriever=None, *, settings=None):
        self.settings = settings or Settings()
        self.retriever = retriever or HybridRetriever(settings=self.settings)
        self.pipeline = ChatPipeline(self.retriever, AppendixCatalog(), self.settings)
        self.history = []

    def close(self):
        self.retriever.close()

    def ask(self, question, top_k=8, rerank_top_n=5):
        result = self.pipeline.ask(question, history=self.history, top_k=top_k,
                                   rerank_top_n=rerank_top_n)
        self.history.extend([{"role": "user", "content": question},
                             {"role": "assistant", "content": result["answer"]}])
        self.history = self.history[-20:]
        return result


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
