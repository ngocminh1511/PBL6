import { create } from 'zustand';
import { DocumentRecord, IngestionTask } from '../lib/types';
import { api, errorMessage } from '../lib/api';

interface DocumentState {
  documents: DocumentRecord[];
  error: string | null;
  isLoading: boolean;
  searchQuery: string;
  selectedDomain: string;
  selectedDocType: string;
  nextCursor: string | null;
  hasMore: boolean;
  totalDocuments: number;

  selectedDocId: string;
  selectedDocAST: any | null;
  activeTask: IngestionTask | null;
  isUploadModalOpen: boolean;

  fetchDocuments: (cursor?: string) => Promise<void>;
  setSearchQuery: (query: string) => void;
  setSelectedDomain: (domain: string) => void;
  setSelectedDocType: (docType: string) => void;
  selectDocument: (docId: string) => Promise<void>;
  updateDocumentDomain: (docId: string, domain: 'lao_dong' | 'khac') => Promise<void>;
  uploadDocument: (file: File, docType: string, domain: string, pauseForReview?: boolean) => Promise<string>;
  pollTaskProgress: (taskId: string) => void;
  confirmTaskReview: (taskId: string) => Promise<void>;
  cancelTask: (taskId: string) => Promise<void>;
  setUploadModalOpen: (open: boolean) => void;
}

export const useDocumentStore = create<DocumentState>((set, get) => ({
  documents: [],
  error: null,
  isLoading: false,
  searchQuery: '',
  selectedDomain: 'all',
  selectedDocType: 'all',
  nextCursor: null,
  hasMore: false,
  totalDocuments: 0,

  selectedDocId: '',
  selectedDocAST: null,
  activeTask: null,
  isUploadModalOpen: false,

  fetchDocuments: async (cursor) => {
    set({ isLoading: true, error: null });
    try {
      const data = await api.listDocuments(
        get().selectedDomain,
        get().searchQuery,
        cursor,
        10,
        get().selectedDocType
      );
      set((state) => ({
        documents: cursor ? [...state.documents, ...data.items] : data.items,
        nextCursor: data.next_cursor || null,
        hasMore: data.has_more,
        totalDocuments: data.total_count ?? 0,
        isLoading: false,
      }));
    } catch (e) {
      console.error('Failed to fetch documents:', e);
      set({ isLoading: false, error: errorMessage(e) });
    }
  },

  setSearchQuery: (query) => {
    set({ searchQuery: query });
    get().fetchDocuments();
  },

  setSelectedDomain: (domain) => {
    set({ selectedDomain: domain });
    get().fetchDocuments();
  },

  setSelectedDocType: (docType) => {
    set({ selectedDocType: docType });
    get().fetchDocuments();
  },

  selectDocument: async (docId: string) => {
    set({ selectedDocId: docId, selectedDocAST: null, error: null });
    try {
      const ast = await api.getDocumentAST(docId);
      set({ selectedDocAST: ast.ast_tree });
    } catch (e) {
      set({ error: errorMessage(e) });
    }
  },

  updateDocumentDomain: async (docId: string, domain: 'lao_dong' | 'khac') => {
    set({ error: null });
    try {
      const updated = await api.updateDocumentDomain(docId, domain);
      set((state) => ({
        documents: state.documents.map((d) => (d.id === docId ? { ...d, domain: updated.domain } : d)),
      }));
      await get().fetchDocuments();
    } catch (e) {
      set({ error: errorMessage(e) });
    }
  },

  uploadDocument: async (file, docType, domain, pauseForReview = true) => {
    try {
      const res = await api.uploadDocument(file, docType, domain, undefined, pauseForReview);
      get().pollTaskProgress(res.task_id);
      return res.task_id;
    } catch (e) {
      console.error('Failed to upload document:', e);
      throw e;
    }
  },

  pollTaskProgress: (taskId: string) => {
    const check = async (interval?: ReturnType<typeof setInterval>) => {
      try {
        const task = await api.getTaskProgress(taskId);
        set({ activeTask: task });

        if (
          task.status === 'completed' ||
          task.status === 'failed' ||
          task.status === 'cancelled' ||
          task.status === 'awaiting_review'
        ) {
          if (interval) clearInterval(interval);
          if (task.status === 'completed') {
            await get().fetchDocuments();
            const newId = task.document_id || task.result?.document_ids?.[0];
            if (newId) {
              if (!get().documents.some((d) => d.id === newId) && get().selectedDomain !== 'all') {
                set({ selectedDomain: 'all', selectedDocType: 'all' });
                await get().fetchDocuments();
              }
              await get().selectDocument(newId);
            }
          }
          return true;
        }
      } catch (e) {
        set({ error: errorMessage(e) });
        if (interval) clearInterval(interval);
        return true;
      }
      return false;
    };
    void check().then((done) => {
      if (done) return;
      const interval = setInterval(() => {
        void check(interval);
      }, 1000);
    });
  },

  confirmTaskReview: async (taskId: string) => {
    set({ error: null });
    try {
      const updated = await api.confirmTaskReview(taskId);
      set({ activeTask: updated });
      get().pollTaskProgress(taskId);
    } catch (e) {
      set({ error: errorMessage(e) });
      throw e;
    }
  },

  cancelTask: async (taskId: string) => {
    set({ error: null });
    try {
      const updated = await api.cancelTask(taskId);
      set({ activeTask: updated });
    } catch (e) {
      set({ error: errorMessage(e) });
    }
  },

  setUploadModalOpen: (open) => set({ isUploadModalOpen: open }),
}));

