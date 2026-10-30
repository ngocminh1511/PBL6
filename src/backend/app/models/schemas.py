from __future__ import annotations
from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field
from src.backend.app.models.enums import RetrievalMode, DocumentType, TaskStatus, EmbeddingBackend, LLMProvider

T = TypeVar("T")

# ================= AUTH SCHEMAS =================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: Optional[str] = "lawyer"

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# ================= EVIDENCE & TRACE SCHEMAS =================
class AmendmentItem(BaseModel):
    chunk_id: str
    citation: str
    change: Optional[str] = None
    text: str

class EvidenceItem(BaseModel):
    chunk_id: str
    mapc: Optional[str] = None
    ten: str
    text: str
    source: str
    score: float = 0.0
    document_id: Optional[str] = None
    meta_dieu: Optional[str] = None
    meta_khoan: Optional[str] = None
    meta_de_muc: Optional[str] = None
    citation: str
    amendments: List[AmendmentItem] = []

class StepQueryRewriteTrace(BaseModel):
    activated: bool = True
    original_query: str
    standalone_query: str
    pronoun_resolved: Optional[str] = None

class StepRetrievalTrace(BaseModel):
    vector_hits_count: int = 0
    vector_score_range: str = "0.0 - 0.0"
    graph_hops_count: int = 0
    refers_to_targets: List[str] = []

class StepRerankTrace(BaseModel):
    retained_count: int = 0
    pruned_count: int = 0
    pruned_citations: List[str] = []

class StepVerificationTrace(BaseModel):
    status: str = "100% Khớp CSDL"
    verified_citations: List[str] = []
    unverified_citations: List[str] = []

class PipelineTrace(BaseModel):
    trace_id: str
    execution_time_ms: int
    step1_query_rewrite: StepQueryRewriteTrace
    step2_hybrid_retrieval: StepRetrievalTrace
    step3_rerank: StepRerankTrace
    step4_verification: StepVerificationTrace

class CitationCheckResult(BaseModel):
    verified: List[str] = []
    unverified: List[str] = []
    all_verified: bool = True

# ================= CHAT SCHEMAS =================
class ChatSessionCreate(BaseModel):
    title: Optional[str] = "Phiên tra cứu mới"
    domain: Optional[str] = "all"
    retrieval_mode: Optional[RetrievalMode] = RetrievalMode.HYBRID

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    domain: str
    retrieval_mode: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: Optional[str] = None

    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    standalone_query: Optional[str] = None
    pipeline_trace: Optional[PipelineTrace] = None
    legal_evidence: Optional[List[EvidenceItem]] = None
    citation_check: Optional[CitationCheckResult] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SessionDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]

class ChatAskRequest(BaseModel):
    session_id: Optional[str] = None
    question: str
    domain: Optional[str] = "all"
    retrieval_mode: Optional[RetrievalMode] = RetrievalMode.HYBRID
    top_k: Optional[int] = 8
    rerank_top_n: Optional[int] = 5

class ChatAskResponse(BaseModel):
    session_id: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse

# ================= PAGINATION SCHEMAS =================
class CursorPage(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: Optional[str] = None
    has_more: bool = False
    total_count: Optional[int] = None

# ================= DOCUMENT SCHEMAS =================
class DocumentResponse(BaseModel):
    id: str
    title: str
    document_number: Optional[str] = None
    document_type: str
    domain: str
    effective_from_date: Optional[str] = None
    status: str
    chunks_count: int = 0
    nodes_count: int = 0
    edges_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DocumentASTResponse(BaseModel):
    document_id: str
    title: str
    ast_tree: Dict[str, Any]

class IngestionTaskResponse(BaseModel):
    id: str
    document_id: Optional[str] = None
    file_name: str
    document_type: str
    status: TaskStatus
    progress: float
    current_step: str
    total_chunks: int = 0
    embedded_chunks: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    task_id: str
    message: str
    document_id: str

# ================= ADMIN SCHEMAS =================
class AdminConfigUpdate(BaseModel):
    embedding_model: Optional[str] = None
    embedding_backend: Optional[EmbeddingBackend] = None
    vector_db: Optional[str] = "qdrant"
    qdrant_url: Optional[str] = None
    qdrant_collection: Optional[str] = None
    llm_provider: Optional[LLMProvider] = None
    gemini_model: Optional[str] = None
    modal_app_name: Optional[str] = None

class AdminConfigResponse(BaseModel):
    embedding_model: str
    embedding_backend: str
    vector_db: str
    qdrant_url: str
    qdrant_collection: str
    llm_provider: str
    gemini_model: str
    modal_app_name: str
    neo4j_uri: str
    redis_enabled: bool

class SystemStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_nodes: int
    total_edges: int
    vector_db_status: str
    graph_db_status: str
    redis_status: str
    active_sessions_count: int
