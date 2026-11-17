"""Bootstrap PostgreSQL setup works without PostgreSQL, Redis or LLM access."""
import os
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from labor_rag.appendices.runtime import AppendixCatalog
from labor_rag.settings import Settings
from src.backend.app.main import create_app
from src.backend.app.services.postgres_configuration import PostgresConfiguration


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('# Keep existing settings\nGEMINI_API_KEY="unchanged-private"\n', encoding="utf-8")
    settings = Settings(_env_file=None, DATABASE_URL="", CONFIG_ENCRYPTION_KEY="", REDIS_ENABLED=False,
                        INTERIM_DIR=tmp_path / "interim", UPLOAD_DIR=tmp_path / "uploads")
    app = create_app(AppendixCatalog(tmp_path / "catalog"), settings=settings, bootstrap_env_file=env_file)
    seen = []
    monkeypatch.setattr(PostgresConfiguration, "_probe", staticmethod(lambda url: seen.append(url)))
    return app, env_file, seen


def test_bootstrap_save_works_without_database_or_encryption_key(setup):
    app, env_file, seen = setup
    value = "postgresql://user:private-password@db.example:5432/app?sslmode=require"
    with TestClient(app) as client:
        assert not client.get("/api/admin/config").json()["can_save"]
        tested = client.post("/api/admin/postgres/check", json={"url": value})
        assert tested.status_code == 200 and tested.json()["status"] == "passed"
        assert "DATABASE_URL" not in dotenv_values(env_file)
        result = client.put("/api/admin/postgres", json={"url": value})
        assert result.status_code == 200 and result.json()["saved"]
        assert result.json()["pending_apply"] and result.json()["can_apply"]
        assert result.json()["host"] == "db.example"
        assert "private-password" not in result.text
        assert dotenv_values(env_file)["DATABASE_URL"] == value
        assert dotenv_values(env_file)["GEMINI_API_KEY"] == "unchanged-private"
        assert env_file.read_text(encoding="utf-8").startswith("# Keep existing settings")
        assert app.state.runtime.settings.DATABASE_URL == ""
        assert not app.state.database.available  # No live clients are reconfigured.
        assert "DATABASE_URL" not in os.environ
        reloaded = client.get("/api/admin/postgres").json()
        assert reloaded["saved"] and reloaded["pending_apply"]
    assert len(seen) == 2


def test_structured_input_encodes_password_and_keeps_it_out_of_metadata(setup):
    app, env_file, seen = setup
    with TestClient(app) as client:
        response = client.put("/api/admin/postgres", json={"mode": "fields", "host": "localhost", "port": 5433,
            "database": "app", "username": "user", "password": "p@ss:/#word", "sslmode": "disable"})
        assert response.status_code == 200
        parsed = make_url(dotenv_values(env_file)["DATABASE_URL"])
        assert parsed.password == "p@ss:/#word" and parsed.query["sslmode"] == "disable"
        metadata = client.get("/api/admin/postgres")
        assert metadata.json()["password_configured"]
        assert "p@ss" not in metadata.text and "url" not in metadata.json()
        checked = client.post("/api/admin/postgres/check", json={"mode": "fields", "host": "localhost", "port": 5433,
            "database": "another", "username": "user", "sslmode": "disable"})
        assert checked.json()["status"] == "passed" and make_url(seen[-1]).password == "p@ss:/#word"
        client.post("/api/admin/postgres/check", json={"mode": "fields", "host": "other.example", "username": "user", "database": "app"})
        assert not make_url(seen[-1]).password


def test_failed_check_never_changes_file_or_claims_success(setup, monkeypatch):
    app, env_file, _ = setup
    original = env_file.read_bytes()
    monkeypatch.setattr(PostgresConfiguration, "_probe", staticmethod(lambda url: (_ for _ in ()).throw(RuntimeError("private-password"))))
    with TestClient(app) as client:
        payload = {"url": "postgresql://u:private-password@offline.example/app"}
        checked = client.post("/api/admin/postgres/check", json=payload)
        assert checked.json()["status"] == "failed" and "private-password" not in checked.text
        saved = client.put("/api/admin/postgres", json=payload)
        assert saved.status_code == 503 and "private-password" not in saved.text
        assert env_file.read_bytes() == original


@pytest.mark.parametrize("process_url,conflict", [
    (None, False),
    ("postgresql://user:private-password@db.example:5432/app?sslmode=require", False),
    ("postgres://user:private-password@db.example:5432/app?sslmode=require", False),
    ("postgresql+psycopg2://user:private-password@db.example:5432/app?sslmode=require", False),
    ("postgresql://user:private-password@other.example:5432/app?sslmode=require", True),
    ("postgresql://user:other-password@db.example:5432/app?sslmode=require", True),
])
def test_environment_warning_requires_a_real_conflict(setup, monkeypatch, process_url, conflict):
    app, env_file, probes = setup
    saved = "postgresql://user:private-password@db.example:5432/app?sslmode=require"
    env_file.write_text('DATABASE_URL="' + saved + '"\n', encoding="utf-8")
    if process_url is not None:
        monkeypatch.setenv("DATABASE_URL", process_url)
    original = env_file.read_bytes()
    with TestClient(app) as client:
        response = client.get("/api/admin/postgres")
        assert response.status_code == 200
        status = response.json()
        assert status["environment_override"] is conflict
        assert status["source"] == ("environment" if process_url else "env_file")
        assert status["can_apply"] is not conflict
        assert status["pending_restart"] is conflict
        assert "private-password" not in response.text and "other-password" not in response.text
        if conflict:
            assert client.post("/api/admin/postgres/apply").status_code == 409
        assert not probes
        assert env_file.read_bytes() == original
        assert os.environ.get("DATABASE_URL") == process_url


