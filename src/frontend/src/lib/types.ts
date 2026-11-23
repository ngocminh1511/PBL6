export type RetrievalMode = 'hybrid' | 'vector_only' | 'graph_only';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  role: string;
}

export interface AmendmentItem {
  chunk_id: string;
  citation: string;
  change?: string;
  text: string;
}

export interface EvidenceItem {
  chunk_id: string;
  mapc?: string;
  ten: string;
  text: string;
  source: string;
  score: number;
  document_id?: string;
  meta_dieu?: string;
  meta_khoan?: string;
  meta_de_muc?: string;
  citation: string;
  amendments: EvidenceItem[];
  version_date?: string;
  change?: string;
  chunk_type?: string;
  appendix_id?: string;
  appendix_number?: string;
  document_number?: string;
  artifact_ids?: string[];
  locator?: Record<string, unknown>;
  source_url?: string;
  view_url?: string;
}

export interface StepQueryRewriteTrace {
  activated: boolean;
  original_query: string;
  standalone_query: string;
  pronoun_resolved?: string;
}

export interface StepRetrievalTrace {
  vector_hits_count: number;
  vector_score_range: string;
  graph_hops_count: number;
  refers_to_targets: string[];
}

export interface StepRerankTrace {
  retained_count: number;
  pruned_count: number;
  pruned_citations: string[];
}

export interface StepVerificationTrace {
  status: string;
  verified_citations: string[];
  unverified_citations: string[];
}

export interface PipelineTrace {
  trace_id: string;
  execution_time_ms: number;
  step1_query_rewrite: StepQueryRewriteTrace;
  step2_hybrid_retrieval: StepRetrievalTrace;
  step3_rerank: StepRerankTrace;
  step4_verification: StepVerificationTrace;
  timings_ms?: Record<string, number>;
  config_version?: number;
}

export interface CitationCheckResult {
  verified: string[];
  unverified: string[];
  all_verified: boolean;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  standalone_query?: string;
  pipeline_trace?: PipelineTrace;
  legal_evidence?: EvidenceItem[];
  citation_check?: CitationCheckResult;
  execution_time_ms?: number;
  created_at: string;
  attachments?: AppendixItem[];
  warnings?: string[];
}

export interface ChatSession {
  id: string;
  title: string;
  domain: string;
  retrieval_mode: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  last_message_preview?: string;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor?: string;
  has_more: boolean;
  total_count?: number;
}

export interface DocumentRecord {
  id: string;
  title: string;
  document_number?: string;
  document_type: string;
  domain: string;
  effective_from_date?: string;
  status: string;
  chunks_count: number;
  nodes_count: number;
  edges_count: number;
  articles_count?: number;
  clauses_count?: number;
  points_count?: number;
  created_at: string;
  updated_at: string;
  ast_tree_json?: any;
}

export interface OCRPagePreview {
  page_number: number;
  method: string;
  confidence?: number | null;
  char_count: number;
  preview_text: string;
}

export interface OCRPageDetail extends OCRPagePreview {
  text: string;
}

export interface OCRPreviewSummary {
  total_pages: number;
  processed_pages: number;
  text_pages: number;
  ocr_pages: number;
  empty_pages: number;
  avg_confidence?: number | null;
  heuristic_score?: number | null;
  articles_count?: number | null;
  warnings: string[];
  recent_pages: OCRPagePreview[];
}

export interface IngestionTask {
  result?: {
    document_ids?: string[];
    artifact_ids?: string[];
    warnings?: string[];
    reused_chunks?: number;
    ocr_summary?: Partial<OCRPreviewSummary>;
  };
  id: string;
  document_id?: string;
  file_name: string;
  document_type: string;
  status: 'pending' | 'parsing' | 'awaiting_review' | 'chunking' | 'embedding' | 'indexing' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  current_step: string;
  total_chunks: number;
  embedded_chunks: number;
  error_message?: string;
  ocr_preview?: OCRPreviewSummary | null;
  created_at: string;
}

export interface DocumentAST {
  document_id: string;
  title: string;
  ast_tree: ASTNode;
}

