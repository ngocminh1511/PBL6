from __future__ import annotations
from typing import Optional, List, Dict, Any, Generic, TypeVar, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from src.backend.app.models.enums import RetrievalMode, DocumentType, TaskStatus, EmbeddingBackend, LLMProvider

T = TypeVar("T")

# ================= AUTH SCHEMAS =================
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: Literal["user", "lawyer"] = "lawyer"

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

    model_config = ConfigDict(from_attributes=True)

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
    version_date: Optional[str] = None
    change: Optional[str] = None
    chunk_type: str = "article"
    appendix_id: Optional[str] = None
    appendix_number: Optional[str] = None
    document_number: Optional[str] = None
    artifact_ids: List[str] = Field(default_factory=list)
    locator: Dict[str, Any] = Field(default_factory=dict)
    source_url: Optional[str] = None
    view_url: Optional[str] = None
    amendments: List[EvidenceItem] = Field(default_factory=list)

class StepQueryRewriteTrace(BaseModel):
    activated: bool = True
    original_query: str
    standalone_query: str
    pronoun_resolved: Optional[str] = None

class StepRetrievalTrace(BaseModel):
    vector_hits_count: int = 0
    vector_score_range: str = "0.0 - 0.0"
    graph_hops_count: int = 0
    refers_to_targets: List[str] = Field(default_factory=list)

class StepRerankTrace(BaseModel):
    retained_count: int = 0
    pruned_count: int = 0
    pruned_citations: List[str] = Field(default_factory=list)

class StepVerificationTrace(BaseModel):
    status: str = "Chưa xác minh"
    verified_citations: List[str] = Field(default_factory=list)
    unverified_citations: List[str] = Field(default_factory=list)

class PipelineTrace(BaseModel):
    trace_id: str
    execution_time_ms: int
    step1_query_rewrite: StepQueryRewriteTrace
    step2_hybrid_retrieval: StepRetrievalTrace
    step3_rerank: StepRerankTrace
    step4_verification: StepVerificationTrace
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    config_version: Optional[int] = None

class CitationCheckResult(BaseModel):
    verified: List[str] = Field(default_factory=list)
    unverified: List[str] = Field(default_factory=list)
    all_verified: bool = True

# ================= CHAT SCHEMAS =================
class ChatSessionCreate(BaseModel):
    title: Optional[str] = "Phiên tra cứu mới"
    domain: Literal["all", "lao_dong"] = "all"
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

    model_config = ConfigDict(from_attributes=True)

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
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime

    @field_validator("attachments", "warnings", mode="before")
    @classmethod
    def empty_lists(cls, value):
        return value or []

    model_config = ConfigDict(from_attributes=True)

class SessionDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]

class ChatAskRequest(BaseModel):
    session_id: Optional[str] = None
    question: str = Field(min_length=1, max_length=4000)
    domain: Literal["all", "lao_dong"] = "all"
    retrieval_mode: Optional[RetrievalMode] = RetrievalMode.HYBRID
    top_k: int = Field(default=8, ge=1, le=20)
    rerank_top_n: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Câu hỏi không được để trống.")
        return value.strip()

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

    model_config = ConfigDict(from_attributes=True)

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
    result: Optional[Dict[str, Any]] = None
    progress: float
    current_step: str
    total_chunks: int = 0
    embedded_chunks: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UploadResponse(BaseModel):
    task_id: str
    message: str
    document_id: Optional[str] = None

# ================= ADMIN SCHEMAS =================
class AdminConfigUpdate(BaseModel):
    config_version: Optional[int] = None
    query_embedding_backend: Optional[EmbeddingBackend] = None
    neo4j_uri: Optional[str] = None
    redis_enabled: Optional[bool] = None
    anthropic_model: Optional[str] = None
    openai_model: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_backend: Optional[EmbeddingBackend] = None
    vector_db: Optional[str] = "qdrant"
    qdrant_url: Optional[str] = None
    qdrant_collection: Optional[str] = None
    llm_provider: Optional[LLMProvider] = None
    gemini_model: Optional[str] = None
    modal_app_name: Optional[str] = None

class AdminConfigResponse(BaseModel):
    config_version: int
    demo_mode: bool
    dataset_id: str
    query_embedding_backend: str
    available_collections: Dict[str, str]
    anthropic_model: str
    openai_model: str
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


class GraphNode(BaseModel):
    id: str
    label: str
    title: str
    document_id: Optional[str] = None
    article_number: Optional[str] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    status: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    warnings: List[str] = Field(default_factory=list)

class SystemStatsResponse(BaseModel):
    total_documents: Optional[int] = None
    total_chunks: Optional[int] = None
    total_nodes: Optional[int] = None
    total_edges: Optional[int] = None
    vector_db_status: str
    graph_db_status: str
    redis_status: str
    active_sessions_count: Optional[int] = None
