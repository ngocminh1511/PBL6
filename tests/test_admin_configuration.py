"""Runtime settings and diagnostic contracts; every external service is mocked."""
import json
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from labor_rag.appendices.runtime import AppendixCatalog
from labor_rag.settings import Settings
from src.backend.app.main import create_app
from src.backend.app.models.database import SystemConfig
from src.backend.app.services import configuration


@pytest.fixture
def setup(tmp_path, monkeypatch):
    # Other legacy tests import modules that load dotenv. Never use real credentials here.
    for name, field in Settings.model_fields.items():
        monkeypatch.delenv(name, raising=False)
        aliases = getattr(field.validation_alias, "choices", ())
        for alias in aliases:
            monkeypatch.delenv(alias, raising=False)
    settings = Settings(_env_file=None, DATABASE_URL="sqlite:///" + str(tmp_path / "app.db"),
        CONFIG_ENCRYPTION_KEY=Fernet.generate_key().decode(), GEMINI_API_KEY="environment-key",
        QDRANT_URL="https://vectors.example", QDRANT_API_KEY="environment-vector-key",
        NEO4J_URI="neo4j+s://graph.example", REDIS_ENABLED=False,
        UPLOAD_DIR=tmp_path / "uploads", INTERIM_DIR=tmp_path / "interim")
    calls = []
    def fake(service, candidate):
        calls.append((service, candidate))
        return {"dimensions": 3, "points": 7}
    monkeypatch.setattr(configuration, "_check", fake)
    return settings, calls, tmp_path


def application(setup, **changes):
    settings, _, directory = setup
    settings = settings.model_copy(update=changes)
    return create_app(AppendixCatalog(directory / "catalog"), settings=settings)


def test_secrets_are_encrypted_persisted_and_never_returned(setup):
    app = application(setup)
    secret = "private-new-gemini-key"
    with TestClient(app) as client:
        saved = client.put("/api/admin/config", json={"config_version": 1, "gemini_api_key": secret})
        assert saved.status_code == 200
        assert secret not in saved.text and "environment-key" not in saved.text
        assert "gemini_api_key" not in saved.json()
        assert saved.json()["secret_configured"]["gemini_api_key"]
        assert saved.json()["sources"]["gemini_api_key"] == "saved"
        with app.state.database.session() as db:
            record = db.query(SystemConfig).filter_by(key="runtime").one().value
            assert secret not in json.dumps(record)
            assert "gemini_api_key" in record["encrypted_secrets"]
        assert client.put("/api/admin/config", json={"qdrant_timeout": 45}).status_code == 200
        assert app.state.runtime.settings.GEMINI_API_KEY == secret
    restarted = application(setup)
    with TestClient(restarted) as client:
        assert restarted.state.runtime.settings.GEMINI_API_KEY == secret
        assert client.get("/api/admin/config").json()["config_version"] == 3


def test_reset_uses_startup_environment_and_explicit_empty_does_not_fallback(setup):
    app = application(setup)
    with TestClient(app) as client:
        result = client.put("/api/admin/config", json={"qdrant_api_key": ""})
        assert result.status_code == 200
        assert app.state.runtime.settings.QDRANT_API_KEY == ""
        assert not result.json()["secret_configured"]["qdrant_api_key"]
        result = client.put("/api/admin/config", json={"reset_fields": ["qdrant_api_key"]})
        assert result.status_code == 200
        assert app.state.runtime.settings.QDRANT_API_KEY == "environment-vector-key"
        assert result.json()["sources"]["qdrant_api_key"] == "environment"
        assert client.put("/api/admin/config", json={"reset_fields": ["database_url"]}).status_code == 422


