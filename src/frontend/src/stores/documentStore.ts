import { create } from 'zustand';
import { DocumentRecord, DocumentRemoval, IngestionTask, IngestionTaskSummary } from '../lib/types';
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
  tasks: IngestionTaskSummary[];
  tasksTotal: number;
  tasksLoading: boolean;
  tasksError: string | null;

  fetchDocuments: (cursor?: string) => Promise<void>;
  setSearchQuery: (query: string) => void;
  setSelectedDomain: (domain: string) => void;
  setSelectedDocType: (docType: string) => void;
  selectDocument: (docId: string) => Promise<void>;
  updateDocumentDomain: (docId: string, domain: 'lao_dong' | 'khac') => Promise<void>;
  removeDocument: (docId: string) => Promise<DocumentRemoval>;
  uploadDocument: (file: File, docType: string, domain: string, pauseForReview?: boolean) => Promise<string>;
  pollTaskProgress: (taskId: string) => void;
  confirmTaskReview: (taskId: string, prune?: string[]) => Promise<void>;
  cancelTask: (taskId: string) => Promise<void>;
  fetchTasks: () => Promise<void>;
  openTask: (taskId: string) => Promise<void>;
  reopenTask: (taskId: string) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
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
  tasks: [],
  tasksTotal: 0,
  tasksLoading: false,
  tasksError: null,

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
      if (get().selectedDocId === docId) set({ selectedDocAST: ast.ast_tree });
    } catch (e) {
      // A late answer for an entry no longer selected is not an error of the current one.
      if (get().selectedDocId === docId) set({ error: errorMessage(e) });
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

  removeDocument: async (docId: string) => {
    set({ error: null });
    const result = await api.removeDocument(docId);
    // Refresh the list before clearing the selection, so the page never re-selects the removed entry.
    await get().fetchDocuments();
    set({ selectedDocId: '', selectedDocAST: null });
    return result;
  },

  uploadDocument: async (file, docType, domain, pauseForReview = true) => {
    try {
      const res = await api.uploadDocument(file, docType, domain, undefined, pauseForReview);
      set({ activeTask: null });
      get().pollTaskProgress(res.task_id);
      void get().fetchTasks();
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
        // Keep following it, but do not take the screen back from another upload the user opened.
        set((state) => (state.activeTask && state.activeTask.id !== taskId ? {} : { activeTask: task }));

        if (
          task.status === 'completed' ||
          task.status === 'failed' ||
          task.status === 'cancelled' ||
          task.status === 'awaiting_review'
        ) {
          if (interval) clearInterval(interval);
          void get().fetchTasks();
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

  confirmTaskReview: async (taskId: string, prune: string[] = []) => {
    set({ error: null });
    try {
      const updated = await api.confirmTaskReview(taskId, prune);
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
      void get().fetchTasks();
    } catch (e) {
      set({ error: errorMessage(e) });
    }
  },

  fetchTasks: async () => {
    set({ tasksLoading: true, tasksError: null });
    try {
      const page = await api.listTasks({ limit: 100 });
      set({ tasks: page.items, tasksTotal: page.total_count ?? page.items.length, tasksLoading: false });
    } catch (e) {
      set({ tasksLoading: false, tasksError: errorMessage(e) });
    }
  },

  /** Show an upload from the list; a running one is followed until it settles. */
  openTask: async (taskId: string) => {
    set({ error: null });
    try {
      const task = await api.getTaskProgress(taskId);
      set({ activeTask: task });
      if (!['completed', 'failed', 'cancelled', 'awaiting_review'].includes(task.status)) get().pollTaskProgress(taskId);
    } catch (e) {
      set({ error: errorMessage(e) });
    }
  },

  /** Delete an upload and its revisions; errors (still in the corpus, running) are thrown to the caller. */
  deleteTask: async (taskId: string) => {
    await api.deleteTask(taskId);
    set((state) => (state.activeTask?.id === taskId ? { activeTask: null } : {}));
    await get().fetchTasks();
  },

  /** A new draft of an indexed or removed upload; the corpus changes only when it is confirmed. */
  reopenTask: async (taskId: string) => {
    set({ error: null });
    const task = await api.reopenTask(taskId);
    set({ activeTask: task });
    void get().fetchTasks();
  },

}));

