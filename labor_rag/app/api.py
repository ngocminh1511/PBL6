"""Appendix viewer, retrieval inspection and chat. Run: python -m labor_rag.app.api."""
from __future__ import annotations

import os
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from labor_rag.config import ROOT_DIR
from labor_rag.appendices.catalog import PROCESSED_DIR, load_manifest, read_json
from labor_rag.appendices.runtime import AppendixCatalog, usable

load_dotenv(ROOT_DIR / ".env")
STATIC = Path(__file__).with_name("static")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


class RetrievalRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=20)


def create_app(catalog: AppendixCatalog | None = None, chat_factory=None, storage_factory=None, retrieval_factory=None) -> FastAPI:
    catalog = catalog or AppendixCatalog()
    chats, lock = {}, threading.Lock()
    storage=None
    inspector, retrieval_lock = None, threading.Lock()

    def storage_client():
        nonlocal storage
        if storage is None:
            from labor_rag.appendices.object_storage import R2Store
            storage=storage_factory() if storage_factory else R2Store()
        return storage

    @asynccontextmanager
    async def lifespan(app):
        yield
        for chat in chats.values():
            chat.close()
        if inspector is not None:
            inspector.close()
        if storage is not None:
            storage.close()

    app = FastAPI(title="Phụ lục pháp luật lao động", lifespan=lifespan)
    app.state.catalog = catalog

    @app.get("/api/appendices")
    def listing(document: str | None = None, kind: str | None = None, status: str | None = None,
                q: str = "", offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)):
        from labor_rag.ingest.chunk_schema import ascii_fold, make_document_id
        rows = list(catalog.items.values())
        if document:
            rows = [a for a in rows if a["document_id"] == make_document_id(document)]
        if kind:
            rows = [a for a in rows if a["kind"] == kind]
        if status:
            rows = [a for a in rows if status in {a.get("review_status"), a.get("download_status"), a.get("extraction_status")}]
        if q:
            folded = ascii_fold(q).lower()
            rows = [a for a in rows if folded in ascii_fold(" ".join([a["title"],a["document_number"],a["number"]," ".join(a["forms"])] )).lower()]
        rows.sort(key=lambda a:(a["document_id"],a["key"]))
        return {"total":len(rows),"items":[catalog.public_item(a) for a in rows[offset:offset+limit]],
                "documents":catalog.report.get("documents",[])}

    def item_or_404(appendix_id):
        if appendix_id not in catalog.items:
            raise HTTPException(404,"Không tìm thấy phụ lục trong manifest.")
        return catalog.items[appendix_id]

    @app.get("/api/appendices/{appendix_id}")
    def detail(appendix_id: str):
        return catalog.public_item(item_or_404(appendix_id), detail=True)

    @app.get("/api/appendices/{appendix_id}/view", response_class=HTMLResponse)
    def view(appendix_id: str, chunk_id: str | None = None, download: bool = False):
        item_or_404(appendix_id)
        if chunk_id and (chunk_id not in catalog.chunks or catalog.chunks[chunk_id]["appendix_id"] != appendix_id):
            raise HTTPException(404,"Chunk không thuộc phụ lục này.")
        headers={"X-Content-Type-Options":"nosniff","Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self'"}
        if download:
            headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(appendix_id+".html")
        return HTMLResponse(catalog.render(appendix_id,chunk_id),headers=headers)

    @app.get("/api/files/{artifact_id}")
    def file(artifact_id: str, download: bool = False):
        try:
            artifact=catalog.artifact(artifact_id)
        except KeyError:
            raise HTTPException(404,"File không có trong manifest.")
        remote=artifact.get("storage_backend")=="r2" and bool(artifact.get("r2",{}).get("verified_at"))
        inline=artifact.get("format")=="pdf" and not download
        remote_error=None
        if remote:
            try:
                url=storage_client().download_url(artifact,inline=inline)
                return RedirectResponse(url,status_code=307,headers={"Cache-Control":"no-store","X-Storage-Backend":"r2"})
            except Exception as exc:
                remote_error=exc
        try:
            path,artifact=catalog.file_path(artifact_id)
        except KeyError:
            raise HTTPException(404,"File không có trong manifest.")
        except (FileNotFoundError,ValueError):
            if remote and not isinstance(remote_error,FileNotFoundError):
                raise HTTPException(503,"R2 tạm thời chưa truy cập được và bản trên máy hiện thiếu.")
            raise HTTPException(410,"File nguồn hiện thiếu trên máy; cần thu thập lại.")
        return FileResponse(path,media_type="application/pdf" if inline else "application/octet-stream",
                            filename=artifact["file_name"],content_disposition_type="inline" if inline else "attachment",
                            headers={"X-Content-Type-Options":"nosniff","Content-Security-Policy":"sandbox",
                                     "X-Storage-Backend":"local-fallback" if remote else "local"})

    @app.post("/api/retrieve")
    def retrieve(body: RetrievalRequest):
        nonlocal inspector
        question = body.question.strip()
        if not question:
            raise HTTPException(422, "Câu hỏi không được để trống.")
        before = perf_counter()
        from labor_rag.retrieval.inspect import RetrievalInspector, RetrievalStageError
        with retrieval_lock:
            try:
                if inspector is None:
                    inspector = retrieval_factory() if retrieval_factory else RetrievalInspector(catalog)
                initialization_ms = round((perf_counter() - before) * 1000, 2)
                result = inspector.inspect(question, top_k=body.top_k)
            except RetrievalStageError as exc:
                raise HTTPException(503, f"Bước {exc.stage} chưa hoàn tất ({exc.error_type}).") from None
            except Exception as exc:
                raise HTTPException(503, f"Truy hồi chưa hoàn tất ({type(exc).__name__}).") from None
        result["timings_ms"]["initialization"] = initialization_ms
        result["timings_ms"]["total"] += initialization_ms
        return result

    @app.post("/api/chat")
    def chat(body: ChatRequest):
        if not body.question.strip():
            raise HTTPException(422,"Câu hỏi không được để trống.")
        session_id=body.session_id or uuid.uuid4().hex
        with lock:
            try:
                if session_id not in chats:
                    if len(chats)>=20:
                        chats.pop(next(iter(chats))).close()
                    if chat_factory:
                        chats[session_id]=chat_factory()
                    else:
                        from labor_rag.app.chat import LaborLawChat
                        from labor_rag.retrieval.hybrid_retrieve import HybridRetriever
                        chats[session_id]=LaborLawChat(HybridRetriever(embedding_backend=os.getenv("QUERY_EMBEDDING_BACKEND") or os.getenv("EMBEDDING_BACKEND","local")))
                result=chats[session_id].ask(body.question.strip())
                chats[session_id].history=chats[session_id].history[-20:]
            except Exception as exc:
                # Error text from cloud SDKs may contain endpoint credentials; expose only the type.
                raise HTTPException(503,f"Chat chưa hoàn tất ({type(exc).__name__}). Danh sách và tải file vẫn sử dụng được.") from None
        evidence=[]
        for entry in result["evidence"]:
            value=asdict(entry)
            value["citation"]=entry.citation
            if entry.appendix_id in catalog.items:
                value["view_url"]=catalog.public_item(catalog.items[entry.appendix_id])["view_url"]
                if entry.chunk_id in catalog.chunks:
                    value["view_url"]+="?chunk_id="+quote(entry.chunk_id,safe="")
            evidence.append(value)
        return {**result,"evidence":evidence,"session_id":session_id}

    @app.get("/api/health")
    def health(probe: bool = False):
        raw=load_manifest()
        result={"storage":{"backend":raw.get("storage_backend","local"),"automatic_upload":False,
                           "local_backups_retained":True,
                           "r2_verified_files":sum(bool(a.get("r2",{}).get("verified_at")) for a in raw["artifacts"].values()),
                           "r2":{k:v for k,v in read_json(catalog.directory/"r2_sync_report.json",{}).items()
                                 if k in {"status","verified_file_locations","completed_at"}}},
                "data":{"documents":len(raw["documents"]),"appendices":len(catalog.items),"chunks":len(catalog.chunks),
                        "usable_appendices":sum(usable(a) for a in catalog.items.values()),
                        "needs_review":sum(a["review_status"]=="needs_review" for a in catalog.items.values()),
                        "missing_documents":[d for d in catalog.report.get("documents",[]) if d.get("extraction_status")!="extracted"]},
                "neo4j":read_json(catalog.directory/"neo4j_load_report.json",{"status":"not_checked"}),
                "qdrant":read_json(catalog.directory/"qdrant_load_report.json",{"status":"not_checked"}),
                "embedding":{"backend":os.getenv("QUERY_EMBEDDING_BACKEND") or os.getenv("EMBEDDING_BACKEND","local")},
                "llm":{"provider":os.getenv("LLM_PROVIDER","gemini"),"status":"not_probed"}}
        # Health returns a concise status, never SDK URLs/messages or credentials.
        for key in ["neo4j","qdrant"]:
            result[key]={k:v for k,v in result[key].items() if k in {"status","nodes","edges","appendix_points","base_unchanged","error_type"}}
        if probe:
            from neo4j import GraphDatabase
            from qdrant_client import QdrantClient
            try:
                with GraphDatabase.driver(os.environ["NEO4J_URI"],auth=(os.getenv("NEO4J_USER","neo4j"),os.environ["NEO4J_PASSWORD"]),connection_timeout=8,max_transaction_retry_time=0) as driver:
                    driver.verify_connectivity()
                result["neo4j"]["connection"]="connected"
            except Exception as exc:
                result["neo4j"].update({"connection":"unavailable","error_type":type(exc).__name__})
            try:
                client=QdrantClient(url=os.environ["QDRANT_URL"],api_key=os.getenv("QDRANT_API_KEY"),timeout=10)
                info=client.get_collection(os.getenv("QDRANT_COLLECTION","legal_ld_v5_bge"))
                client.close()
                result["qdrant"].update({"connection":"connected","points":info.points_count})
            except Exception as exc:
                result["qdrant"].update({"connection":"unavailable","error_type":type(exc).__name__})
            try:
                storage_client().check_bucket()
                result["storage"]["r2"]["connection"]="connected"
            except Exception as exc:
                result["storage"]["r2"].update({"connection":"unavailable","error_type":type(exc).__name__})
        return result

    app.mount("/static",StaticFiles(directory=STATIC),name="static")

    @app.get("/",include_in_schema=False)
    def home():
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for name in ["app.js", "style.css"]:
            version = sha256((STATIC / name).read_bytes()).hexdigest()[:12]
            html = html.replace(f"/static/{name}", f"/static/{name}?v={version}")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    return app


def main():
    import uvicorn
    uvicorn.run(create_app(),host="127.0.0.1",port=8000)


if __name__=="__main__":
    main()