def test_can_check_without_postgres_or_encryption_key_but_cannot_save(setup):
    app = application(setup, DATABASE_URL="", CONFIG_ENCRYPTION_KEY="")
    with TestClient(app) as client:
        cfg = client.get("/api/admin/config").json()
        assert not cfg["can_save"] and not cfg["encryption_ready"]
        check = client.post("/api/admin/config/check", json={"service": "llm", "overrides": {"gemini_api_key": "draft-key"}})
        assert check.status_code == 200 and check.json()["status"] == "passed"
        assert "draft-key" not in check.text
        assert app.state.runtime.settings.GEMINI_API_KEY == "environment-key"
        assert client.put("/api/admin/config", json={"gemini_api_key": "draft-key"}).status_code == 503


def test_key_required_only_to_store_nonempty_secret(setup):
    app = application(setup, CONFIG_ENCRYPTION_KEY="")
    with TestClient(app) as client:
        assert client.put("/api/admin/config", json={"qdrant_timeout": 20}).status_code == 200
        rejected = client.put("/api/admin/config", json={"gemini_api_key": "new-secret"})
        assert rejected.status_code == 422 and "CONFIG_ENCRYPTION_KEY" in rejected.text
        assert app.state.runtime.settings.GEMINI_API_KEY == "environment-key"
        assert client.put("/api/admin/config", json={"qdrant_api_key": ""}).status_code == 200


def test_bad_decryption_is_visible_and_does_not_fallback(setup):
    with TestClient(application(setup)) as client:
        assert client.put("/api/admin/config", json={"gemini_api_key": "saved-key"}).status_code == 200
    app = application(setup, CONFIG_ENCRYPTION_KEY="")
    with TestClient(app) as client:
        result = client.get("/api/admin/config").json()
        assert result["configuration_error"] and not result["can_save"]
        assert result["postgres_status"] == "connected"
        assert client.post("/api/admin/config/check", json={"service": "llm"}).status_code == 503
        assert client.get("/health").status_code == 200


def test_group_save_does_not_probe_unrelated_unconfigured_services(setup):
    app = application(setup, GEMINI_API_KEY="", NEO4J_URI="", OBJECT_STORAGE_BUCKET="")
    with TestClient(app) as client:
        response = client.put("/api/admin/config", json={"qdrant_timeout": 30})
        assert response.status_code == 200
    assert [service for service, _ in setup[1]] == ["qdrant"]


def test_checks_use_unsaved_settings_without_writes(setup):
    app = application(setup)
    with TestClient(app) as client:
        response = client.post("/api/admin/config/check", json={"service": "qdrant",
            "overrides": {"qdrant_url": "http://127.0.0.1:6333", "qdrant_api_key": ""}})
        assert response.json()["status"] == "passed"
        assert setup[1][-1][1].QDRANT_URL == "http://127.0.0.1:6333"
        assert setup[1][-1][1].QDRANT_API_KEY == ""
        assert app.state.runtime.settings.QDRANT_URL == "https://vectors.example"
        assert app.state.runtime.version == 1
        with app.state.database.session() as db:
            assert db.query(SystemConfig).count() == 0


def test_failed_checks_and_commit_preserve_active_settings(setup, monkeypatch):
    app = application(setup)
    with TestClient(app) as client:
        def fail(service, config):
            raise RuntimeError("private-key-and-url-must-not-leak")
        monkeypatch.setattr(configuration, "_check", fail)
        result = client.post("/api/admin/config/check", json={"service": "llm"})
        assert result.json()["status"] == "failed" and "private-key" not in result.text
        assert client.put("/api/admin/config", json={"gemini_model": "another-model"}).status_code == 503
        assert app.state.runtime.version == 1
        monkeypatch.setattr(configuration, "_check", lambda *args: {})
        from sqlalchemy.orm import Session
        monkeypatch.setattr(Session, "commit", lambda self: (_ for _ in ()).throw(SQLAlchemyError("private-value")))
        result = client.put("/api/admin/config", json={"gemini_model": "another-model"})
        assert result.status_code == 503 and "private-value" not in result.text
        assert app.state.runtime.settings.GEMINI_MODEL == setup[0].GEMINI_MODEL
        assert app.state.runtime.version == 1


