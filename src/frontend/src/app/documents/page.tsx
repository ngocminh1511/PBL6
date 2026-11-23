'use client';

import React, { Suspense, useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { StatsCards } from '../../components/documents/StatsCards';
import { DocumentTable } from '../../components/documents/DocumentTable';
import { IngestionProgress } from '../../components/documents/IngestionProgress';
import { UploadModal } from '../../components/documents/UploadModal';
import { IngestionStepper } from '../../components/documents/IngestionStepper';
import { ingestionSteps } from '../../lib/ingestionSteps';
import { AppendixWorkspace } from '../../components/appendices/AppendixWorkspace';
import { LegalTree } from '../../components/inspector/LegalTree';
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
  const { fetchDocuments, activeTask, selectedDocId, selectedDocAST, documents, selectDocument, updateDocumentDomain, removeDocument, error } = useDocumentStore();
  const [updatingDomain, setUpdatingDomain] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<{ id: string; title: string } | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [removedCount, setRemovedCount] = useState(0);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => { if (!selectedDocId && documents.length) selectDocument(documents[0].id); }, [documents, selectedDocId, selectDocument]);

  const selectedDoc = documents.find((d) => d.id === selectedDocId) || documents[0];

  const docStats = useMemo(() => {
    if (!selectedDocAST) {
      return {
        dieu: selectedDoc?.articles_count || 0,
        khoan: selectedDoc?.clauses_count || 0,
        diem: selectedDoc?.points_count || 0,
        chuong: 0,
        muc: 0,
      };
    }
    let chuong = 0, muc = 0, dieu = 0, khoan = 0, diem = 0;
    function walk(node: any) {
      if (!node) return;
      const t = (node.type || '').toLowerCase();
      if (t === 'chuong' || t === 'chapter') chuong++;
      else if (t === 'muc' || t === 'section') muc++;

      if (node.point_number || t === 'diem' || t === 'point') diem++;
      else if (node.clause_number || t === 'khoan' || t === 'clause') khoan++;
      else if (node.article_number || t === 'dieu' || t === 'article') dieu++;

      if (Array.isArray(node.children)) {
        for (const child of node.children) walk(child);
      }
    }
    walk(selectedDocAST);
    return {
      chuong,
      muc,
      dieu: dieu || selectedDoc?.articles_count || 0,
      khoan: khoan || selectedDoc?.clauses_count || 0,
      diem: diem || selectedDoc?.points_count || 0,
    };
  }, [selectedDocAST, selectedDoc]);

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

        {tab === 'van-ban' && <StatsCards refreshKey={`${activeTask?.status === 'completed' ? activeTask.id : ''}:${removedCount}`} />}

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

        {/* DOCUMENT WORKSPACE: corpus table / selected document structure */}
        {tab === 'van-ban' && <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg w-full items-start">
          {/* LEFT COLUMN: Document Corpus Management (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-space-md">
            <DocumentTable />
          </div>

          {/* RIGHT COLUMN: Document Detail & Structure Inspection (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-space-md">
            <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col gap-space-md border border-outline-variant/30">
              {/* Header */}
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-semibold text-secondary">
                    {selectedDoc?.document_type === 'phap_dien_html'
                      ? 'Cấu trúc chi tiết đề mục'
                      : 'Cấu trúc chi tiết văn bản'}
                  </span>
                  {selectedDoc?.document_number && (
                    <span className="text-[12px] px-2 py-0.5 rounded bg-surface-container text-secondary font-semibold">
                      {selectedDoc.document_type === 'phap_dien_html'
                        ? selectedDoc.document_number
                        : `Số hiệu: ${selectedDoc.document_number}`}
                    </span>
                  )}
                </div>
                <h2 className="text-[18px] font-semibold text-ink leading-snug">
                  {selectedDoc?.title || 'Chưa chọn mục'}
                </h2>
                <div className="text-ink-3 text-[11.5px] flex flex-wrap items-center gap-1.5">
                  <span>
                    {selectedDoc?.document_type === 'phap_dien_html'
                      ? 'Nguồn: Bộ Pháp điển • Hiệu lực: Hiện hành'
                      : `Nguồn: PDF (OCR) • Hiệu lực: ${selectedDoc?.effective_from_date || 'Chưa xác định'}`}
                  </span>
                  <span>• Lĩnh vực:</span>
                  {selectedDoc?.document_type === 'pdf' ? (
                    <select
                      aria-label="Đổi lĩnh vực văn bản"
                      disabled={updatingDomain}
                      value={selectedDoc.domain === 'khac' ? 'khac' : 'lao_dong'}
                      onChange={async (e) => {
                        setUpdatingDomain(true);
                        await updateDocumentDomain(selectedDoc.id, e.target.value as 'lao_dong' | 'khac');
                        setUpdatingDomain(false);
                      }}
                      className="bg-surface-container text-ink px-1.5 py-0.5 rounded text-[11.5px] border border-outline-variant/40 cursor-pointer disabled:opacity-50"
                    >
                      <option value="lao_dong">Lao động</option>
                      <option value="khac">Lĩnh vực khác</option>
                    </select>
                  ) : (
                    <span>
                      {selectedDoc?.domain === 'lao_dong'
                        ? 'Lao động'
                        : selectedDoc?.domain === 'khac'
                        ? 'Lĩnh vực khác'
                        : selectedDoc?.domain || 'Chung'}
                    </span>
                  )}
                </div>
                {selectedDoc?.document_type === 'pdf' && (
                  <button type="button" onClick={() => setRemoveTarget({ id: selectedDoc.id, title: selectedDoc.title })}
                    className="self-start mt-1 flex items-center gap-1 px-2 py-1 rounded-lg text-[12px] text-error border border-error/30 hover:bg-error-container/40 transition-colors">
                    <span className="material-symbols-outlined text-[16px]">delete</span>
                    Gỡ văn bản PDF này
                  </button>
                )}
              </div>

              {/* Breakdown Stats */}
              <div className="grid grid-cols-3 gap-2 bg-surface-container-low p-space-sm rounded-lg text-center">
                <div className="p-1">
                  <div className="text-[12px] font-medium text-ink-3">Chương / Mục</div>
                  <div className="text-[14px] font-semibold tabular-nums text-ink">
                    {docStats.chuong > 0 ? `${docStats.chuong} Ch.` : 'Toàn văn'}
                    {docStats.muc > 0 ? ` • ${docStats.muc} Mục` : ''}
                  </div>
                </div>
                <div className="p-1">
                  <div className="text-[12px] font-medium text-ink-3">Điều luật</div>
                  <div className="text-[14px] font-semibold tabular-nums text-secondary">
                    {docStats.dieu > 0 ? `${docStats.dieu} Điều` : 'Toàn văn'}
                  </div>
                </div>
                <div className="p-1">
                  <div className="text-[12px] font-medium text-ink-3">Khoản & Điểm</div>
                  <div className="text-[14px] font-semibold tabular-nums text-ink">
                    {docStats.khoan > 0 ? `${docStats.khoan} K` : '0 K'}
                    {docStats.diem > 0 ? ` • ${docStats.diem} Đm` : ''}
                  </div>
                </div>
              </div>

              {/* Tree: same hierarchy view as the chat inspector */}
              <div className="flex items-center justify-between pt-space-xs border-t border-outline-variant/20">
                <div className="flex items-center gap-1 bg-stone p-1 rounded-xl">
                  <button type="button" onClick={() => setShowJson(false)} className={'px-2.5 py-1 rounded-lg text-[12px] font-medium transition-colors ' + (!showJson ? 'bg-white text-ink shadow-[0_1px_2px_rgba(28,27,24,0.06)]' : 'text-ink-3 hover:text-ink')}>Cây phân cấp trực quan</button>
                  <button type="button" onClick={() => setShowJson(true)} className={'px-2.5 py-1 rounded-lg text-[12px] font-medium transition-colors ' + (showJson ? 'bg-white text-ink shadow-[0_1px_2px_rgba(28,27,24,0.06)]' : 'text-ink-3 hover:text-ink')}>Mã AST / JSON</button>
                </div>
                {selectedDocAST && !showJson && <span className="text-[11.5px] text-muted">Bấm để mở rộng</span>}
              </div>

              <div className="p-2.5 rounded-2xl bg-white border border-ink/10 max-h-[600px] overflow-auto legal-scroll">
                {selectedDocAST ? (
                  showJson
                    ? <pre className="font-mono text-[11.5px] text-ink-2 overflow-auto">{JSON.stringify(selectedDocAST, null, 2)}</pre>
                    : <LegalTree node={selectedDocAST} />
                ) : (
                  <p className="py-10 text-center text-[12.5px] text-muted">{selectedDoc ? (error ? 'Không tải được cấu trúc văn bản.' : 'Đang tải cấu trúc…') : 'Chọn một văn bản trong danh mục để xem cấu trúc.'}</p>
                )}
              </div>

              {/* Quick Action Button */}
              {selectedDoc && (
                <div className="pt-1">
                  <Link
                    href={`/chat?doc=${encodeURIComponent(selectedDoc.id)}`}
                    className="w-full flex items-center justify-center gap-2 px-space-md py-2.5 rounded-xl bg-secondary text-white hover:bg-opacity-95 shadow-sm transition-all text-[13px] font-medium"
                  >
                    <span className="material-symbols-outlined text-[18px]">chat</span>
                    <span>Đặt câu hỏi về văn bản này tại Trợ lý Hỏi đáp</span>
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>}
      </div>
    </div>
  );
}


