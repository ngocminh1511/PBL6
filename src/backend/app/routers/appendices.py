"""Public appendix, source-file and retrieval endpoints. No LLM dependency."""
from time import perf_counter
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

class RetrievalRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Câu hỏi không được để trống.")
        return value.strip()


def create_router(runtime):
    router = APIRouter(tags=["Appendices & Retrieval"])
    catalog = runtime.catalog
    storage_client = runtime.storage

    @router.get("/appendices")
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

    @router.get("/appendices/{appendix_id}")
    def detail(appendix_id: str):
        return catalog.public_item(item_or_404(appendix_id), detail=True)

    @router.get("/appendices/{appendix_id}/view", response_class=HTMLResponse)
    def view(appendix_id: str, chunk_id: str | None = None, download: bool = False):
        item_or_404(appendix_id)
        if chunk_id and (chunk_id not in catalog.chunks or catalog.chunks[chunk_id]["appendix_id"] != appendix_id):
            raise HTTPException(404,"Chunk không thuộc phụ lục này.")
        headers={"X-Content-Type-Options":"nosniff","Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self'"}
        if download:
            headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(appendix_id+".html")
        return HTMLResponse(catalog.render(appendix_id,chunk_id),headers=headers)

    @router.get("/files/{artifact_id}")
    def file(artifact_id: str, download: bool = False):
        with runtime.operation(serialized=False):
            return file_response(artifact_id, download)

    def file_response(artifact_id: str, download: bool = False):
        try:
            artifact=catalog.artifact(artifact_id)
        except KeyError:
            artifact = None
            if runtime.database.available:
                from src.backend.app.models.database import FileArtifact
                with runtime.database.session() as db:
                    record = db.get(FileArtifact, artifact_id)
                    artifact = record.record if record else None
            if artifact is None:
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
            if artifact_id in catalog.artifacts:
                path,artifact=catalog.file_path(artifact_id)
            else:
                from labor_rag.appendices.catalog import local_path
                path = local_path(artifact["path"], roots=(runtime.settings.UPLOAD_DIR, runtime.settings.INTERIM_DIR))
                if not path.is_file():
                    raise FileNotFoundError()
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

    @router.post("/retrieve")
    def retrieve(body: RetrievalRequest):
        question = body.question.strip()
        if not question:
            raise HTTPException(422, "Câu hỏi không được để trống.")
        before = perf_counter()
        from labor_rag.retrieval.inspect import RetrievalInspector, RetrievalStageError
        with runtime.operation():
            try:
                inspector = runtime.inspector()
                initialization_ms = round((perf_counter() - before) * 1000, 2)
                result = inspector.inspect(question, top_k=body.top_k)
            except RetrievalStageError as exc:
                raise HTTPException(503, f"Bước {exc.stage} chưa hoàn tất ({exc.error_type}).") from None
            except Exception as exc:
                raise HTTPException(503, f"Truy hồi chưa hoàn tất ({type(exc).__name__}).") from None
        result["timings_ms"]["initialization"] = initialization_ms
        result["timings_ms"]["total"] += initialization_ms
        return result

    @router.get("/health")
    def health(probe: bool = False):
        from src.backend.app.services.health import health_status
        with runtime.operation(serialized=False):
            return health_status(runtime, probe=probe)

    return router
