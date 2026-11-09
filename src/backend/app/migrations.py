"""Additive, versioned schema upgrades for new and pre-merge databases."""
from sqlalchemy import inspect, text

REVISION = "001_unified_backend"


def upgrade(engine):
    from src.backend.app.models.database import Base
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS app_schema_versions "
            "(revision VARCHAR(100) PRIMARY KEY)"
        ))
        applied = connection.execute(text(
            "SELECT revision FROM app_schema_versions WHERE revision=:revision"
        ), {"revision": REVISION}).first()
        if applied:
            return
        # No tables, rows, collections or volumes are dropped by this migration.
        Base.metadata.create_all(connection)
        for table, column in [
            ("chat_messages", "attachments"), ("chat_messages", "warnings"),
            ("ingestion_tasks", "result"),
        ]:
            if column not in {c["name"] for c in inspect(connection).get_columns(table)}:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} JSON"))
        connection.execute(text(
            "INSERT INTO app_schema_versions (revision) VALUES (:revision)"
        ), {"revision": REVISION})
