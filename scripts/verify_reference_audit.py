"""Confirm selected discovery cases against live Neo4j and Qdrant, without an LLM."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

CASES = {
    "manual08": {
        "target": "45-2019-qh14:d64",
        "markers": ["Tình hình sản xuất, kinh doanh của người sử dụng lao động", "Điều kiện làm việc"],
    },
    "manual13": {
        "target": "45-2019-qh14:d122",
        "markers": ["tổ chức đại diện người lao động tại cơ sở mà người lao động đang bị xử lý kỷ luật là thành viên",
                    "trường hợp là người chưa đủ 15 tuổi thì phải có sự tham gia của người đại diện theo pháp luật"],
    },
    "manual15": {
        "target": "84-2015-qh13:d38",
        "markers": ["1,5 tháng tiền lương", "Thanh toán toàn bộ chi phí y tế đối với người lao động không tham gia bảo hiểm y tế"],
    },
}


def normalized(text):
    return " ".join(text.lower().split())


def run(args):
    # Tripwires: verification cannot use a completion provider, even accidentally.
    for module in ["google.genai", "openai", "anthropic", "labor_rag.generation.llm_client"]:
        sys.modules[module] = None
    logging.disable(logging.CRITICAL)
    print("Loading the retrieval modules; verification will not call embedding or LLM APIs", flush=True)
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    from labor_rag.retrieval.hybrid_retrieve import (
        DATASET_ID, NEO4J_DATABASE, Evidence, HybridRetriever, REFERENCED_COMPONENTS, in_force, khoans_of,
    )

    report = json.loads(args.discovery.read_text(encoding="utf-8"))
    retriever = HybridRetriever(collection=report["collection"], embedding_backend="modal")
    verified = []
    try:
        for question in report["questions"]:
            spec = CASES.get(question["id"])
            if spec is None:
                continue
            seeds = []
            for hit in question["vector_top_k"]:
                document, separator, number = hit["article_id"].rpartition(":d")
                seeds.append(Evidence.from_payload({
                    "chunk_id": hit["chunk_id"], "text": hit["text"], "ten": hit["title"],
                    "document_id": document if separator else None,
                    "meta_dieu": number if separator else None, "meta_khoan": hit["meta_khoan"],
                }, "vector", hit["score"]))
            keys = [{"index": i, "document_id": e.document_id, "meta_dieu": e.meta_dieu,
                     "khoans": khoans_of(e.meta_khoan)}
                    for i, e in enumerate(seeds) if e.document_id and e.meta_dieu]
            with retriever.neo4j.session(database=NEO4J_DATABASE) as session:
                rows = [dict(row) for row in session.run(REFERENCED_COMPONENTS, keys=keys, dataset_id=DATASET_ID)]
            target = spec["target"]
            matched_rows = [row for row in rows if f"{row['document_id']}:d{row['article_number']}" == target]
            expanded = retriever.reference_expand(seeds, limit_per_node=3)
            returned = [e for e in expanded if e.chunk_id == target]
            document, number = target.rsplit(":d", 1)
            points, offset = retriever.qdrant.scroll(
                collection_name=report["collection"], scroll_filter=Filter(must=[in_force(date.fromisoformat(report['as_of'])),
                    FieldCondition(key="document_id", match=MatchValue(value=document)),
                    FieldCondition(key="meta_dieu", match=MatchValue(value=number))]),
                limit=64, with_payload=True, with_vectors=False)
            assert offset is None, "Target article needs more than one verification page"
            seed_text = normalized("\n".join(e.text for e in seeds))
            returned_text = normalized("\n".join(e.text for e in returned))
            marker_checks = [{"text": marker, "in_vector_context": normalized(marker) in seed_text,
                              "in_default_reference_context": normalized(marker) in returned_text}
                             for marker in spec["markers"]]
            item = {
                "id": question["id"], "question": question["question"], "target_article": target,
                "target_rank_in_top50_raw_deduplicated": question["ranks_in_top50_raw"].get(target),
                "vector_top_k": question["vector_top_k"],
                "live_graph_rows": [{**row, "seed_chunk_id": seeds[row["index"]].chunk_id} for row in matched_rows],
                "default_reference_expand_limit_per_node": 3,
                "default_reference_results": [{"chunk_id": e.chunk_id, "clause": e.meta_khoan,
                    "change": e.change, "source": e.source, "text": e.text} for e in returned],
                "qdrant_target_chunks": [{"chunk_id": p.payload["chunk_id"], "text": p.payload["text"]} for p in points],
                "marker_checks": marker_checks,
            }
            assert matched_rows and points and returned, f"Reference verification failed for {question['id']}"
            assert target not in {hit["article_id"] for hit in question["vector_top_k"]}
            assert any(not m["in_vector_context"] and m["in_default_reference_context"] for m in marker_checks)
            verified.append(item)
            print(question["id"], "live_edges=", len(matched_rows), "target_chunks=", len(points),
                  "default_reference_results=", len(returned), "marker_checks=", marker_checks, flush=True)
        result = {"generated_at": datetime.now(timezone.utc).isoformat(), "dataset": DATASET_ID,
                  "collection": report["collection"], "as_of": report["as_of"], "top_k": report["top_k"],
                  "llm_used": False, "embedding_calls_during_verification": 0,
                  "note": "Confirms missing source information, not a legal opinion or universal superiority of graph retrieval. Markers check returned text; relevance still requires manual reading.",
                  "cases": verified}
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Saved", args.output, flush=True)
    finally:
        retriever.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    try:
        run(parser.parse_args())
    except Exception as exc:
        print(f"Verification stopped: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
