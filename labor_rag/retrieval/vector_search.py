"""Standalone Vector Retrieval on Qdrant (Semantic search only, no Neo4j dependency).

Allows searching either TH1 (minimal header) or TH2 (full header) collections,
or comparing both side-by-side.

Usage:
  # Query TH1 (minimal header - lao_dong_v6)
  python -m labor_rag.retrieval.vector_search "Người lao động thử việc có được trả lương không?" --collection legal_ld_v6_bge

  # Query TH2 (full header - lao_dong_v5)
  python -m labor_rag.retrieval.vector_search "Người lao động thử việc có được trả lương không?" --collection legal_ld_v5_bge

  # Compare TH1 and TH2 side-by-side for the same query
  python -m labor_rag.retrieval.vector_search "Người lao động thử việc có được trả lương không?" --compare

  # Interactive REPL mode
  python -m labor_rag.retrieval.vector_search --interactive
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import Sequence

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import DatetimeRange, FieldCondition, Filter, IsNullCondition, MatchValue, PayloadField
from sentence_transformers import SentenceTransformer

from labor_rag.ingest.chunk_schema import article_id, citation, join_parts, part_number
from labor_rag.retrieval.hybrid_retrieve import Evidence, in_force

load_dotenv()

DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DEFAULT_COLLECTION_TH2 = os.getenv("QDRANT_COLLECTION", "legal_ld_v5_bge")
DEFAULT_COLLECTION_TH1 = "legal_ld_v6_bge"
OVERFETCH = 2


class VectorRetriever:
    """Pure Vector-based Retriever using Qdrant (independent of Neo4j)."""

    def __init__(
        self,
        collection: str = DEFAULT_COLLECTION_TH2,
        model_name: str = DEFAULT_MODEL,
        qdrant_url: str = DEFAULT_QDRANT_URL,
        qdrant_api_key: str | None = None,
    ) -> None:
        self.collection = collection
        self.model_name = model_name
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY") or None
        self.timeout = int(os.getenv("QDRANT_TIMEOUT", "60"))

        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key, timeout=self.timeout)

    def search(
        self,
        query: str,
        top_k: int = 5,
        collection: str | None = None,
        join_split_parts: bool = True,
    ) -> list[Evidence]:
        """Search top-k relevant provisions in Qdrant.

        Collapses split parts (:p1, :p2) into their parent article so each
        Dieu counts once, keeping the highest similarity score.
        """
        col = collection or self.collection
        vector = self.model.encode(query, normalize_embeddings=True).tolist()

        try:
            hits = self.client.query_points(
                collection_name=col,
                query=vector,
                query_filter=in_force(),
                limit=top_k * OVERFETCH,
                with_payload=True,
            ).points
        except Exception as exc:
            raise RuntimeError(f"Error querying Qdrant collection '{col}': {exc}") from exc

        best_articles: dict[str, Evidence] = {}
        for h in hits:
            if not h.payload:
                continue
            key = article_id(h.payload["chunk_id"])
            if key not in best_articles:
                best_articles[key] = Evidence.from_payload(h.payload, "vector", h.score)

        results = list(best_articles.values())[:top_k]

        if join_split_parts:
            self._hydrate_full_text(results, col)

        return results

    def _hydrate_full_text(self, evidences: list[Evidence], collection: str) -> None:
        """If an article was split into multiple parts, fetch all parts and join them."""
        for ev in evidences:
            if not ev.chunk_id:
                continue
            base_id = article_id(ev.chunk_id)
            doc_id = ev.document_id
            dieu_num = ev.meta_dieu
            if not doc_id or not dieu_num:
                continue

            points, _ = self.client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="document_id", match=MatchValue(value=doc_id)),
                        FieldCondition(key="meta_dieu", match=MatchValue(value=dieu_num)),
                        in_force(),
                    ]
                ),
                limit=32,
                with_payload=True,
            )
            if len(points) > 1:
                sorted_parts = sorted(
                    (p.payload for p in points if p.payload),
                    key=lambda p: part_number(p["chunk_id"]),
                )
                ev.text = join_parts([p["text"] for p in sorted_parts])


def print_results(results: list[Evidence], title: str = "Kết quả tìm kiếm") -> None:
    print(f"\n{'='*70}")
    print(f" {title} (Tìm thấy {len(results)} kết quả)")
    print(f"{'='*70}")
    for idx, ev in enumerate(results, start=1):
        score_pct = f"{ev.score * 100:.1f}%" if ev.score else "N/A"
        print(f"[{idx}] {ev.citation} | Độ khớp: {score_pct} (score: {ev.score:.4f})")
        print(f"    Tiêu đề: {ev.ten}")
        print(f"    Chunk ID: {ev.chunk_id} | Đề mục: {ev.meta_de_muc}")
        preview = ev.text.replace("\n", " ").strip()
        if len(preview) > 220:
            preview = preview[:220] + "..."
        print(f"    Trích đoạn: {preview}")
        print("-" * 70)


def run_comparison(retriever: VectorRetriever, query: str, top_k: int = 5) -> None:
    print(f"\n[QUERY] {query}")
    print("\n>>> Đang tìm kiếm trên TH1 (Tối giản - legal_ld_v6_bge)...")
    res_th1 = retriever.search(query, top_k=top_k, collection=DEFAULT_COLLECTION_TH1)

    print(">>> Đang tìm kiếm trên TH2 (Đầy đủ ngữ cảnh - legal_ld_v5_bge)...")
    res_th2 = retriever.search(query, top_k=top_k, collection=DEFAULT_COLLECTION_TH2)

    print_results(res_th1, title=f"TH1 (Tối giản: Điều n. Tên + nội dung) - [{DEFAULT_COLLECTION_TH1}]")
    print_results(res_th2, title=f"TH2 (Đầy đủ: Ngữ cảnh + Điều n. Tên) - [{DEFAULT_COLLECTION_TH2}]")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="?", default=None, help="Câu hỏi cần tìm kiếm quy định pháp luật")
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION_TH2,
        help=f"Tên Qdrant collection cần truy vấn (Mặc định: {DEFAULT_COLLECTION_TH2})",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Tên embedding model (Mặc định: {DEFAULT_MODEL})")
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL, help=f"URL Qdrant (Mặc định: {DEFAULT_QDRANT_URL})")
    parser.add_argument("--top-k", type=int, default=5, help="Số lượng Điều luật hàng đầu cần lấy (Mặc định: 5)")
    parser.add_argument(
        "--compare",
        action="store_true",
        help="So sánh kết quả song song giữa TH1 (v6) và TH2 (v5)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Bật chế độ hỏi đáp liên tục (interactive REPL) trên terminal",
    )
    args = parser.parse_args()

    retriever = VectorRetriever(collection=args.collection, model_name=args.model, qdrant_url=args.qdrant_url)

    if args.interactive:
        print(f"\n[INTERACTIVE MODE] Đang kết nối Qdrant tại: {args.qdrant_url}")
        print(f"Collection: {args.collection} | Model: {args.model}")
        print("Gõ câu hỏi và nhấn Enter (Gõ 'exit' hoặc 'quit' để thoát).\n")
        while True:
            try:
                user_q = input("\nNhập câu hỏi: ").strip()
                if not user_q:
                    continue
                if user_q.lower() in ("exit", "quit", "q"):
                    break
                if args.compare:
                    run_comparison(retriever, user_q, top_k=args.top_k)
                else:
                    results = retriever.search(user_q, top_k=args.top_k)
                    print_results(results, title=f"Kết quả từ collection '{args.collection}'")
            except (KeyboardInterrupt, EOFError):
                break
        return 0

    if not args.query:
        # Default demo query if none supplied
        demo_query = "Người lao động thử việc có được trả lương không?"
        print(f"Không có query được truyền, sử dụng query mẫu: '{demo_query}'\n")
        if args.compare:
            run_comparison(retriever, demo_query, top_k=args.top_k)
        else:
            results = retriever.search(demo_query, top_k=args.top_k)
            print_results(results, title=f"Kết quả từ collection '{args.collection}'")
        return 0

    if args.compare:
        run_comparison(retriever, args.query, top_k=args.top_k)
    else:
        results = retriever.search(args.query, top_k=args.top_k)
        print_results(results, title=f"Kết quả từ collection '{args.collection}'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
