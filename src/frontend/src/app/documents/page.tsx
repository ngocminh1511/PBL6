'use client';

import React, { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CorpusBrowser } from '../../components/documents/CorpusBrowser';
import { IngestionProgress } from '../../components/documents/IngestionProgress';
import { UploadModal } from '../../components/documents/UploadModal';
import { IngestionStepper } from '../../components/documents/IngestionStepper';
import { ingestionSteps } from '../../lib/ingestionSteps';
import { AppendixWorkspace } from '../../components/appendices/AppendixWorkspace';
import { useDocumentStore } from '../../stores/documentStore';
import { RemoveDocumentModal } from '../../components/documents/RemoveDocumentModal';

const TABS = [
  { key: 'van-ban', icon: 'folder_special', label: 'Văn bản & Pháp điển' },
  { key: 'nap-pdf', icon: 'upload_file', label: 'Nạp PDF' },
  { key: 'danh-muc', icon: 'library_books', label: 'Danh mục & Biểu mẫu' },
] as const;
type TabKey = (typeof TABS)[number]['key'];
const RUNNING = ['pending', 'parsing', 'chunking', 'embedding', 'indexing'];
const PDF_STEPS = ingestionSteps('pdf');

export default function DocumentsPage() {
  return <Suspense fallback={<p className="p-6">Đang mở kho văn bản…</p>}><DocumentsWorkspace /></Suspense>;
}

function DocumentsWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get('tab');
  const tab: TabKey = TABS.some((t) => t.key === requested) ? (requested as TabKey) : 'van-ban';
  const selectTab = (key: TabKey) => router.replace('/documents?tab=' + key, { scroll: false });
  const { fetchDocuments, activeTask, selectedDocId, documents, selectDocument, removeDocument, error } = useDocumentStore();
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

        {tab === 'nap-pdf' && (
          <div className="flex flex-col gap-space-md">
            <div className="flex flex-col">
              <h1 className="text-[18px] font-semibold text-ink">Nạp văn bản</h1>
              <p className="text-[12.5px] text-ink-3">Tải PDF hoặc HTML Pháp điển, rà soát nội dung rồi lập chỉ mục vào kho tra cứu.</p>
            </div>

            {activeTask ? (
              <IngestionProgress task={activeTask} onOpenDocument={() => selectTab('van-ban')}
                onUploadAnother={() => setUploadOpen(true)} />
            ) : (
              <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm px-space-md py-12 flex flex-col items-center gap-5 text-center">
                <div className="w-14 h-14 rounded-2xl bg-secondary-fixed flex items-center justify-center text-secondary">
                  <span className="material-symbols-outlined text-[30px]">upload_file</span>
                </div>
                <div className="flex flex-col gap-1 max-w-md">
                  <span className="text-[15px] font-semibold text-ink">Chưa có văn bản nào đang được nạp</span>
                  <span className="text-[12.5px] text-ink-3">Tiến trình đọc, rà soát và lập chỉ mục sẽ hiển thị ở đây sau khi bạn tải tài liệu lên.</span>
                </div>
                <button type="button" onClick={() => setUploadOpen(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-secondary/40 text-secondary text-[13px] font-medium hover:bg-secondary/10">
                  <span className="material-symbols-outlined text-[18px]">add</span>
                  Nạp văn bản
                </button>
                <div className="w-full max-w-3xl pt-4 border-t border-outline-variant/20">
                  <IngestionStepper steps={PDF_STEPS} states={PDF_STEPS.map(() => 'pending')} muted />
                </div>
              </div>
            )}
          </div>
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
            onRemove={setRemoveTarget} />
        )}
      </div>
    </div>
  );
}