def test_environment_without_a_saved_url_is_not_a_conflict(setup, monkeypatch):
    app, _, _ = setup
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private-password@db.example/app")
    with TestClient(app) as client:
        response = client.get("/api/admin/postgres")
        assert response.json()["source"] == "environment"
        assert not response.json()["environment_override"]


@pytest.mark.parametrize("value", ["not-a-url", "sqlite:///local.db", "postgresql://hostonly/app", "postgresql://user:pass@host/app?sslmode=bad"])
def test_invalid_connection_strings_are_sanitized(setup, value):
    app, _, seen = setup
    with TestClient(app) as client:
        response = client.post("/api/admin/postgres/check", json={"url": value})
        assert response.status_code == 422 and not seen
        assert value not in response.text


def test_env_write_failure_does_not_report_saved(setup, monkeypatch):
    import src.backend.app.services.postgres_configuration as module
    app, env_file, _ = setup
    original = env_file.read_bytes()
    monkeypatch.setattr(module, "set_key", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("private-file-details")))
    with TestClient(app) as client:
        response = client.put("/api/admin/postgres", json={"url": "postgresql://u:p@host/app"})
        assert response.status_code == 503 and "private-file-details" not in response.text
        assert env_file.read_bytes() == original


def test_probe_only_reads_and_always_disposes_engine(monkeypatch):
    calls = []
    urls = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query):
            calls.append(str(query))
            return SimpleNamespace(scalar_one=lambda: 1)
    class Engine:
        def connect(self): return Connection()
        def dispose(self): calls.append("disposed")
    import sqlalchemy
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda value, **kwargs: urls.append(value) or Engine())
    PostgresConfiguration._probe("postgresql://u:p@host/app")
    assert calls == ["SELECT 1", "disposed"]
    assert make_url(urls[0]).drivername == "postgresql+psycopg2"


def test_bootstrap_endpoints_keep_existing_admin_auth(setup):
    app, _, _ = setup
    with TestClient(app) as client:
        app.state.runtime.settings = app.state.runtime.settings.model_copy(update={"DEMO_MODE": False})
        assert client.get("/api/admin/postgres").status_code != 200
        assert client.put("/api/admin/postgres", json={"url": "postgresql://u:p@host/app"}).status_code != 200


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg2"])
def test_probe_loads_the_declared_driver_without_connecting(scheme):
    from sqlalchemy import create_engine
    from src.backend.app.repositories.postgres import normalize_database_url
    value = normalize_database_url(scheme + "://test:test@127.0.0.1:1/test")
    engine = create_engine(value)
    try:
        assert engine.dialect.driver == "psycopg2"
    finally:
        engine.dispose()


def test_missing_driver_is_not_reported_as_missing_database(setup, monkeypatch):
    app, _, _ = setup
    def missing_driver(value):
        raise ModuleNotFoundError("No module named 'private-placeholder'")
    monkeypatch.setattr(PostgresConfiguration, "_probe", staticmethod(missing_driver))
    with TestClient(app) as client:
        checked = client.post("/api/admin/postgres/check", json={"url": "postgresql://u:p@host/app"})
        assert checked.json()["status"] == "failed"
        assert checked.json()["details"]["error"] == "dependency"
        assert "driver PostgreSQL" in checked.json()["message"]
        assert "model, collection" not in checked.text and "private-placeholder" not in checked.text


def test_startup_uses_same_postgres_driver_as_connection_check(monkeypatch):
    import src.backend.app.repositories.postgres as module
    import src.backend.app.migrations as migrations
    captured = []
    monkeypatch.setattr(module, "create_engine", lambda value, **kwargs: captured.append(value) or SimpleNamespace(dispose=lambda: None))
    monkeypatch.setattr(migrations, "upgrade", lambda engine: None)
    monkeypatch.setattr(module, "sessionmaker", lambda **kwargs: object())
    database = module.Database("postgres://user:private-password@host/app?sslmode=require")
    database.start()
    assert database.available
    assert make_url(captured[0]).drivername == "postgresql+psycopg2"
    assert make_url(captured[0]).password == "private-password"
    database.close()


@pytest.mark.parametrize("value", ["sqlite://", r"sqlite:///C:\work\test database.db"])
def test_explicit_sqlite_test_urls_are_not_reencoded(value):
    from src.backend.app.repositories.postgres import normalize_database_url
    assert normalize_database_url(value) == value