def test_embedding_requires_registered_compatible_collection(setup, monkeypatch):
    app = application(setup)
    with TestClient(app) as client:
        unknown = client.put("/api/admin/config", json={"embedding_model": "new-model"})
        assert unknown.status_code == 422
        def wrong_size(service, config):
            return {"dimensions": 3 if service == "embedding" else 4}
        monkeypatch.setattr(configuration, "_check", wrong_size)
        mismatch = client.put("/api/admin/config", json={"embedding_model": "new-model",
            "collection_models": {"legal_ld_v5_bge": "new-model"}})
        assert mismatch.status_code == 422
        assert app.state.runtime.version == 1


def test_models_use_draft_credentials_and_are_closed(setup, monkeypatch):
    from labor_rag.generation.llm_client import LLMClient
    seen = []
    monkeypatch.setattr(LLMClient, "models", lambda self: seen.append(self.settings) or ["model-one"])
    monkeypatch.setattr(LLMClient, "close", lambda self: seen.append("closed"))
    with TestClient(application(setup)) as client:
        result = client.post("/api/admin/llm/models", json={"overrides": {
            "llm_provider": "local", "local_llm_base_url": "http://127.0.0.1:11434/v1", "local_llm_api_key": "local-private"}})
        assert result.json() == {"provider": "local", "models": ["model-one"]}
        assert seen[0].LOCAL_LLM_API_KEY == "local-private" and seen[1] == "closed"


def test_invalid_admin_requests_never_echo_secrets(setup):
    with TestClient(application(setup)) as client:
        result = client.post("/api/admin/config/check", json={"service": "llm",
            "overrides": {"gemini_api_key": {"value": "private-marker"}}})
        assert result.status_code == 422 and "private-marker" not in result.text


def test_new_admin_apis_keep_existing_authentication(setup):
    with TestClient(application(setup, DEMO_MODE=False, JWT_SECRET="test-only")) as client:
        assert client.post("/api/admin/config/check", json={"service": "llm"}).status_code == 401
        assert client.post("/api/admin/llm/models", json={}).status_code == 401


def test_query_backend_keeps_inheritance_after_environment_reset(setup):
    app = application(setup, QUERY_EMBEDDING_BACKEND=None)
    with TestClient(app) as client:
        initial = client.get("/api/admin/config").json()
        assert initial["query_embedding_inherits"]
        saved = client.put("/api/admin/config", json={"query_embedding_backend": "local"})
        assert saved.status_code == 200 and not saved.json()["query_embedding_inherits"]
        reset = client.put("/api/admin/config", json={"reset_fields": ["query_embedding_backend"], "embedding_backend": "local"})
        assert reset.status_code == 200
        assert reset.json()["query_embedding_inherits"] and reset.json()["query_embedding_backend"] == "local"


@pytest.mark.parametrize("status,expected", [(401, "authentication"), (403, "authentication"), (429, "quota"), (404, "not_found")])
def test_failure_messages_are_sanitized(status, expected):
    error = RuntimeError("private-data")
    error.status_code = status
    code, message = configuration.failure_message(error)
    assert code == expected and "private-data" not in message


def test_llm_local_all_stages_share_the_configured_client(monkeypatch):
    from labor_rag.generation.llm_client import LLMClient, use_settings, complete
    from labor_rag.retrieval.query_rewrite import rewrite_query
    from labor_rag.retrieval.rerank import rerank
    from labor_rag.generation.answer import generate_answer
    from labor_rag.retrieval.hybrid_retrieve import Evidence
    config = Settings(_env_file=None, LLM_PROVIDER="local", LOCAL_LLM_MODEL="installed-model")
    calls = []
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:
        calls.append(kw) or SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))]))))
    client = LLMClient(config)
    client._client = fake
    evidence = Evidence("law:d1", None, "Điều 1", "Nội dung", "vector", 0.7)
    with use_settings(config, client):
        rewrite_query([{"role": "user", "content": "Câu hỏi trước"}], "Câu hỏi sau")
        rerank("Hỏi", [evidence], top_n=1)
        generate_answer("Hỏi", [evidence])
        complete("system", "test")
    assert len(calls) >= 3 and all(call["model"] == "installed-model" for call in calls)


