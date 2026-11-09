"""Shared startup configuration. Reading settings never opens a connection."""
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore", frozen=True)
    PROJECT_NAME: str = "LexGraph VN - Legal RAG API"
    VERSION: str = "3.0.0"
    API_V1_PREFIX: str = "/api"
    DEMO_MODE: bool = True
    JWT_SECRET: str = Field(default="", repr=False)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    DATABASE_URL: str = Field(default="", repr=False)
    REDIS_URL: str = Field(default="", repr=False)
    REDIS_ENABLED: bool = True
    EMBEDDING_CACHE_TTL: int = 86400 * 7
    SESSION_CACHE_TTL: int = 86400 * 2
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = Field(default="", repr=False)
    QDRANT_COLLECTION: str = "legal_ld_v5_bge"
    QDRANT_TIMEOUT: int = 60
    COLLECTION_MODELS: dict[str, str] = Field(default_factory=dict)
    NEO4J_URI: str = ""
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = Field(default="", repr=False)
    NEO4J_DATABASE: str = "neo4j"
    DATASET_ID: str = "lao_dong_v5"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BACKEND: Literal["local", "modal"] = "modal"
    QUERY_EMBEDDING_BACKEND: Literal["local", "modal"] | None = None
    MODAL_APP_NAME: str = "labor-rag-embed"
    LLM_PROVIDER: Literal["gemini", "anthropic", "openai"] = "gemini"
    GEMINI_API_KEY: str = Field(default="", repr=False)
    GEMINI_MODEL: str = "gemini-3.6-flash"
    ANTHROPIC_API_KEY: str = Field(default="", repr=False)
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    OPENAI_API_KEY: str = Field(default="", repr=False)
    OPENAI_MODEL: str = "gpt-4o-mini"
    UPLOAD_DIR: Path = ROOT_DIR / "data/uploads"
    INTERIM_DIR: Path = ROOT_DIR / "data/interim"
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def query_backend(self) -> str:
        return self.QUERY_EMBEDDING_BACKEND or self.EMBEDDING_BACKEND

    @model_validator(mode="after")
    def validate_dataset(self):
        if not self.DATASET_ID.strip():
            raise ValueError("DATASET_ID must not be empty.")
        return self
