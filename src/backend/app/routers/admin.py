from fastapi import APIRouter, Depends, HTTPException
from src.backend.app.dependencies import get_current_admin
from src.backend.app.models.schemas import AdminConfigUpdate, AdminConfigResponse, SystemStatsResponse
from src.backend.app.services.runtime import get_runtime
from src.backend.app.services.health import health_status

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/config", response_model=AdminConfigResponse)
def get_config(runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return runtime.config()

@router.put("/config", response_model=AdminConfigResponse)
def update_config(body: AdminConfigUpdate, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    data = body.model_dump(mode="json", exclude_unset=True)
    version = data.pop("config_version", None)
    return runtime.update(data, expected_version=version)

@router.get("/system-stats", response_model=SystemStatsResponse)
def statistics(runtime=Depends(get_runtime)):
    from src.backend.app.services.corpus import Corpus
    from src.backend.app.models.database import ChatSession, DocumentRecord
    with runtime.operation(serialized=False):
        h = health_status(runtime, probe=True)
    documents = len(Corpus().documents)
    sessions = None
    if runtime.database.available:
        with runtime.database.session() as db:
            documents = len(set(Corpus().documents) | {row[0] for row in db.query(DocumentRecord.id).all()})
            sessions = db.query(ChatSession).count()
    return SystemStatsResponse(total_documents=documents, total_chunks=h["qdrant"].get("points"),
        total_nodes=h["neo4j"].get("nodes"), total_edges=h["neo4j"].get("edges"),
        vector_db_status=h["qdrant"]["connection"], graph_db_status=h["neo4j"]["connection"],
        redis_status=h["redis"]["connection"], active_sessions_count=sessions)

@router.post("/cache/flush")
def flush(runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    with runtime.operation():
        try:
            cache = runtime.cache()
            if cache.status != "connected":
                raise HTTPException(503, "Redis cloud chưa kết nối.")
            count = cache.flush()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Chưa xóa được cache ứng dụng.") from None
    return {"message": "Đã xóa " + str(count) + " mục cache của ứng dụng."}