def test_ocr_scoping_and_r2_use_explicit_snapshot(setup, monkeypatch):
    from labor_rag.ocr import settings as ocr_settings
    from labor_rag.ocr import pipeline
    from labor_rag.appendices.object_storage import StorageConfig
    captured = []
    monkeypatch.setattr(pipeline, "_process_document", lambda *args, **kwargs:
        captured.append((ocr_settings.OCR_MODEL, ocr_settings.OCR_DPI, ocr_settings.SEMANTIC_CHUNKING)))
    snapshot = setup[0].model_copy(update={"OCR_MODEL": "vgg_seq2seq", "OCR_DPI": 150, "OCR_SEMANTIC_CHUNKING": True,
        "OBJECT_STORAGE_ENDPOINT_URL": "https://test.r2.cloudflarestorage.com", "OBJECT_STORAGE_BUCKET": "new-bucket",
        "OBJECT_STORAGE_ACCESS_KEY_ID": "new-key", "OBJECT_STORAGE_SECRET_ACCESS_KEY": "new-secret"})
    pipeline.process_document("test.pdf", settings=snapshot)
    assert captured == [("vgg_seq2seq", 150, True)]
    assert ocr_settings.OCR_MODEL == setup[0].OCR_MODEL
    store = StorageConfig.from_settings(snapshot)
    assert store.bucket == "new-bucket" and store.access_key == "new-key"
    assert "new-secret" not in repr(store)