def isolated_candidate_factory(tmp_path):
    """Exercise real ORM/migrations while redirecting all cloud writes to SQLite."""
    from src.backend.app.repositories.postgres import Database
    def factory(value):
        candidate = Database("sqlite:///" + str(tmp_path / "target.db"))
        original_start = candidate.start
        def start():
            original_start()
            candidate.url = value
        candidate.start = start
        return candidate
    return factory


def test_saved_connection_survives_reload_and_can_be_applied_without_restart(setup, monkeypatch, tmp_path):
    app, _, _ = setup
    monkeypatch.setattr(PostgresConfiguration, "_database", staticmethod(isolated_candidate_factory(tmp_path)))
    resource = app.state.database
    with TestClient(app) as client:
        saved = client.put("/api/admin/postgres", json={"url": "postgresql://user:private-pass@db.example/app"})
        assert saved.status_code == 200
        assert not resource.available
        applied = client.post("/api/admin/postgres/apply")
        assert applied.status_code == 200
        assert applied.json()["saved"] and not applied.json()["pending_apply"]
        assert applied.json()["connection_status"] == "connected"
        assert "private-pass" not in applied.text
        assert app.state.database is resource and app.state.ingestion.database is resource
        assert client.get("/api/admin/config").json()["can_save"]
        state = client.get("/api/admin/postgres").json()
        assert state["saved"] and not state["pending_apply"]
        with resource.session() as db:
            from sqlalchemy import text
            assert db.execute(text("SELECT 1")).scalar_one() == 1


def test_apply_failure_keeps_saved_file_and_old_runtime(setup, monkeypatch):
    app, env_file, _ = setup
    monkeypatch.setattr(PostgresConfiguration, "_database", staticmethod(lambda value: SimpleNamespace(
        available=False, start=lambda: None, close=lambda: None)))
    with TestClient(app) as client:
        client.put("/api/admin/postgres", json={"url": "postgresql://user:pass@db.example/app"})
        content = env_file.read_bytes()
        previous = app.state.runtime.settings
        result = client.post("/api/admin/postgres/apply")
        assert result.status_code == 503
        assert not app.state.database.available and app.state.runtime.settings is previous
        assert env_file.read_bytes() == content
        assert client.get("/api/admin/postgres").json()["saved"]


def test_apply_waits_for_tasks_and_does_not_switch_live_database(setup, monkeypatch, tmp_path):
    app, env_file, _ = setup
    monkeypatch.setattr(PostgresConfiguration, "_database", staticmethod(isolated_candidate_factory(tmp_path)))
    with TestClient(app) as client:
        client.put("/api/admin/postgres", json={"url": "postgresql://user:pass@db.example/app"})
        with app.state.runtime.operation():
            assert client.post("/api/admin/postgres/apply").status_code == 409
        assert client.post("/api/admin/postgres/apply").status_code == 200
        engine = app.state.database.engine
        client.put("/api/admin/postgres", json={"url": "postgresql://user:pass@different.example/app"})
        status = client.get("/api/admin/postgres").json()
        assert status["pending_restart"] and not status["can_apply"]
        assert client.post("/api/admin/postgres/apply").status_code == 409
        assert app.state.database.engine is engine and app.state.database.available


def test_apply_loads_target_runtime_configuration(setup, monkeypatch, tmp_path):
    from src.backend.app.repositories.postgres import Database
    from src.backend.app.models.database import SystemConfig
    target = Database("sqlite:///" + str(tmp_path / "target.db"))
    target.start()
    with target.session() as db:
        db.add(SystemConfig(key="runtime", value={"version": 8, "overrides": {"redis_enabled": False, "qdrant_timeout": 19}}))
        db.commit()
    target.close()
    app, _, _ = setup
    monkeypatch.setattr(PostgresConfiguration, "_database", staticmethod(isolated_candidate_factory(tmp_path)))
    with TestClient(app) as client:
        client.put("/api/admin/postgres", json={"url": "postgresql://user:pass@db.example/app"})
        assert client.post("/api/admin/postgres/apply").status_code == 200
        config = client.get("/api/admin/config").json()
        assert config["config_version"] == 8 and config["qdrant_timeout"] == 19


def test_apply_rejects_target_config_that_cannot_be_decrypted(setup, monkeypatch, tmp_path):
    from src.backend.app.repositories.postgres import Database
    from src.backend.app.models.database import SystemConfig
    target = Database("sqlite:///" + str(tmp_path / "target.db"))
    target.start()
    with target.session() as db:
        db.add(SystemConfig(key="runtime", value={"version": 4, "overrides": {},
            "encrypted_secrets": {"gemini_api_key": "unreadable-ciphertext"}}))
        db.commit()
    target.close()
    app, _, _ = setup
    monkeypatch.setattr(PostgresConfiguration, "_database", staticmethod(isolated_candidate_factory(tmp_path)))
    with TestClient(app) as client:
        client.put("/api/admin/postgres", json={"url": "postgresql://user:pass@db.example/app"})
        previous = app.state.runtime.settings
        result = client.post("/api/admin/postgres/apply")
        assert result.status_code == 503
        assert app.state.runtime.settings is previous and not app.state.database.available
        assert client.get("/api/admin/postgres").json()["saved"]
