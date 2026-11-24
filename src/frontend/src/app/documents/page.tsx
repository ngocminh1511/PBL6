'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CorpusBrowser } from '../../components/documents/CorpusBrowser';
import { IngestionWorkspace } from '../../components/documents/IngestionWorkspace';
import { UploadModal } from '../../components/documents/UploadModal';
import { AppendixWorkspace } from '../../components/appendices/AppendixWorkspace';
import { useDocumentStore } from '../../stores/documentStore';
import { api, errorMessage } from '../../lib/api';
import { RemoveDocumentModal } from '../../components/documents/RemoveDocumentModal';

const TABS = [
  { key: 'van-ban', icon: 'folder_special', label: 'Văn bản & Pháp điển' },
  { key: 'nap-pdf', icon: 'upload_file', label: 'Nạp PDF' },
  { key: 'danh-muc', icon: 'library_books', label: 'Danh mục & Biểu mẫu' },
] as const;
type TabKey = (typeof TABS)[number]['key'];
const RUNNING = ['pending', 'parsing', 'chunking', 'embedding', 'indexing'];

export default function DocumentsPage() {
  return <Suspense fallback={<p className="p-6">Đang mở kho văn bản…</p>}><DocumentsWorkspace /></Suspense>;
}

function DocumentsWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get('tab');
  const tab: TabKey = TABS.some((t) => t.key === requested) ? (requested as TabKey) : 'van-ban';
  const selectTab = (key: TabKey) => router.replace('/documents?tab=' + key, { scroll: false });
  const taskId = params.get('task');
  const selectTask = (id: string) => router.replace('/documents?tab=nap-pdf&task=' + encodeURIComponent(id), { scroll: false });
  const { fetchDocuments, activeTask, selectedDocId, documents, selectDocument, removeDocument, error } = useDocumentStore();
  const [reviewNotice, setReviewNotice] = useState('');

  /** The newest upload of a PDF document, opened in the upload tab. */
  async function openReview(documentId: string) {
    setReviewNotice('');
    try {
      const page = await api.listTasks({ document_id: documentId, limit: 1 });
      if (page.items[0]) selectTask(page.items[0].id);
      else setReviewNotice('Không tìm thấy lượt nạp của văn bản này (có thể được nạp bằng dòng lệnh).');
    } catch (e) {
      setReviewNotice(errorMessage(e));
    }
  }
  const [removeTarget, setRemoveTarget] = useState<{ id: string; title: string } | null>(null);
  const [removedCount, setRemovedCount] = useState(0);
  const [uploadOpen, setUploadOpen] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => { if (!selectedDocId && documents.length) selectDocument(documents[0].id); }, [documents, selectedDocId, selectDocument]);

  const taskBadge = activeTask?.status === 'awaiting_review' ? 'Chờ rà soát'
    : activeTask && RUNNING.includes(activeTask.status) ? 'Đang xử lý' : '';

  return (
    <div className="flex flex-col w-full bg-surface">
      {/* Sub-Header: workspace tabs */}
      <div className="w-full bg-surface-container-low px-gutter py-space-sm flex flex-wrap items-center justify-between gap-space-md shadow-sm border-b border-outline-variant/30">
        <div role="tablist" aria-label="Khu vực quản lý" className="flex flex-wrap items-center gap-1 p-1 rounded-lg bg-surface-container">
          {TABS.map((t) => (
            <button
              key={t.key} role="tab" type="button" aria-selected={tab === t.key}
              onClick={() => selectTab(t.key)}
              className={`flex items-center gap-space-xs px-space-md py-1.5 rounded-lg text-[13px] font-medium transition-all ${
                tab === t.key ? 'bg-surface-container-lowest text-secondary shadow-sm' : 'text-ink-3 hover:text-ink'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
              <span>{t.label}</span>
              {t.key === 'nap-pdf' && taskBadge && (
                <span className="ml-1 px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-900 text-[11.5px] font-semibold">{taskBadge}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="p-gutter flex flex-col gap-space-lg w-full max-w-[1600px] mx-auto">
        {error && <p role="alert" className="p-space-md rounded-xl bg-error-container text-on-error-container text-[12.5px]">{error}</p>}
        {reviewNotice && <p role="status" className="p-space-sm rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-[12.5px]">{reviewNotice}</p>}

        {tab === 'nap-pdf' && (
          <IngestionWorkspace taskId={taskId} onSelectTask={selectTask} onUpload={() => setUploadOpen(true)}
            onOpenDocument={(documentId) => {
              if (documentId) void selectDocument(documentId);
              selectTab('van-ban');
            }} />
        )}

        {uploadOpen && <UploadModal onClose={() => setUploadOpen(false)} />}

        {removeTarget && (
          <RemoveDocumentModal
            target={removeTarget}
            onRemove={async (id) => { const result = await removeDocument(id); setRemovedCount((n) => n + 1); return result; }}
            onClose={() => setRemoveTarget(null)}
          />
        )}

        {tab === 'danh-muc' && <AppendixWorkspace basePath="/documents?tab=danh-muc" embedded />}

        {/* DOCUMENT WORKSPACE: corpus list / table of contents / article */}
        {tab === 'van-ban' && (
          <CorpusBrowser refreshKey={`${activeTask?.status === 'completed' ? activeTask.id : ''}:${removedCount}`}
            onRemove={setRemoveTarget} onOpenReview={(documentId) => void openReview(documentId)} />
        )}
      </div>
    </div>
  );
}


