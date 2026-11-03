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
  amendments: AmendmentItem[];
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
  created_at: string;
  updated_at: string;
  ast_tree_json?: any;
}

export interface IngestionTask {
  id: string;
  document_id?: string;
  file_name: string;
  document_type: string;
  status: 'pending' | 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'completed' | 'failed';
  progress: number;
  current_step: string;
  total_chunks: number;
  embedded_chunks: number;
  error_message?: string;
  created_at: string;
}

export interface DocumentAST {
  document_id: string;
  title: string;
  ast_tree: any;
}

export interface AdminConfig {
  embedding_model: string;
  embedding_backend: 'local' | 'modal';
  vector_db: string;
  qdrant_url: string;
  qdrant_collection: string;
  llm_provider: 'gemini' | 'anthropic' | 'openai';
  gemini_model: string;
  modal_app_name: string;
  neo4j_uri: string;
  redis_enabled: boolean;
}

export interface SystemStats {
  total_documents: number;
  total_chunks: number;
  total_nodes: number;
  total_edges: number;
  vector_db_status: string;
  graph_db_status: string;
  redis_status: string;
  active_sessions_count: number;
}

