import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Ensure .env is loaded from workspace root
ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        from pydantic import BaseModel as BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "LexGraph VN - Legal RAG API"
    VERSION: str = "2.4.8"
    API_V1_PREFIX: str = "/api"
    
    # Security / Auth
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-lexgraph-judicial-key-2026")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # PostgreSQL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/lexgraph_db"
    )
    
    # Redis Cache
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED: bool = True
    EMBEDDING_CACHE_TTL: int = 86400 * 7  # 7 days
    SESSION_CACHE_TTL: int = 86400 * 2   # 2 days
    
    # Vector DB (Qdrant)
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "legal_ld_v5_bge")
    
    # Graph DB (Neo4j)
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "labor_rag_pw")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
    DATASET_ID: str = os.getenv("DATASET_ID", "lao_dong_v5")
    
    # Embedding Configuration
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    EMBEDDING_BACKEND: str = os.getenv("EMBEDDING_BACKEND", "local")  # "local" | "modal"
    MODAL_APP_NAME: str = os.getenv("MODAL_APP_NAME", "labor-rag-embed")
    
    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" | "anthropic" | "openai"
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Upload & Storage
    UPLOAD_DIR: Path = ROOT_DIR / "data" / "uploads"
    INTERIM_DIR: Path = ROOT_DIR / "data" / "interim"
    
    class Config:
        env_file = ROOT_DIR / ".env"
        extra = "allow"

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