def test_health_failure_does_not_reuse_old_counts(setup, monkeypatch):
    from src.backend.app.services import health
    monkeypatch.setattr(health, "read_json", lambda *args: {"status": "loaded", "nodes": 300, "edges": 1161})
    app = application(setup)
    class BadGraph:
        @staticmethod
        def driver(*args, **kwargs):
            raise RuntimeError("offline")
    import neo4j
    monkeypatch.setattr(neo4j, "GraphDatabase", BadGraph)
    import qdrant_client
    monkeypatch.setattr(qdrant_client, "QdrantClient", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    with TestClient(app):
        result = health.health_status(app.state.runtime, probe=True)
        assert result["neo4j"]["connection"] == "unavailable"
        assert "nodes" not in result["neo4j"] and "edges" not in result["neo4j"]


def profile_input(name="Gemini riêng", key="private-profile-key", **changes):
    return {"name": name, "mode": "cloud", "provider": "gemini", "model": "test-model",
            "api_key_source": "custom", "api_key": key, **changes}


def test_multiple_gemini_profiles_have_independent_keys_and_activation(setup):
    app = application(setup)
    with TestClient(app) as client:
        first = client.post("/api/admin/llm/profiles", json=profile_input("Gemini A", "private-token-a", config_version=1))
        assert first.status_code == 200
        a = next(p for p in first.json()["profiles"] if p["name"] == "Gemini A")
        second = client.post("/api/admin/llm/profiles", json=profile_input("Gemini B", "private-token-b", config_version=2))
        assert second.status_code == 200
        b = next(p for p in second.json()["profiles"] if p["name"] == "Gemini B")
        assert a["id"] != b["id"] and len(second.json()["profiles"]) == 3
        assert app.state.runtime.settings.GEMINI_API_KEY == "environment-key"
        assert "private-token" not in second.text
        with app.state.database.session() as db:
            record = db.query(SystemConfig).one().value
            assert "private-token" not in json.dumps(record)
        active = client.post(f"/api/admin/llm/profiles/{a['id']}/activate", json={"config_version": 3})
        assert active.status_code == 200 and active.json()["active_profile_id"] == a["id"]
        assert app.state.runtime.settings.GEMINI_API_KEY == "private-token-a"
        assert client.request("DELETE", f"/api/admin/llm/profiles/{a['id']}", json={"config_version": 4}).status_code == 409
        deleted = client.request("DELETE", f"/api/admin/llm/profiles/{b['id']}", json={"config_version": 4})
        assert deleted.status_code == 200
        assert client.put("/api/admin/config", json={"qdrant_timeout": 21, "config_version": 5}).status_code == 200
    restarted = application(setup)
    with TestClient(restarted) as client:
        result = client.get("/api/admin/llm/profiles").json()
        assert result["active_profile_id"] == a["id"] and len(result["profiles"]) == 2
        assert restarted.state.runtime.settings.GEMINI_API_KEY == "private-token-a"


def test_editing_inactive_profile_preserves_active_connection_and_key(setup):
    app = application(setup)
    with TestClient(app) as client:
        saved = client.post("/api/admin/llm/profiles", json=profile_input()).json()
        profile = next(p for p in saved["profiles"] if not p["read_only"])
        body = profile_input(name="Gemini đã sửa", model="model-two", config_version=2)
        body.pop("api_key")
        edited = client.put(f"/api/admin/llm/profiles/{profile['id']}", json=body)
        assert edited.status_code == 200
        assert app.state.runtime.settings.GEMINI_API_KEY == "environment-key"
        client.post(f"/api/admin/llm/profiles/{profile['id']}/activate", json={"config_version": 3})
        assert app.state.runtime.settings.GEMINI_API_KEY == "private-profile-key"
        assert app.state.runtime.settings.GEMINI_MODEL == "model-two"


def test_profile_check_failure_and_stale_version_cannot_change_active_llm(setup, monkeypatch):
    app = application(setup)
    with TestClient(app) as client:
        saved = client.post("/api/admin/llm/profiles", json=profile_input()).json()
        identity = next(p["id"] for p in saved["profiles"] if not p["read_only"])
        assert client.post(f"/api/admin/llm/profiles/{identity}/activate", json={"config_version": 1}).status_code == 409
        monkeypatch.setattr(configuration, "_check", lambda *args: (_ for _ in ()).throw(RuntimeError("private-token")))
        failed = client.post(f"/api/admin/llm/profiles/{identity}/activate", json={"config_version": 2})
        assert failed.status_code == 503 and "private-token" not in failed.text
        assert app.state.runtime.settings.GEMINI_API_KEY == "environment-key"
        assert app.state.runtime.version == 2


def test_local_profile_models_and_checks_use_the_entered_server(setup, monkeypatch):
    from labor_rag.generation.llm_client import LLMClient
    seen = []
    monkeypatch.setattr(LLMClient, "models", lambda self: seen.append(self.settings) or ["installed-model-a", "installed-model-b"])
    app = application(setup, DATABASE_URL="", CONFIG_ENCRYPTION_KEY="")
    with TestClient(app) as client:
        body = profile_input(mode="local", provider="local", model="", api_key_source="none", base_url="http://localhost:1234/v1")
        result = client.post("/api/admin/llm/profiles/models", json=body)
        assert result.json()["models"] == ["installed-model-a", "installed-model-b"]
        assert seen[0].LOCAL_LLM_BASE_URL == "http://localhost:1234/v1" and seen[0].LOCAL_LLM_API_KEY == ""
        assert client.post("/api/admin/llm/profiles", json=body).status_code == 503
        assert client.post("/api/admin/llm/profiles/check", json={**body, "mode": "cloud"}).status_code == 422


def test_environment_profile_can_restore_fallback_without_losing_saved_profiles(setup):
    app = application(setup)
    with TestClient(app) as client:
        saved = client.post("/api/admin/llm/profiles", json=profile_input(activate=True))
        assert saved.status_code == 200 and saved.json()["active_profile_id"] != "environment"
        result = client.post("/api/admin/llm/profiles/environment/activate", json={"config_version": 2})
        assert result.status_code == 200 and result.json()["active_profile_id"] == "environment"
        assert len(result.json()["profiles"]) == 2
        assert app.state.runtime.settings.GEMINI_API_KEY == "environment-key"
