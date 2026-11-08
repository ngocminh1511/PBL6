import axios from 'axios';
import type { AppendixItem, AppendixList, RetrievalResult, HealthResponse, GraphResponse } from './types';

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
  DocumentAST, IngestionTask, AdminConfig, SystemStats
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
  async listDocuments(domain?: string, search?: string, cursor?: string, limit: number = 10): Promise<CursorPage<DocumentRecord>> {
    const res = await apiClient.get('/documents/list', { params: { domain, search, cursor, limit } });
    return res.data;
  },

  async getDocumentAST(documentId: string): Promise<DocumentAST> {
    const res = await apiClient.get(`/documents/${documentId}/ast`);
    return res.data;
  },

  async uploadDocument(file: File, documentType: string = 'pdf', domain: string = 'lao_dong', deMucId?: string): Promise<{ task_id: string; message: string; document_id?: string }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    formData.append('domain', domain);
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

  // ================= ADMIN =================
  async getAdminConfig(): Promise<AdminConfig> {
    const res = await apiClient.get('/admin/config');
    return res.data;
  },

  async updateAdminConfig(config: Partial<AdminConfig>): Promise<AdminConfig> {
    const res = await apiClient.put('/admin/config', config);
    return res.data;
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

