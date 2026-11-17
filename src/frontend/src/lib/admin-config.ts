import type { AdminConfigUpdate, ConfigCheckResult, ConfigField, ConfigService } from './types';

export type ConfigCheckState = { checking?: boolean; result?: ConfigCheckResult; error?: string };

/** A current check or edit takes precedence over an earlier health probe. */
export function isConfigVerified(state: ConfigCheckState | undefined, connection?: string): boolean {
  if (state !== undefined) return !state.checking && !state.error && state.result?.status === 'passed';
  return connection === 'connected';
}

export interface ConfigFieldSpec {
  key: ConfigField;
  label: string;
  kind?: 'secret' | 'number' | 'checkbox' | 'select' | 'binding';
  options?: [string, string][];
  advanced?: boolean;
  provider?: string;
  optionalAuth?: boolean;
  hint?: string;
  scale?: number;
  min?: number;
}

export interface ConfigGroup {
  id: ConfigService;
  title: string;
  icon: string;
  hint: string;
  fields: ConfigFieldSpec[];
}

const backends: [string, string][] = [['modal', 'Modal cloud'], ['local', 'Local · CPU/GPU']];
export const configGroups: ConfigGroup[] = [
  { id: 'llm', title: 'Mô hình ngôn ngữ lớn (LLM)', icon: 'neurology',
    hint: 'Dùng dịch vụ cloud hoặc model đã chạy trên server local. Kiểm tra LLM sẽ gọi một phản hồi ngắn và sử dụng hạn mức API.', fields: [
      { key: 'llm_provider', label: 'Nơi chạy và nhà cung cấp', kind: 'select', options: [
        ['gemini', 'Cloud · Google Gemini'], ['openai', 'Cloud · OpenAI'],
        ['anthropic', 'Cloud · Anthropic'], ['openrouter', 'Cloud · OpenRouter'],
        ['groq', 'Cloud · Groq'], ['qwen', 'Cloud · Qwen / Alibaba Cloud'],
        ['local', 'Local · API tương thích OpenAI (Ollama…)']] },
      { key: 'gemini_model', label: 'Model Gemini', provider: 'gemini' },
      { key: 'gemini_api_key', label: 'Gemini API key', kind: 'secret', provider: 'gemini' },
      { key: 'openai_model', label: 'Model OpenAI', provider: 'openai' },
      { key: 'openai_api_key', label: 'OpenAI API key', kind: 'secret', provider: 'openai' },
      { key: 'anthropic_model', label: 'Model Anthropic', provider: 'anthropic' },
      { key: 'anthropic_api_key', label: 'Anthropic API key', kind: 'secret', provider: 'anthropic' },
      { key: 'openrouter_base_url', label: 'Địa chỉ API OpenRouter', provider: 'openrouter' },
      { key: 'openrouter_model', label: 'Model OpenRouter', provider: 'openrouter' },
      { key: 'openrouter_api_key', label: 'OpenRouter API key', kind: 'secret', provider: 'openrouter' },
      { key: 'groq_base_url', label: 'Địa chỉ API Groq', provider: 'groq' },
      { key: 'groq_model', label: 'Model Groq', provider: 'groq' },
      { key: 'groq_api_key', label: 'Groq API key', kind: 'secret', provider: 'groq' },
      { key: 'qwen_base_url', label: 'Địa chỉ API Qwen / Alibaba Cloud', provider: 'qwen' },
      { key: 'qwen_model', label: 'Model Qwen', provider: 'qwen' },
      { key: 'qwen_api_key', label: 'Qwen API key', kind: 'secret', provider: 'qwen' },
      { key: 'local_llm_base_url', label: 'Endpoint local (gồm /v1)', provider: 'local', hint: 'Địa chỉ được truy cập từ máy chạy backend.' },
      { key: 'local_llm_model', label: 'Model local đã cài', provider: 'local' },
      { key: 'local_llm_api_key', label: 'API key local (nếu có)', kind: 'secret', provider: 'local', optionalAuth: true },
    ] },
  { id: 'embedding', title: 'Embedding và nguồn tính toán', icon: 'hub',
    hint: 'Model phải khớp với collection đã lập chỉ mục. Kiểm tra tạo vector thử; khi lưu sẽ đối chiếu collection liên quan.', fields: [
      { key: 'embedding_model', label: 'Model embedding' },
      { key: 'embedding_backend', label: 'Tính vector khi nạp dữ liệu', kind: 'select', options: backends },
      { key: 'query_embedding_backend', label: 'Tính vector khi truy vấn', kind: 'select', options: backends },
      { key: 'modal_app_name', label: 'Ứng dụng Modal đã triển khai' },
      { key: 'hf_token', label: 'Hugging Face token (nếu cần)', kind: 'secret', advanced: true, optionalAuth: true,
        hint: 'Dùng cho model trên máy backend/OCR. Model trên Modal dùng quyền đã thiết lập ở Modal.' },
    ] },
  { id: 'qdrant', title: 'Cơ sở dữ liệu vector · Qdrant', icon: 'database',
    hint: 'Nhập URL local hoặc cloud đang chạy, rồi chọn collection có sẵn. Trang này không tạo collection hoặc nạp dữ liệu.', fields: [
      { key: 'qdrant_url', label: 'Qdrant URL' },
      { key: 'qdrant_collection', label: 'Collection' },
      { key: 'qdrant_api_key', label: 'Qdrant API key (nếu có)', kind: 'secret', optionalAuth: true },
      { key: 'qdrant_timeout', label: 'Timeout truy vấn (giây)', kind: 'number', min: 1, advanced: true },
      { key: 'collection_models', label: 'Model đã dùng để lập chỉ mục collection đang chọn', kind: 'binding', advanced: true,
        hint: 'Khai báo đúng model thực tế. Hệ thống kiểm tra số chiều; thay khai báo không chuyển đổi vector đã có.' },
    ] },
  { id: 'neo4j', title: 'Đồ thị tri thức · Neo4j', icon: 'account_tree',
    hint: 'Kết nối đến Neo4j local hoặc cloud bằng URI và thông tin xác thực của database có sẵn.', fields: [
      { key: 'neo4j_uri', label: 'Neo4j URI' }, { key: 'neo4j_database', label: 'Database' },
      { key: 'neo4j_user', label: 'Tên người dùng' }, { key: 'neo4j_password', label: 'Mật khẩu Neo4j', kind: 'secret' },
    ] },
  { id: 'r2', title: 'Lưu trữ file · Cloudflare R2', icon: 'cloud',
    hint: 'Kiểm tra chỉ đọc thông tin bucket. Đổi bucket không chuyển các file đang lưu ở bucket cũ.', fields: [
      { key: 'object_storage_endpoint_url', label: 'R2 endpoint HTTPS' }, { key: 'object_storage_bucket', label: 'Bucket' },
      { key: 'object_storage_access_key_id', label: 'Access key ID', kind: 'secret' },
      { key: 'object_storage_secret_access_key', label: 'Secret access key', kind: 'secret' },
      { key: 'object_storage_region', label: 'Region', advanced: true },
      { key: 'object_storage_prefix', label: 'Prefix lưu trữ', advanced: true },
      { key: 'object_storage_provider', label: 'Giao thức lưu trữ', kind: 'select', advanced: true,
        options: [['s3', 'R2 · API S3'], ['r2', 'Cloudflare R2']] },
    ] },
  { id: 'redis', title: 'Bộ nhớ đệm · Redis', icon: 'cached',
    hint: 'Redis là tùy chọn. URL có thể chứa mật khẩu nên được lưu và xử lý như thông tin bí mật.', fields: [
      { key: 'redis_enabled', label: 'Bật Redis cache', kind: 'checkbox' },
      { key: 'redis_url', label: 'Redis URL (redis:// hoặc rediss://)', kind: 'secret' },
      { key: 'embedding_cache_ttl', label: 'TTL cache embedding (giây)', kind: 'number', min: 1, advanced: true },
      { key: 'session_cache_ttl', label: 'TTL cache phiên (giây)', kind: 'number', min: 1, advanced: true },
    ] },
  { id: 'ocr', title: 'OCR và tài liệu tải lên', icon: 'document_scanner',
    hint: 'Áp dụng cho lần xử lý tài liệu tiếp theo. Kiểm tra dependency, thiết bị và file model hiện có; không tải model trong bước kiểm tra.', fields: [
      { key: 'ocr_model', label: 'Model VietOCR', kind: 'select', options: [
        ['vgg_transformer', 'VGG Transformer'], ['vgg_seq2seq', 'VGG Seq2Seq']] },
      { key: 'ocr_device', label: 'Thiết bị OCR', kind: 'select', options: [
        ['', 'Tự động'], ['cpu', 'CPU'], ['cuda:0', 'GPU · CUDA:0'], ['cuda', 'GPU · CUDA']] },
      { key: 'ocr_dpi', label: 'DPI (72–600)', kind: 'number', min: 72 },
      { key: 'max_upload_bytes', label: 'Dung lượng upload tối đa (MiB)', kind: 'number', min: 1, scale: 1024 * 1024 },
      { key: 'ocr_beamsearch', label: 'Bật beam search', kind: 'checkbox', advanced: true },
      { key: 'ocr_semantic_chunking', label: 'Bật semantic chunking', kind: 'checkbox', advanced: true },
      { key: 'ocr_semantic_model', label: 'Model semantic chunking', advanced: true },
    ] },
];