export interface AdminConfigValues {
  query_embedding_backend: 'local' | 'modal';
  anthropic_model: string;
  openai_model: string;
  embedding_model: string;
  embedding_backend: 'local' | 'modal';
  qdrant_url: string;
  qdrant_collection: string;
  llm_provider: LLMProvider;
  gemini_model: string;
  openrouter_model: string;
  openrouter_base_url: string;
  groq_model: string;
  groq_base_url: string;
  qwen_model: string;
  qwen_base_url: string;
  modal_app_name: string;
  neo4j_uri: string;
  redis_enabled: boolean;
  local_llm_base_url: string;
  local_llm_model: string;
  qdrant_timeout: number;
  collection_models: Record<string, string>;
  neo4j_user: string;
  neo4j_database: string;
  object_storage_provider: 's3' | 'r2';
  object_storage_endpoint_url: string;
  object_storage_region: string;
  object_storage_bucket: string;
  object_storage_prefix: string;
  embedding_cache_ttl: number;
  session_cache_ttl: number;
  ocr_model: 'vgg_transformer' | 'vgg_seq2seq';
  ocr_device: '' | 'cpu' | 'cuda' | 'cuda:0';
  ocr_dpi: number;
  ocr_beamsearch: boolean;
  ocr_semantic_chunking: boolean;
  ocr_semantic_model: string;
  max_upload_bytes: number;
}

export interface AdminSecretValues {
  gemini_api_key: string;
  openai_api_key: string;
  anthropic_api_key: string;
  openrouter_api_key: string;
  groq_api_key: string;
  qwen_api_key: string;
  local_llm_api_key: string;
  hf_token: string;
  qdrant_api_key: string;
  neo4j_password: string;
  object_storage_access_key_id: string;
  object_storage_secret_access_key: string;
  redis_url: string;
}

export type ConfigField = keyof (AdminConfigValues & AdminSecretValues);
export type ConfigService = 'llm' | 'embedding' | 'qdrant' | 'neo4j' | 'r2' | 'redis' | 'ocr';
export type ConfigSource = 'saved' | 'environment' | 'default';
export type AdminConfigUpdate = Partial<AdminConfigValues & AdminSecretValues> & {
  config_version?: number;
  reset_fields?: ConfigField[];
};

export interface AdminConfig extends AdminConfigValues {
  active_llm_profile_id: string | null;
  config_version: number;
  demo_mode: boolean;
  dataset_id: string;
  vector_db: string;
  available_collections: Record<string, string>;
  sources: Record<ConfigField, ConfigSource>;
  environment_values: Partial<AdminConfigValues>;
  environment_sources: Record<ConfigField, 'environment' | 'default'>;
  query_embedding_inherits: boolean;
  environment_query_embedding_inherits: boolean;
  environment_secret_configured: Record<keyof AdminSecretValues, boolean>;
  secret_configured: Record<keyof AdminSecretValues, boolean>;
  can_save: boolean;
  encryption_ready: boolean;
  configuration_error: string | null;
  postgres_status: string;
  postgres_endpoint: string;
  redis_endpoint: string;
  startup: { upload_dir: string; interim_dir: string; cors_origins: string[]; api_prefix: string };
}

export interface ConfigCheckResult {
  service: ConfigService;
  status: 'passed' | 'failed' | 'not_configured' | 'disabled';
  message: string;
  checked_at: string;
  latency_ms: number;
  details: { error?: string; dimensions?: number; points?: number; missing_fields?: string[] };
}

export type LLMProvider = 'gemini' | 'openai' | 'anthropic' | 'openrouter' | 'groq' | 'qwen' | 'local';
export interface LLMProfileInput {
  name: string;
  mode: 'cloud' | 'local';
  provider: LLMProvider;
  model: string;
  base_url: string;
  local_runtime: 'ollama' | 'lmstudio' | 'compatible';
  api_key_source: 'custom' | 'environment' | 'none';
  api_key?: string;
  profile_id?: string;
  copy_key_from?: string;
  config_version?: number;
  activate?: boolean;
}
export interface LLMProfile extends Omit<LLMProfileInput, 'api_key' | 'profile_id' | 'config_version' | 'activate'> {
  id: string;
  key_configured: boolean;
  read_only: boolean;
  verification: ConfigCheckResult | null;
}
export interface LLMProfilesResponse {
  profiles: LLMProfile[];
  active_profile_id: string;
  config_version: number;
  can_save: boolean;
  encryption_ready: boolean;
}

