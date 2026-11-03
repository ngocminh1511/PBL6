"""Upsert only appendix vectors; fingerprint the existing base points before/after."""
from __future__ import annotations

import argparse
import hashlib
import json
import os

from dotenv import load_dotenv

from labor_rag.config import ROOT_DIR
from labor_rag.ingest.chunk_schema import article_id, make_chunk_id, point_id
from .catalog import PROCESSED_DIR, read_json, write_json
from .graph import jsonl


def fingerprint(client, collection: str) -> dict:
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    rows, offset = [], None
    while True:
        points, offset = client.scroll(collection,scroll_filter=Filter(must_not=[FieldCondition(key="chunk_type",match=MatchValue(value="appendix"))]),
                                       offset=offset,limit=256,with_payload=True,with_vectors=True)
        for point in points:
            value=json.dumps({"id":str(point.id),"payload":point.payload,"vector":point.vector},sort_keys=True,ensure_ascii=False,separators=(",",":"))
            rows.append((str(point.id),hashlib.sha256(value.encode()).hexdigest()))
        if offset is None:
            break
    digest=hashlib.sha256(json.dumps(sorted(rows),separators=(",",":")).encode()).hexdigest()
    return {"points":len(rows),"sha256":digest}


def run(output_dir=PROCESSED_DIR) -> dict:
    from qdrant_client import QdrantClient
    from qdrant_client.models import FieldCondition, Filter, MatchValue, PayloadSchemaType, PointIdsList, PointStruct
    from labor_rag.ingest.embed_and_index import embed_local, embed_modal, upsert_with_retry
    load_dotenv(ROOT_DIR/".env")
    collection=os.getenv("QDRANT_COLLECTION","legal_ld_v5_bge")
    client=QdrantClient(url=os.getenv("QDRANT_URL","http://localhost:6333"),api_key=os.getenv("QDRANT_API_KEY") or None,timeout=60)
    client.get_collection(collection)  # never recreate an existing corpus
    for field in ["chunk_type","appendix_id","appendix_dataset_id","article_keys","kind"]:
        client.create_payload_index(collection,field_name=field,field_schema=PayloadSchemaType.KEYWORD,wait=True)
    before=fingerprint(client,collection)
    write_json(output_dir/"qdrant_base_before.json",before)
    chunks=jsonl(output_dir/"chunks.jsonl")
    dataset=os.getenv("DATASET_ID","lao_dong_v5")
    for chunk in chunks:
        assert chunk["chunk_type"]=="appendix" and chunk["chunk_id"].startswith(chunk["document_id"]+":pl")
        chunk.update({"dataset_id":dataset,"appendix_dataset_id":"appendices_v1",
                      "article_keys":[make_chunk_id(a["document_id"],a["article_number"]) for a in chunk.get("article_ids",[])]})
    existing, offset = {}, None
    while True:
        points,offset=client.scroll(collection,scroll_filter=Filter(must=[FieldCondition(key="appendix_dataset_id",match=MatchValue(value="appendices_v1"))]),
                                    offset=offset,limit=256,with_payload=True,with_vectors=False)
        existing.update({p.payload["chunk_id"]:p.payload for p in points})
        if offset is None:
            break
    changed=[c for c in chunks if existing.get(c["chunk_id"],{}).get("text")!=c["text"]]
    refresh=[c for c in chunks if c["chunk_id"] in existing and existing[c["chunk_id"]].get("text")==c["text"] and existing[c["chunk_id"]]!=c]
    for chunk in refresh:
        client.overwrite_payload(collection,payload=chunk,points=[point_id(chunk["chunk_id"])],wait=True)
    backend=os.getenv("EMBEDDING_BACKEND","local")
    model=os.getenv("EMBEDDING_MODEL","BAAI/bge-m3")
    if changed:
        embed=embed_modal if backend=="modal" else embed_local
        for indices,vectors in embed([c["text"] for c in changed],model,32768 if backend=="modal" else 8192,64):
            points=[PointStruct(id=point_id(changed[i]["chunk_id"]),vector=vector.tolist(),payload=changed[i]) for i,vector in zip(indices,vectors)]
            upsert_with_retry(client,collection,points)
    # Remove only this pipeline's obsolete parts inside the current collection scope.
    scoped_docs={d["document_id"] for d in read_json(output_dir/"manifest.json",{}).get("documents",[])}
    incoming={c["chunk_id"] for c in chunks}
    stale=[point_id(key) for key,payload in existing.items() if key not in incoming and payload.get("document_id") in scoped_docs]
    if stale:
        client.delete(collection,points_selector=PointIdsList(points=stale),wait=True)
    after=fingerprint(client,collection)
    result={"status":"indexed" if before==after else "base_changed","collection":collection,"backend":backend,
            "embedded":len(changed),"metadata_refreshed":len(refresh),"obsolete_appendix_parts_removed":len(stale),
            "appendix_points":len(chunks),"base_before":before,"base_after":after,"base_unchanged":before==after,"r2_uploaded":False}
    write_json(output_dir/"qdrant_load_report.json",result)
    client.close()
    if before!=after:
        raise RuntimeError("Base corpus fingerprint changed; inspect the load report")
    return result


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(json.dumps(run(),ensure_ascii=False,indent=2))
    except Exception as exc:
        write_json(PROCESSED_DIR/"qdrant_error.json",{"status":"failed","error_type":type(exc).__name__,"message":str(exc)[:300]})
        raise


if __name__=="__main__":
    main()
