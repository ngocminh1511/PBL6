import { create } from 'zustand';
import { DocumentRecord, IngestionTask } from '../lib/types';
import { api } from '../lib/api';

interface DocumentState {
  documents: DocumentRecord[];
  isLoading: boolean;
  searchQuery: string;
  selectedDomain: string;
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
  selectDocument: (docId: string) => Promise<void>;
  uploadDocument: (file: File, docType: string, domain: string) => Promise<string>;
  pollTaskProgress: (taskId: string) => void;
  setUploadModalOpen: (open: boolean) => void;
}

export const useDocumentStore = create<DocumentState>((set, get) => ({
  documents: [],
  isLoading: false,
  searchQuery: '',
  selectedDomain: 'all',
  nextCursor: null,
  hasMore: false,
  totalDocuments: 42,

  selectedDocId: 'BLLD2019',
  selectedDocAST: null,
  activeTask: null,
  isUploadModalOpen: false,

  fetchDocuments: async (cursor) => {
    set({ isLoading: true });
    try {
      const data = await api.listDocuments(
        get().selectedDomain,
        get().searchQuery,
        cursor
      );
      set((state) => ({
        documents: cursor ? [...state.documents, ...data.items] : data.items,
        nextCursor: data.next_cursor || null,
        hasMore: data.has_more,
        totalDocuments: data.total_count || 42,
        isLoading: false,
      }));
    } catch (e) {
      console.error('Failed to fetch documents:', e);
      set({ isLoading: false });
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

  selectDocument: async (docId: string) => {
    set({ selectedDocId: docId });
    try {
      const ast = await api.getDocumentAST(docId);
      set({ selectedDocAST: ast.ast_tree });
    } catch (e) {
      console.error('Failed to get AST:', e);
    }
  },

  uploadDocument: async (file, docType, domain) => {
    try {
      const res = await api.uploadDocument(file, docType, domain);
      get().pollTaskProgress(res.task_id);
      return res.task_id;
    } catch (e) {
      console.error('Failed to upload document:', e);
      throw e;
    }
  },

  pollTaskProgress: (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const task = await api.getTaskProgress(taskId);
        set({ activeTask: task });

        if (task.status === 'completed' || task.status === 'failed') {
          clearInterval(interval);
          get().fetchDocuments();
        }
      } catch (e) {
        clearInterval(interval);
      }
    }, 1500);
  },

  setUploadModalOpen: (open) => set({ isUploadModalOpen: open }),
}));

