"""Shared startup configuration. Reading settings never opens a connection."""
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from labor_rag.llm_providers import DEFAULT_CLOUD_BASE_URLS

ROOT_DIR = Path(__file__).resolve().parents[1]


# Embedding models compared in the retrieval benchmarks
# (labor_rag/evaluation/results/retrieval_three_models_comparison_report.md),
# each with the Qdrant collection that was indexed with it.
EMBEDDING_CATALOG: tuple[dict, ...] = (
    {"model": "BAAI/bge-m3", "label": "BGE-M3", "dimensions": 1024, "max_tokens": 8192,
     "collection": "legal_ld_v7_bge"},
    {"model": "bkai-foundation-models/vietnamese-bi-encoder", "label": "BKAI Vietnamese bi-encoder",
     "dimensions": 768, "max_tokens": 256, "collection": "legal_ld_v7_bkai"},
    {"model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "label": "Multilingual MPNet",
     "dimensions": 768, "max_tokens": 128, "collection": "legal_ld_v7_mpnet"},
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore", frozen=True)
    PROJECT_NAME: str = "LexGraph VN - Legal RAG API"
    VERSION: str = "3.0.0"
    API_V1_PREFIX: str = "/api"
    DEMO_MODE: bool = True
    HEALTH_PROBE_ON_STARTUP: bool = True
    JWT_SECRET: str = Field(default="", repr=False)
    CONFIG_ENCRYPTION_KEY: str = Field(default="", repr=False)
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
    QDRANT_TIMEOUT: int = Field(default=60, ge=1, le=300)
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
    LLM_PROVIDER: Literal["gemini", "anthropic", "openai", "openrouter", "groq", "qwen", "local"] = "gemini"
    # Reasoning ("thinking") tokens count toward the output limit of every call.
    LLM_REASONING: Literal["default", "off", "low", "medium", "high"] = "default"
    GEMINI_API_KEY: str = Field(default="", repr=False)
    GEMINI_MODEL: str = "gemini-3.6-flash"
    ANTHROPIC_API_KEY: str = Field(default="", repr=False)
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    OPENAI_API_KEY: str = Field(default="", repr=False)
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENROUTER_API_KEY: str = Field(default="", repr=False)
    OPENROUTER_MODEL: str = ""
    OPENROUTER_BASE_URL: str = DEFAULT_CLOUD_BASE_URLS["openrouter"]
    GROQ_API_KEY: str = Field(default="", repr=False)
    GROQ_MODEL: str = ""
    GROQ_BASE_URL: str = DEFAULT_CLOUD_BASE_URLS["groq"]
    QWEN_API_KEY: str = Field(default="", repr=False)
    QWEN_MODEL: str = ""
    QWEN_BASE_URL: str = DEFAULT_CLOUD_BASE_URLS["qwen"]
    LOCAL_LLM_BASE_URL: str = "http://127.0.0.1:11434/v1"
    LOCAL_LLM_MODEL: str = ""
    LOCAL_LLM_API_KEY: str = Field(default="", repr=False)
    HF_TOKEN: str = Field(default="", repr=False)
    OBJECT_STORAGE_PROVIDER: Literal["s3", "r2"] = "s3"
    OBJECT_STORAGE_ENDPOINT_URL: str = Field(default="", validation_alias=AliasChoices("OBJECT_STORAGE_ENDPOINT_URL", "R2_ENDPOINT_URL"))
    OBJECT_STORAGE_BUCKET: str = Field(default="", validation_alias=AliasChoices("OBJECT_STORAGE_BUCKET", "R2_BUCKET_NAME"))
    OBJECT_STORAGE_ACCESS_KEY_ID: str = Field(default="", repr=False, validation_alias=AliasChoices("OBJECT_STORAGE_ACCESS_KEY_ID", "R2_ACCESS_KEY_ID"))
    OBJECT_STORAGE_SECRET_ACCESS_KEY: str = Field(default="", repr=False, validation_alias=AliasChoices("OBJECT_STORAGE_SECRET_ACCESS_KEY", "R2_SECRET_ACCESS_KEY"))
    OBJECT_STORAGE_REGION: str = "auto"
    OBJECT_STORAGE_PREFIX: str = "appendices_v1"
    OCR_MODEL: Literal["vgg_transformer", "vgg_seq2seq"] = "vgg_transformer"
    OCR_DEVICE: str = ""
    OCR_DPI: int = Field(default=300, ge=72, le=600)
    OCR_BEAMSEARCH: bool = False
    OCR_SEMANTIC_CHUNKING: bool = False
    OCR_SEMANTIC_MODEL: str = "BAAI/bge-m3"
    UPLOAD_DIR: Path = ROOT_DIR / "data/uploads"
    INTERIM_DIR: Path = ROOT_DIR / "data/interim"
    MAX_UPLOAD_BYTES: int = Field(default=50 * 1024 * 1024, ge=1, le=1024 * 1024 * 1024)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def query_backend(self) -> str:
        return self.QUERY_EMBEDDING_BACKEND or self.EMBEDDING_BACKEND

    @model_validator(mode="after")
    def validate_dataset(self):
        if not self.DATASET_ID.strip():
            raise ValueError("DATASET_ID must not be empty.")
        if self.EMBEDDING_CACHE_TTL <= 0 or self.SESSION_CACHE_TTL <= 0:
            raise ValueError("Cache TTL must be positive.")
        if self.OCR_DEVICE not in {"", "cpu", "cuda", "cuda:0"}:
            raise ValueError("OCR_DEVICE must be Auto, CPU or CUDA.")
        return self