export interface PostgresConfigInput {
  mode: 'url' | 'fields';
  url?: string;
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  sslmode: 'require' | 'verify-full' | 'verify-ca' | 'prefer' | 'allow' | 'disable';
}
export interface PostgresConfig {
  configured: boolean;
  connection_status: string;
  host: string;
  port: number;
  database: string;
  username: string;
  sslmode: PostgresConfigInput['sslmode'];
  password_configured: boolean;
  source: 'environment' | 'env_file' | 'default';
  /** The process DATABASE_URL differs from the saved .env connection. */
  environment_override: boolean;
  pending_restart: boolean;
  pending_apply: boolean;
  can_apply: boolean;
  saved: boolean;
  message: string;
}
export interface PostgresCheckResult extends Omit<ConfigCheckResult, 'service' | 'status'> {
  status: 'passed' | 'failed' | 'not_configured';
}

export interface SystemStats {
  checked_at?: string | null;
  total_documents: number | null;
  total_chunks: number | null;
  total_nodes: number | null;
  total_edges: number | null;
  total_articles?: number | null;
  total_clauses?: number | null;
  total_points?: number | null;
  total_demuc?: number | null;
  total_pdf_docs?: number | null;
  vector_db_status: string;
  graph_db_status: string;
  redis_status: string;
  active_sessions_count: number | null;
}


export interface FileReference {
  artifact_id: string;
  file_name: string;
  format: string;
  view_url: string;
  download_url: string;
  available?: boolean;
}
export interface AppendixItem {
  appendix_id: string;
  document_id: string;
  document_number: string;
  number: string;
  title: string;
  kind: string;
  review_status: string;
  effect_status?: string;
  source_url?: string;
  view_url: string;
  text?: string;
  files: FileReference[];
  article_ids?: { document_id: string; article_number: string }[];
}
export interface AppendixList {
  total: number;
  items: AppendixItem[];
  documents: { document_id: string; document: string; download_status: string; extraction_status: string; appendices: number }[];
}
export interface RetrievedChunk extends Omit<EvidenceItem, 'score'> {
  score: number | null;
  rank?: number;
}
export interface GraphNode {
  id: string;
  title?: string;
  document_id?: string;
  article_number?: string;
  appendix_id?: string;
  appendix_number?: string;
}
export interface GraphEdge { source: string; target: string; type: string }
export interface GraphPath {
  seed_chunk_id?: string;
  appendix_id?: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}
export interface GraphResponse {
  status: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  warnings: string[];
}
export interface RetrievalResult {
  mode: string;
  llm_used: boolean;
  question: string;
  embedding: { model: string; backend: string; dimensions: number };
  collection: string;
  vector_hits: RetrievedChunk[];
  graph: { status: string; paths: GraphPath[]; provenance: GraphPath[]; cypher: string; parameters: Record<string, unknown> };
  appendices: (Partial<AppendixItem> & { appendix_id: string; chunks: RetrievedChunk[]; retrieved_via: string[]; eligible_for_retrieval: boolean })[];
  appendix_fetch_status: string;
  timings_ms: Record<string, number>;
  warnings: string[];
}
export interface HealthResponse {
  embedding?: { model: string; backend: string };
  demo_mode: boolean;
  config_version: number;
  data: { documents: number; appendices: number; chunks: number; needs_review: number };
  storage: { backend: string; r2: { connection: string }; r2_verified_files: number };
  qdrant: { connection: string; status?: string };
  neo4j: { connection: string; status?: string };
  postgres: { connection: string };
  redis: { connection: string };
}
export interface ASTNode {
  id: string;
  type: string;
  title: string;
  text?: string;
  article_number?: string | null;
  clause_number?: string | null;
  point_number?: string | null;
  children?: ASTNode[];
}
