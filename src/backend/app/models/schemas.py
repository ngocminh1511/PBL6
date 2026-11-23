from __future__ import annotations
from typing import Optional, List, Dict, Any, Generic, TypeVar, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from src.backend.app.models.enums import RetrievalMode, DocumentType, TaskStatus, EmbeddingBackend, LLMProvider

T = TypeVar("T")
LLMReasoning = Literal["default", "off", "low", "medium", "high"]

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
class LLMCallUsage(BaseModel):
    stage: str
    provider: str
    model: str
    status: Literal["succeeded", "failed"]
    input_tokens: Optional[int] = Field(None, ge=0)
    output_tokens: Optional[int] = Field(None, ge=0)
    total_tokens: Optional[int] = Field(None, ge=0)
    cached_input_tokens: Optional[int] = Field(None, ge=0)
    reasoning_tokens: Optional[int] = Field(None, ge=0)
    requested_tokens: Optional[int] = Field(None, ge=0)
    error_type: Optional[str] = None
    http_status: Optional[int] = None


class TokenUsage(BaseModel):
    status: Literal["complete", "partial", "unavailable"]
    input_tokens: Optional[int] = Field(None, ge=0)
    output_tokens: Optional[int] = Field(None, ge=0)
    total_tokens: Optional[int] = Field(None, ge=0)
    executed_stages: List[str] = Field(default_factory=list)
    calls: List[LLMCallUsage] = Field(default_factory=list)


class ChatAskErrorResponse(BaseModel):
    detail: str
    token_usage: Optional[TokenUsage] = None


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "Phiên tra cứu mới"
    domain: Literal["all", "lao_dong"] = "all"
    retrieval_mode: Optional[RetrievalMode] = RetrievalMode.HYBRID

class ChatSessionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)

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
    token_usage: Optional[TokenUsage] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    feedback: Optional[Literal["up", "down"]] = None
    created_at: datetime

    @field_validator("attachments", "warnings", mode="before")
    @classmethod
    def empty_lists(cls, value):
        return value or []

    model_config = ConfigDict(from_attributes=True)

class MessageFeedbackRequest(BaseModel):
    """`null` clears the reader's rating of an assistant answer."""
    feedback: Optional[Literal["up", "down"]] = None

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
    articles_count: Optional[int] = 0
    clauses_count: Optional[int] = 0
    points_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentASTResponse(BaseModel):
    document_id: str
    title: str
    ast_tree: Dict[str, Any]

class OCRPagePreview(BaseModel):
    page_number: int
    method: str
    confidence: Optional[float] = None
    char_count: int = 0
    preview_text: str = ""

class OCRPageDetail(OCRPagePreview):
    text: str = ""

class OCRPageUpdateRequest(BaseModel):
    text: str

