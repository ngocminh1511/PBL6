from fastapi import APIRouter, Depends, HTTPException
from src.backend.app.dependencies import get_current_admin
from src.backend.app.models.schemas import AdminConfigUpdate, AdminConfigResponse, SystemStatsResponse
from src.backend.app.models.schemas import ConfigCheckRequest, ConfigCheckResponse, LLMModelsRequest, LLMModelsResponse
from src.backend.app.models.schemas import LLMProfileInput, LLMProfilesResponse, LLMProfileAction
from src.backend.app.models.schemas import PostgresConfigInput, PostgresConfigResponse, PostgresCheckResponse
from src.backend.app.services.llm_profiles import LLMProfiles
from src.backend.app.services.runtime import get_runtime
from src.backend.app.services.health import health_status

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/config", response_model=AdminConfigResponse)
def get_config(runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return runtime.config()


@router.get("/postgres", response_model=PostgresConfigResponse)
def get_postgres(runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return runtime.postgres_config.config()


@router.post("/postgres/check", response_model=PostgresCheckResponse)
def check_postgres(body: PostgresConfigInput, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return runtime.postgres_config.check(body)


@router.put("/postgres", response_model=PostgresConfigResponse)
def save_postgres(body: PostgresConfigInput, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return runtime.postgres_config.save(body)


@router.post("/postgres/apply", response_model=PostgresConfigResponse)
def apply_postgres(runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return runtime.postgres_config.apply()

@router.put("/config", response_model=AdminConfigResponse)
def update_config(body: AdminConfigUpdate, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    data = body.model_dump(mode="json", exclude_unset=True)
    version = data.pop("config_version", None)
    reset = data.pop("reset_fields", [])
    return runtime.update(data, expected_version=version, reset_fields=reset)


@router.post("/config/check", response_model=ConfigCheckResponse)
def check_config(body: ConfigCheckRequest, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    data = body.overrides.model_dump(mode="json", exclude_unset=True)
    reset = data.pop("reset_fields", [])
    return runtime.check(body.service, data, reset)


@router.post("/llm/models", response_model=LLMModelsResponse)
def llm_models(body: LLMModelsRequest, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    data = body.overrides.model_dump(mode="json", exclude_unset=True)
    reset = data.pop("reset_fields", [])
    return runtime.models(data, reset)


@router.get("/llm/profiles", response_model=LLMProfilesResponse)
def list_profiles(runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return LLMProfiles(runtime).listing()


@router.post("/llm/profiles/check", response_model=ConfigCheckResponse)
def check_profile(body: LLMProfileInput, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return LLMProfiles(runtime).check(body)


@router.post("/llm/profiles/models", response_model=LLMModelsResponse)
def profile_models(body: LLMProfileInput, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return LLMProfiles(runtime).models(body)


@router.post("/llm/profiles", response_model=LLMProfilesResponse)
def add_profile(body: LLMProfileInput, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return LLMProfiles(runtime).mutate("save", body=body, expected_version=body.config_version)


@router.put("/llm/profiles/{profile_id}", response_model=LLMProfilesResponse)
def edit_profile(profile_id: str, body: LLMProfileInput, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return LLMProfiles(runtime).mutate("save", identity=profile_id, body=body, expected_version=body.config_version)


@router.post("/llm/profiles/{profile_id}/activate", response_model=LLMProfilesResponse)
def activate_profile(profile_id: str, body: LLMProfileAction, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return LLMProfiles(runtime).mutate("activate", identity=profile_id, expected_version=body.config_version)


@router.delete("/llm/profiles/{profile_id}", response_model=LLMProfilesResponse)
def delete_profile(profile_id: str, body: LLMProfileAction, runtime=Depends(get_runtime), _=Depends(get_current_admin)):
    return LLMProfiles(runtime).mutate("delete", identity=profile_id, expected_version=body.config_version)

@router.get("/system-stats", response_model=SystemStatsResponse)
def statistics(runtime=Depends(get_runtime)):
    from src.backend.app.services.corpus import Corpus
    from src.backend.app.models.database import ChatSession, DocumentRecord
    with runtime.operation(serialized=False):
        h = health_status(runtime, probe=True)
    c = Corpus()
    documents = len(c.documents)
    sessions = None
    if runtime.database.available:
        with runtime.database.session() as db:
            documents = len(set(c.documents) | {row[0] for row in db.query(DocumentRecord.id).all()})
            sessions = db.query(ChatSession).count()
    return SystemStatsResponse(checked_at=h.get("checked_at"), total_documents=documents, total_chunks=h["qdrant"].get("points"),
        total_nodes=h["neo4j"].get("nodes"), total_edges=h["neo4j"].get("edges"),
        total_articles=c.total_articles, total_clauses=c.total_clauses, total_points=c.total_points,
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
