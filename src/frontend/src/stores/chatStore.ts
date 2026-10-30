import { create } from 'zustand';
import { ChatSession, ChatMessage, EvidenceItem, RetrievalMode } from '../lib/types';
import { api } from '../lib/api';

interface ChatState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  messages: ChatMessage[];
  isLoading: boolean;
  isSending: boolean;
  nextCursor: string | null;
  hasMore: boolean;
  totalSessions: number;

  // Selected filters
  selectedDomain: string;
  selectedRetrievalMode: RetrievalMode;

  // Inspector Column State
  inspectorTab: 'tab-hierarchy' | 'tab-graph' | 'tab-rerank';
  selectedCitation: string | null;
  selectedEvidences: EvidenceItem[];

  // Actions
  fetchSessions: (cursor?: string) => Promise<void>;
  createSession: (title?: string) => Promise<string>;
  selectSession: (sessionId: string) => Promise<void>;
  sendMessage: (question: string) => Promise<void>;
  setSelectedDomain: (domain: string) => void;
  setSelectedRetrievalMode: (mode: RetrievalMode) => void;
  setInspectorTab: (tab: 'tab-hierarchy' | 'tab-graph' | 'tab-rerank') => void;
  setSelectedCitation: (citation: string | null) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  messages: [],
  isLoading: false,
  isSending: false,
  nextCursor: null,
  hasMore: false,
  totalSessions: 0,

  selectedDomain: 'all',
  selectedRetrievalMode: 'hybrid',

  inspectorTab: 'tab-hierarchy',
  selectedCitation: 'Điều 35, Khoản 1, Điểm a',
  selectedEvidences: [],

  fetchSessions: async (cursor) => {
    set({ isLoading: true });
    try {
      const data = await api.listSessions(cursor);
      set((state) => ({
        sessions: cursor ? [...state.sessions, ...data.items] : data.items,
        nextCursor: data.next_cursor || null,
        hasMore: data.has_more,
        totalSessions: data.total_count || 0,
        isLoading: false,
      }));

      // Auto-select first session if none selected
      if (!get().activeSessionId && data.items.length > 0) {
        get().selectSession(data.items[0].id);
      }
    } catch (e) {
      console.error('Failed to fetch sessions:', e);
      set({ isLoading: false });
    }
  },

  createSession: async (title) => {
    try {
      const session = await api.createSession(
        title || 'Phiên tra cứu mới',
        get().selectedDomain,
        get().selectedRetrievalMode
      );
      set((state) => ({
        sessions: [session, ...state.sessions],
        activeSessionId: session.id,
        messages: [],
        totalSessions: state.totalSessions + 1,
      }));
      return session.id;
    } catch (e) {
      console.error('Failed to create session:', e);
      return '';
    }
  },

  selectSession: async (sessionId: string) => {
    set({ activeSessionId: sessionId, isLoading: true });
    try {
      const data = await api.getSession(sessionId);
      set({
        messages: data.messages,
        isLoading: false,
      });

      // Update inspector evidence with last message's evidence
      const lastAsst = [...data.messages].reverse().find((m) => m.role === 'assistant');
      if (lastAsst?.legal_evidence) {
        set({ selectedEvidences: lastAsst.legal_evidence });
      }
    } catch (e) {
      console.error('Failed to select session:', e);
      set({ isLoading: false });
    }
  },

  sendMessage: async (question: string) => {
    if (!question.trim()) return;
    const { activeSessionId, selectedDomain, selectedRetrievalMode, messages } = get();

    // Optimistic user message
    const tempUserMsg: ChatMessage = {
      id: `temp_${Date.now()}`,
      session_id: activeSessionId || '',
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    };

    set({
      messages: [...messages, tempUserMsg],
      isSending: true,
    });

    try {
      const res = await api.ask({
        session_id: activeSessionId || undefined,
        question,
        domain: selectedDomain,
        retrieval_mode: selectedRetrievalMode,
      });

      // Replace optimistic message and append assistant message
      set((state) => {
        const updatedMsgs = state.messages.filter((m) => m.id !== tempUserMsg.id);
        return {
          messages: [...updatedMsgs, res.user_message, res.assistant_message],
          activeSessionId: res.session_id,
          selectedEvidences: res.assistant_message.legal_evidence || [],
          isSending: false,
        };
      });

      // Refresh session list preview
      get().fetchSessions();
    } catch (e) {
      console.error('Failed to send message:', e);
      set({ isSending: false });
    }
  },

  setSelectedDomain: (domain) => set({ selectedDomain: domain }),
  setSelectedRetrievalMode: (mode) => set({ selectedRetrievalMode: mode }),
  setInspectorTab: (tab) => set({ inspectorTab: tab }),
  setSelectedCitation: (citation) => set({ selectedCitation: citation }),
}));

