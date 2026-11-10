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
  created_at: string;
  updated_at: string;
  ast_tree_json?: any;
}

export interface IngestionTask {
  result?: { document_ids: string[]; artifact_ids: string[]; warnings: string[]; reused_chunks?: number };
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
  ast_tree: ASTNode;
}

export interface AdminConfig {
  config_version: number;
  demo_mode: boolean;
  dataset_id: string;
  query_embedding_backend: 'local' | 'modal';
  available_collections: Record<string, string>;
  anthropic_model: string;
  openai_model: string;
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
  total_documents: number | null;
  total_chunks: number | null;
  total_nodes: number | null;
  total_edges: number | null;
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
