import { create } from 'zustand';
import { ChatSession, ChatMessage, EvidenceItem, RetrievalMode } from '../lib/types';
import { api, errorMessage } from '../lib/api';

interface ChatState {
  sessions: ChatSession[];
  error: string | null;
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
  /** Bumped on every citation click, so choosing the same citation again re-focuses the tree. */
  focusTick: number;
  selectedEvidences: EvidenceItem[];
  pinnedSessionIds: string[];

  // Actions
  fetchSessions: (cursor?: string) => Promise<void>;
  createSession: (title?: string) => Promise<string>;
  selectSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, newTitle: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  togglePinSession: (sessionId: string) => void;
  sendMessage: (question: string) => Promise<void>;
  setSelectedDomain: (domain: string) => void;
  setSelectedRetrievalMode: (mode: RetrievalMode) => void;
  setInspectorTab: (tab: 'tab-hierarchy' | 'tab-graph' | 'tab-rerank') => void;
  setSelectedCitation: (citation: string | null) => void;
}

const getStoredPinned = (): string[] => {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem('lexgraph_pinned_sessions');
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  error: null,
  activeSessionId: null,
  messages: [],
  isLoading: false,
  isSending: false,
  nextCursor: null,
  hasMore: false,
  totalSessions: 0,
  pinnedSessionIds: getStoredPinned(),

  selectedDomain: 'all',
  selectedRetrievalMode: 'hybrid',

  inspectorTab: 'tab-hierarchy',
  selectedCitation: 'Điều 35, Khoản 1, Điểm a',
  focusTick: 0,
  selectedEvidences: [],

  fetchSessions: async (cursor) => {
    set({ isLoading: true, error: null });
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
      set({ isLoading: false, error: errorMessage(e) });
    }
  },

  createSession: async (_title?: string) => {
    set({
      activeSessionId: null,
      messages: [],
      selectedEvidences: [],
      selectedCitation: null,
      error: null,
    });
    return '';
  },

  selectSession: async (sessionId: string) => {
    set({ activeSessionId: sessionId, isLoading: true, selectedEvidences: [], selectedCitation: null, error: null });
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
      set({ isLoading: false, error: errorMessage(e) });
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
      error: null,
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
      set(state => ({ isSending: false, error: errorMessage(e), messages: state.messages.filter(message => message.id !== tempUserMsg.id) }));
    }
  },

  setSelectedDomain: (domain) => set({ selectedDomain: domain }),
  setSelectedRetrievalMode: (mode) => set({ selectedRetrievalMode: mode }),
  setInspectorTab: (tab) => set({ inspectorTab: tab }),
  setSelectedCitation: (citation) => set(state => ({ selectedCitation: citation, focusTick: state.focusTick + 1 })),

  renameSession: async (sessionId: string, newTitle: string) => {
    if (!newTitle.trim()) return;
    try {
      const updated = await api.updateSession(sessionId, { title: newTitle.trim() });
      set((state) => ({
        sessions: state.sessions.map((s) => (s.id === sessionId ? { ...s, title: updated.title } : s)),
      }));
    } catch (e) {
      console.error('Failed to rename session:', e);
      set({ error: errorMessage(e) });
    }
  },

  deleteSession: async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId);
      const { sessions, activeSessionId, pinnedSessionIds } = get();
      const remaining = sessions.filter((s) => s.id !== sessionId);
      const remainingPinned = pinnedSessionIds.filter((id) => id !== sessionId);
      try {
        localStorage.setItem('lexgraph_pinned_sessions', JSON.stringify(remainingPinned));
      } catch {}

      const nextActiveId = activeSessionId === sessionId
        ? (remaining.length > 0 ? remaining[0].id : null)
        : activeSessionId;

      set({
        sessions: remaining,
        pinnedSessionIds: remainingPinned,
        activeSessionId: nextActiveId,
        totalSessions: Math.max(0, get().totalSessions - 1),
      });

      if (nextActiveId && nextActiveId !== activeSessionId) {
        get().selectSession(nextActiveId);
      } else if (!nextActiveId) {
        set({ messages: [], selectedEvidences: [] });
      }
    } catch (e) {
      console.error('Failed to delete session:', e);
      set({ error: errorMessage(e) });
    }
  },

  togglePinSession: (sessionId: string) => {
    const { pinnedSessionIds } = get();
    const isPinned = pinnedSessionIds.includes(sessionId);
    const updated = isPinned
      ? pinnedSessionIds.filter((id) => id !== sessionId)
      : [sessionId, ...pinnedSessionIds];
    try {
      localStorage.setItem('lexgraph_pinned_sessions', JSON.stringify(updated));
    } catch {}
    set({ pinnedSessionIds: updated });
  },
}));