export type ConfigDraft = Partial<Record<ConfigField, string | number | boolean | Record<string, string>>>;

export function buildConfigUpdate(version: number, draft: ConfigDraft, resets: ConfigField[], service?: ConfigService): AdminConfigUpdate {
  const fields = service ? configGroups.find(group => group.id === service)!.fields.map(field => field.key) : undefined;
  return {
    ...Object.fromEntries(Object.entries(draft).filter(([key]) => !fields || fields.includes(key as ConfigField))),
    reset_fields: resets.filter(key => !fields || fields.includes(key)),
    config_version: version,
  };
}

export function affectedGroups(field: ConfigField): ConfigService[] {
  const groups = configGroups.filter(group => group.fields.some(item => item.key === field)).map(group => group.id);
  if (['embedding_model', 'embedding_backend', 'query_embedding_backend', 'hf_token'].includes(field)) groups.push('qdrant');
  if (['qdrant_collection', 'collection_models', 'qdrant_url'].includes(field)) groups.push('embedding');
  if (field === 'hf_token') groups.push('ocr');
  return Array.from(new Set(groups));
}

/** A response can confirm only the draft revision that was actually checked. */
export function createConfigRequestTracker() {
  let sequence = 0;
  const revisions = Object.fromEntries(configGroups.map(group => [group.id, 0])) as Record<ConfigService, number>;
  return {
    begin(service: ConfigService) { return revisions[service] = ++sequence; },
    isCurrent(service: ConfigService, revision: number) { return revisions[service] === revision; },
    invalidate(field: ConfigField) {
      const groups = affectedGroups(field);
      groups.forEach(group => revisions[group] = ++sequence);
      return groups;
    },
    invalidateAll() { configGroups.forEach(group => revisions[group.id] = ++sequence); },
  };
}