class OCRPreviewSummary(BaseModel):
    total_pages: int = 0
    processed_pages: int = 0
    text_pages: int = 0
    ocr_pages: int = 0
    empty_pages: int = 0
    avg_confidence: Optional[float] = None
    heuristic_score: Optional[float] = None
    articles_count: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    recent_pages: List[OCRPagePreview] = Field(default_factory=list)

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
    ocr_preview: Optional[OCRPreviewSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UploadResponse(BaseModel):
    task_id: str
    message: str
    document_id: Optional[str] = None

# ================= ADMIN SCHEMAS =================
class AdminConfigUpdate(BaseModel):
    reset_fields: List[str] = Field(default_factory=list)
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
    llm_reasoning: Optional[LLMReasoning] = None
    gemini_model: Optional[str] = None
    modal_app_name: Optional[str] = None
    gemini_api_key: Optional[str] = Field(default=None, repr=False)
    openai_api_key: Optional[str] = Field(default=None, repr=False)
    anthropic_api_key: Optional[str] = Field(default=None, repr=False)
    openrouter_api_key: Optional[str] = Field(default=None, repr=False)
    openrouter_model: Optional[str] = None
    openrouter_base_url: Optional[str] = None
    groq_api_key: Optional[str] = Field(default=None, repr=False)
    groq_model: Optional[str] = None
    groq_base_url: Optional[str] = None
    qwen_api_key: Optional[str] = Field(default=None, repr=False)
    qwen_model: Optional[str] = None
    qwen_base_url: Optional[str] = None
    local_llm_base_url: Optional[str] = None
    local_llm_model: Optional[str] = None
    local_llm_api_key: Optional[str] = Field(default=None, repr=False)
    hf_token: Optional[str] = Field(default=None, repr=False)
    qdrant_api_key: Optional[str] = Field(default=None, repr=False)
    qdrant_timeout: Optional[int] = None
    collection_models: Optional[Dict[str, str]] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = Field(default=None, repr=False)
    neo4j_database: Optional[str] = None
    object_storage_provider: Optional[Literal["s3", "r2"]] = None
    object_storage_endpoint_url: Optional[str] = None
    object_storage_region: Optional[str] = None
    object_storage_bucket: Optional[str] = None
    object_storage_prefix: Optional[str] = None
    object_storage_access_key_id: Optional[str] = Field(default=None, repr=False)
    object_storage_secret_access_key: Optional[str] = Field(default=None, repr=False)
    redis_url: Optional[str] = Field(default=None, repr=False)
    embedding_cache_ttl: Optional[int] = None
    session_cache_ttl: Optional[int] = None
    ocr_model: Optional[Literal["vgg_transformer", "vgg_seq2seq"]] = None
    ocr_device: Optional[Literal["", "cpu", "cuda", "cuda:0"]] = None
    ocr_dpi: Optional[int] = None
    ocr_beamsearch: Optional[bool] = None
    ocr_semantic_chunking: Optional[bool] = None
    ocr_semantic_model: Optional[str] = None
    max_upload_bytes: Optional[int] = None

class AdminConfigResponse(BaseModel):
    active_llm_profile_id: Optional[str] = None
    config_version: int
    demo_mode: bool
    dataset_id: str
    query_embedding_backend: str
    available_collections: Dict[str, str]
    anthropic_model: str
    openai_model: str
    openrouter_model: str
    openrouter_base_url: str
    groq_model: str
    groq_base_url: str
    qwen_model: str
    qwen_base_url: str
    embedding_model: str
    embedding_backend: str
    vector_db: str
    qdrant_url: str
    qdrant_collection: str
    llm_provider: str
    llm_reasoning: str
    gemini_model: str
    modal_app_name: str
    neo4j_uri: str
    redis_enabled: bool
    local_llm_base_url: str
    local_llm_model: str
    qdrant_timeout: int
    collection_models: Dict[str, str]
    neo4j_user: str
    neo4j_database: str
    object_storage_provider: str
    object_storage_endpoint_url: str
    object_storage_region: str
    object_storage_bucket: str
    object_storage_prefix: str
    embedding_cache_ttl: int
    session_cache_ttl: int
    ocr_model: str
    ocr_device: str
    ocr_dpi: int
    ocr_beamsearch: bool
    ocr_semantic_chunking: bool
    ocr_semantic_model: str
    max_upload_bytes: int
    sources: Dict[str, Literal["saved", "environment", "default"]]
    secret_configured: Dict[str, bool]
    environment_values: Dict[str, Any]
    environment_secret_configured: Dict[str, bool]
    environment_sources: Dict[str, Literal["environment", "default"]]
    query_embedding_inherits: bool
    environment_query_embedding_inherits: bool
    can_save: bool
    encryption_ready: bool
    configuration_error: Optional[str] = None
    postgres_status: str
    postgres_endpoint: str
    redis_endpoint: str
    startup: Dict[str, Any]


ConfigService = Literal["llm", "embedding", "qdrant", "neo4j", "r2", "redis", "ocr"]


class ConfigCheckRequest(BaseModel):
    service: ConfigService
    overrides: AdminConfigUpdate = Field(default_factory=AdminConfigUpdate)


class ConfigCheckResponse(BaseModel):
    service: ConfigService
    status: Literal["passed", "failed", "not_configured", "disabled"]
    message: str
    checked_at: str
    latency_ms: int
    details: Dict[str, Any] = Field(default_factory=dict)


class LLMModelsRequest(BaseModel):
    overrides: AdminConfigUpdate = Field(default_factory=AdminConfigUpdate)


class LLMModelsResponse(BaseModel):
    provider: str
    models: List[str]


class LLMProfileInput(BaseModel):
    config_version: Optional[int] = None
    name: str = Field(default="", max_length=100)
    mode: Literal["cloud", "local"]
    provider: Literal["gemini", "openai", "anthropic", "openrouter", "groq", "qwen", "local"]
    model: str = ""
    base_url: str = ""
    local_runtime: Literal["ollama", "lmstudio", "compatible"] = "ollama"
    api_key_source: Literal["custom", "environment", "none"] = "custom"
    api_key: Optional[str] = Field(default=None, repr=False)
    reasoning: LLMReasoning = "default"
    profile_id: Optional[str] = None
    copy_key_from: Optional[str] = None
    activate: bool = False


class LLMProfileResponse(BaseModel):
    id: str
    name: str
    mode: Literal["cloud", "local"]
    provider: str
    model: str
    base_url: str
    local_runtime: str
    api_key_source: str
    reasoning: str = "default"
    key_configured: bool
    read_only: bool = False
    verification: Optional[ConfigCheckResponse] = None


class LLMProfilesResponse(BaseModel):
    profiles: List[LLMProfileResponse]
    active_profile_id: str
    config_version: int
    can_save: bool
    encryption_ready: bool


class LLMProfileAction(BaseModel):
    config_version: Optional[int] = None


class PostgresConfigInput(BaseModel):
    mode: Literal["url", "fields"] = "url"
    url: Optional[str] = Field(default=None, repr=False)
    host: str = ""
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = ""
    username: str = ""
    password: Optional[str] = Field(default=None, repr=False)
    sslmode: Literal["require", "verify-full", "verify-ca", "prefer", "allow", "disable"] = "require"


class PostgresConfigResponse(BaseModel):
    configured: bool
    connection_status: str
    host: str
    port: int
    database: str
    username: str
    sslmode: str
    password_configured: bool
    source: Literal["environment", "env_file", "default"]
    environment_override: bool = Field(description="True only when the process DATABASE_URL conflicts with the saved .env URL.")
    pending_restart: bool
    pending_apply: bool
    can_apply: bool
    saved: bool = False
    message: str = ""


class PostgresCheckResponse(BaseModel):
    status: Literal["passed", "failed", "not_configured"]
    message: str
    checked_at: str
    latency_ms: int
    details: Dict[str, Any] = Field(default_factory=dict)


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
    checked_at: Optional[str] = None
    total_documents: Optional[int] = None
    total_chunks: Optional[int] = None
    total_nodes: Optional[int] = None
    total_edges: Optional[int] = None
    total_articles: Optional[int] = None
    total_clauses: Optional[int] = None
    total_points: Optional[int] = None
    total_demuc: Optional[int] = None
    total_pdf_docs: Optional[int] = None
    vector_db_status: str
    graph_db_status: str
    redis_status: str
    active_sessions_count: Optional[int] = None
