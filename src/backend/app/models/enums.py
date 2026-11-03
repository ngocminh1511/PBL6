from enum import Enum

class RetrievalMode(str, Enum):
    HYBRID = "hybrid"
    VECTOR_ONLY = "vector_only"
    GRAPH_ONLY = "graph_only"

class DocumentType(str, Enum):
    PDF = "pdf"
    PHAP_DIEN_HTML = "phap_dien_html"

class TaskStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"

class UserRole(str, Enum):
    USER = "user"
    LAWYER = "lawyer"
    ADMIN = "admin"

class EmbeddingBackend(str, Enum):
    LOCAL = "local"
    MODAL = "modal"

class VectorDbProvider(str, Enum):
    QDRANT = "qdrant"
    NEO4J = "neo4j"

class LLMProvider(str, Enum):
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

