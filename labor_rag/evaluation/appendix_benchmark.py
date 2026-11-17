"""Read-only comparison of the configured corpus with/without appendix points."""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from labor_rag.config import ROOT_DIR
from labor_rag.appendices.catalog import PROCESSED_DIR, now, write_json
from labor_rag.appendices.graph import jsonl
from labor_rag.retrieval.corpus import corpus_filter


def run(scopes, questions_path=None):
    from qdrant_client import QdrantClient
    from labor_rag.ingest.embed_and_index import embed_local, embed_modal
    load_dotenv(ROOT_DIR/".env")
    questions=jsonl(questions_path or Path(__file__).with_name("appendix_questions.jsonl"))
    encode=embed_modal if os.getenv("EMBEDDING_BACKEND")=="modal" else embed_local
    vectors={i:v.tolist() for indices,batch in encode([q["question"] for q in questions],os.getenv("EMBEDDING_MODEL","BAAI/bge-m3"),32768,32) for i,v in zip(indices,batch)}
    client=QdrantClient(url=os.environ["QDRANT_URL"],api_key=os.getenv("QDRANT_API_KEY"),timeout=60)
    rows=[]
    try:
        for scope in scopes:
            for i,q in enumerate(questions):
                hits=client.query_points(os.environ.get("QDRANT_COLLECTION","legal_ld_v5_bge"),query=vectors[i],query_filter=corpus_filter(scope),limit=30,with_payload=True).points
                unique=list(dict.fromkeys(h.payload.get("appendix_id") or h.payload["chunk_id"] for h in hits))[:10]
                ranks=[unique.index(a)+1 for a in q["expected_appendices"] if a in unique]
                rows.append({"id":q["id"],"scope":scope,"first_rank":min(ranks) if ranks else None,"hit_at_5":any(r<=5 for r in ranks),"hit_at_10":bool(ranks),"results":unique})
    finally:
        client.close()
    summaries={s:{"questions":len(questions),"hit_at_5":sum(r["hit_at_5"] for r in rows if r["scope"]==s)/len(questions),
                  "hit_at_10":sum(r["hit_at_10"] for r in rows if r["scope"]==s)/len(questions),
                  "mrr_at_10":sum(1/r["first_rank"] if r["first_rank"] else 0 for r in rows if r["scope"]==s)/len(questions)} for s in scopes}
    result={"generated_at":now(),"evaluation":"appendix_id_retrieval_without_validity_filter","note":"Separate appendix-ID gold set; frozen article benchmark unchanged. Baseline lacks appendix IDs even where an article already contains appendix text. These scores measure appendix-ID retrieval, not answer quality or absence of legal content in the baseline.","summary":summaries,"rows":rows}
    write_json(PROCESSED_DIR/"benchmark_report.json",result)
    return summaries


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-scope",choices=["baseline","extended","appendices"],action="append")
    args=parser.parse_args()
    print(json.dumps(run(args.corpus_scope or ["baseline","extended"]),ensure_ascii=False,indent=2))
