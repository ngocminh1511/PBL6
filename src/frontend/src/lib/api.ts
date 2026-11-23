import axios from 'axios';
import type { AppendixItem, AppendixList, RetrievalResult, HealthResponse, GraphResponse, OCRPageDetail, TokenUsage } from './types';

export function errorTokenUsage(error: unknown): TokenUsage | null {
  if (!axios.isAxiosError(error)) return null;
  const usage = error.response?.data?.token_usage;
  return usage && Array.isArray(usage.calls) && Array.isArray(usage.executed_stages)
    && ['complete', 'partial', 'unavailable'].includes(usage.status) ? usage : null;
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ');
    return error.response ? 'Lỗi HTTP ' + error.response.status : 'Không kết nối được backend.';
  }
  return error instanceof Error ? error.message : 'Thao tác chưa hoàn tất.';
}

import {
  ChatSession, ChatMessage, CursorPage, DocumentRecord,
  DocumentAST, IngestionTask, AdminConfig, AdminConfigUpdate, ConfigService, ConfigCheckResult, SystemStats,
  LLMProfileInput, LLMProfilesResponse, PostgresConfigInput, PostgresConfig, PostgresCheckResult
} from './types';

const API_BASE = '/api';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token from localStorage if present
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('lexgraph_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export const api = {
  async listAppendices(params: Record<string, string | number>): Promise<AppendixList> {
    return (await apiClient.get('/appendices', { params })).data;
  },
  async getAppendix(id: string): Promise<AppendixItem> {
    return (await apiClient.get('/appendices/' + encodeURIComponent(id))).data;
  },
  async inspect(question: string, top_k: number = 8): Promise<RetrievalResult> {
    return (await apiClient.post('/retrieve', { question, top_k })).data;
  },
  async health(probe: boolean = false): Promise<HealthResponse> {
    return (await apiClient.get('/health', { params: { probe } })).data;
  },
  async getGraph(documentId: string, articleNumber?: string): Promise<GraphResponse> {
    return (await apiClient.get('/documents/' + encodeURIComponent(documentId) + '/graph',
      { params: { article_number: articleNumber } })).data;
  },
  // ================= CHAT =================
  async listSessions(cursor?: string, limit: number = 15): Promise<CursorPage<ChatSession>> {
    const res = await apiClient.get('/chat/sessions', { params: { cursor, limit } });
    return res.data;
  },

  async createSession(title?: string, domain?: string, retrieval_mode?: string): Promise<ChatSession> {
    const res = await apiClient.post('/chat/sessions', { title, domain, retrieval_mode });
    return res.data;
  },

  async getSession(sessionId: string): Promise<{ session: ChatSession; messages: ChatMessage[] }> {
    const res = await apiClient.get(`/chat/sessions/${sessionId}`);
    return res.data;
  },

  async updateSession(sessionId: string, data: { title?: string }): Promise<ChatSession> {
    const res = await apiClient.patch(`/chat/sessions/${sessionId}`, data);
    return res.data;
  },

  async deleteSession(sessionId: string): Promise<{ ok: boolean; session_id: string }> {
    const res = await apiClient.delete(`/chat/sessions/${sessionId}`);
    return res.data;
  },

  async ask(params: {
    session_id?: string;
    question: string;
    domain?: string;
    retrieval_mode?: string;
    top_k?: number;
    rerank_top_n?: number;
  }): Promise<{ session_id: string; user_message: ChatMessage; assistant_message: ChatMessage }> {
    const res = await apiClient.post('/chat/ask', params);
    return res.data;
  },

  // ================= DOCUMENTS =================
  async listDocuments(domain?: string, search?: string, cursor?: string, limit: number = 10, document_type?: string): Promise<CursorPage<DocumentRecord>> {
    const res = await apiClient.get('/documents/list', { params: { domain, search, cursor, limit, document_type } });
    return res.data;
  },

  async getDocumentAST(documentId: string): Promise<DocumentAST> {
    const res = await apiClient.get(`/documents/${documentId}/ast`);
    return res.data;
  },

  async updateDocumentDomain(documentId: string, domain: 'lao_dong' | 'khac'): Promise<DocumentRecord> {
    const res = await apiClient.patch(`/documents/${encodeURIComponent(documentId)}`, { domain });
    return res.data;
  },

  async uploadDocument(file: File, documentType: string = 'pdf', domain: string = 'lao_dong', deMucId?: string, pauseForReview: boolean = true): Promise<{ task_id: string; message: string; document_id?: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    formData.append('domain', domain);
    formData.append('pause_for_review', String(pauseForReview));
    if (deMucId) formData.append('de_muc_id', deMucId);

    const res = await apiClient.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  async getTaskProgress(taskId: string): Promise<IngestionTask> {
    const res = await apiClient.get(`/documents/tasks/${taskId}/progress`);
    return res.data;
  },

  async getTaskOCRPage(taskId: string, pageNumber: number): Promise<OCRPageDetail> {
    const res = await apiClient.get(`/documents/tasks/${taskId}/ocr-page/${pageNumber}`);
    return res.data;
  },

  async updateTaskOCRPage(taskId: string, pageNumber: number, text: string): Promise<OCRPageDetail> {
    const res = await apiClient.put(`/documents/tasks/${taskId}/ocr-page/${pageNumber}`, { text });
    return res.data;
  },

  getTaskPdfPageUrl(taskId: string, pageNumber: number): string {
    return `/api/documents/tasks/${encodeURIComponent(taskId)}/pdf-page/${pageNumber}`;
  },

  async confirmTaskReview(taskId: string): Promise<IngestionTask> {
    const res = await apiClient.post(`/documents/tasks/${taskId}/confirm`);
    return res.data;
  },

  async cancelTask(taskId: string): Promise<IngestionTask> {
    const res = await apiClient.post(`/documents/tasks/${taskId}/cancel`);
    return res.data;
  },

  // ================= ADMIN =================
  async getAdminConfig(): Promise<AdminConfig> {
    const res = await apiClient.get('/admin/config');
    return res.data;
  },

  async updateAdminConfig(config: AdminConfigUpdate): Promise<AdminConfig> {
    const res = await apiClient.put('/admin/config', config);
    return res.data;
  },

  async checkAdminConfig(service: ConfigService, overrides: AdminConfigUpdate): Promise<ConfigCheckResult> {
    return (await apiClient.post('/admin/config/check', { service, overrides }, { timeout: 65000 })).data;
  },

  async listLLMModels(overrides: AdminConfigUpdate): Promise<{ provider: string; models: string[] }> {
    return (await apiClient.post('/admin/llm/models', { overrides }, { timeout: 65000 })).data;
  },

  async listLLMProfiles(): Promise<LLMProfilesResponse> {
    return (await apiClient.get('/admin/llm/profiles')).data;
  },
  async getPostgresConfig(): Promise<PostgresConfig> {
    return (await apiClient.get('/admin/postgres')).data;
  },
  async checkPostgresConfig(config: PostgresConfigInput): Promise<PostgresCheckResult> {
    return (await apiClient.post('/admin/postgres/check', config, { timeout: 20000 })).data;
  },
  async savePostgresConfig(config: PostgresConfigInput): Promise<PostgresConfig> {
    return (await apiClient.put('/admin/postgres', config, { timeout: 20000 })).data;
  },
  async applyPostgresConfig(): Promise<PostgresConfig> {
    return (await apiClient.post('/admin/postgres/apply', {}, { timeout: 65000 })).data;
  },
  async saveLLMProfile(profile: LLMProfileInput, id?: string): Promise<LLMProfilesResponse> {
    return (await apiClient.request({ method: id ? 'PUT' : 'POST',
      url: '/admin/llm/profiles' + (id ? '/' + encodeURIComponent(id) : ''), data: profile, timeout: 65000 })).data;
  },
  async checkLLMProfile(profile: LLMProfileInput): Promise<ConfigCheckResult> {
    return (await apiClient.post('/admin/llm/profiles/check', profile, { timeout: 65000 })).data;
  },
  async listProfileModels(profile: LLMProfileInput): Promise<{ provider: string; models: string[] }> {
    return (await apiClient.post('/admin/llm/profiles/models', profile, { timeout: 65000 })).data;
  },
  async activateLLMProfile(id: string, config_version: number): Promise<LLMProfilesResponse> {
    return (await apiClient.post('/admin/llm/profiles/' + encodeURIComponent(id) + '/activate', { config_version }, { timeout: 65000 })).data;
  },
  async deleteLLMProfile(id: string, config_version: number): Promise<LLMProfilesResponse> {
    return (await apiClient.delete('/admin/llm/profiles/' + encodeURIComponent(id), { data: { config_version } })).data;
  },

  async getSystemStats(): Promise<SystemStats> {
    const res = await apiClient.get('/admin/system-stats');
    return res.data;
  },

  async flushCache(): Promise<{ message: string }> {
    const res = await apiClient.post('/admin/cache/flush');
    return res.data;
  },
};

