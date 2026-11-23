'use client';

import React, { Suspense, useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { StatsCards } from '../../components/documents/StatsCards';
import { DocumentTable } from '../../components/documents/DocumentTable';
import { IngestionProgress } from '../../components/documents/IngestionProgress';
import { UploadPanel } from '../../components/documents/UploadPanel';
import { AppendixWorkspace } from '../../components/appendices/AppendixWorkspace';
import { LegalTree } from '../../components/inspector/LegalTree';
import { api, errorMessage } from '../../lib/api';
import type { HealthResponse } from '../../lib/types';
import { useDocumentStore } from '../../stores/documentStore';

const TABS = [
  { key: 'van-ban', icon: 'folder_special', label: 'Văn bản & Pháp điển' },
  { key: 'nap-pdf', icon: 'upload_file', label: 'Nạp PDF' },
  { key: 'danh-muc', icon: 'library_books', label: 'Danh mục & Biểu mẫu' },
] as const;
type TabKey = (typeof TABS)[number]['key'];
const RUNNING = ['pending', 'parsing', 'chunking', 'embedding', 'indexing'];

function healthLabel(health: HealthResponse | null): { text: string; tone: 'ok' | 'warn' | 'idle' } {
  if (!health) return { text: 'Chưa kiểm tra', tone: 'idle' };
  const states = [health.qdrant?.connection, health.neo4j?.connection];
  if (states.every((s) => s === 'connected')) return { text: 'Sẵn sàng', tone: 'ok' };
  if (states.some((s) => s === 'unavailable')) return { text: 'Thiếu kết nối', tone: 'warn' };
  return { text: 'Chưa kiểm tra', tone: 'idle' };
}

export default function DocumentsPage() {
  return <Suspense fallback={<p className="p-6">Đang mở kho văn bản…</p>}><DocumentsWorkspace /></Suspense>;
}

function DocumentsWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get('tab');
  const tab: TabKey = TABS.some((t) => t.key === requested) ? (requested as TabKey) : 'van-ban';
  const selectTab = (key: TabKey) => router.replace('/documents?tab=' + key, { scroll: false });
  const { fetchDocuments, activeTask, selectedDocId, selectedDocAST, documents, selectDocument, updateDocumentDomain, error } = useDocumentStore();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [probeError, setProbeError] = useState('');
  const [probing, setProbing] = useState(false);
  const [updatingDomain, setUpdatingDomain] = useState(false);
  const [showJson, setShowJson] = useState(false);

  async function probe() {
    setProbing(true); setProbeError('');
    try { setHealth(await api.health(true)); } catch (e) { setProbeError(errorMessage(e)); }
    finally { setProbing(false); }
  }

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
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

  const status = healthLabel(health);
  const taskBadge = activeTask?.status === 'awaiting_review' ? 'Chờ rà soát'
    : activeTask && RUNNING.includes(activeTask.status) ? 'Đang xử lý' : '';
  const taskFinished = !activeTask || ['completed', 'failed', 'cancelled'].includes(activeTask.status);

  return (
    <div className="flex flex-col w-full bg-surface">
      {/* Sub-Header: workspace tabs + data-store status */}
      <div className="w-full bg-surface-container-low px-gutter py-space-sm flex flex-wrap items-center justify-between gap-space-md shadow-sm border-b border-outline-variant/30">
        <div role="tablist" aria-label="Khu vực quản lý" className="flex flex-wrap items-center gap-1 p-1 rounded-lg bg-surface-container">
          {TABS.map((t) => (
            <button
              key={t.key} role="tab" type="button" aria-selected={tab === t.key}
              onClick={() => selectTab(t.key)}
              className={`flex items-center gap-space-xs px-space-md py-1.5 rounded-lg font-headline-sm text-body-sm transition-all ${
                tab === t.key ? 'bg-surface-container-lowest text-secondary shadow-sm' : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">{t.icon}</span>
              <span>{t.label}</span>
              {t.key === 'nap-pdf' && taskBadge && (
                <span className="ml-1 px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-900 text-[10px] font-semibold">{taskBadge}</span>
              )}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-space-sm">
          <div className="flex items-center gap-space-xs px-2.5 py-1 rounded-lg bg-surface-container-lowest shadow-sm border border-outline-variant/30">
            <span className={`relative inline-flex rounded-full h-2 w-2 ${status.tone === 'ok' ? 'bg-emerald-600' : status.tone === 'warn' ? 'bg-amber-500' : 'bg-slate-400'}`}></span>
            <span className="font-label-code text-label-code text-on-surface-variant">
              Kho dữ liệu & Đồ thị:{' '}
              <strong className={`font-semibold ${status.tone === 'ok' ? 'text-emerald-700' : status.tone === 'warn' ? 'text-amber-700' : 'text-on-surface'}`}>{status.text}</strong>
            </span>
          </div>

          <button
            onClick={probe} disabled={probing}
            className="flex items-center gap-space-xs px-space-md py-1.5 rounded-lg bg-secondary text-white hover:bg-opacity-95 shadow-sm transition-all font-headline-sm text-body-sm disabled:opacity-60"
          >
            <span className="material-symbols-outlined text-[17px]">verified_user</span>
            <span>{probing ? 'Đang kiểm tra…' : 'Kiểm tra kết nối'}</span>
          </button>
        </div>
      </div>

      <div className="p-gutter flex flex-col gap-space-lg w-full max-w-[1600px] mx-auto">
        {(error || probeError) && <p role="alert" className="p-space-md rounded-xl bg-error-container text-on-error-container font-body-sm text-body-sm">{error || probeError}</p>}

        {tab === 'van-ban' && <StatsCards refreshKey={activeTask?.status === 'completed' ? activeTask.id : undefined} />}

        {tab === 'nap-pdf' && (
          <div className="flex flex-col gap-space-md">
            {activeTask && <IngestionProgress task={activeTask} onOpenDocument={() => selectTab('van-ban')} />}
            {taskFinished && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
                <div className="lg:col-span-7"><UploadPanel /></div>
                <div className="lg:col-span-5 bg-surface-container-lowest rounded-xl p-space-md shadow-sm border border-outline-variant/30 flex flex-col gap-2 font-body-sm text-body-sm text-on-surface-variant">
                  <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface font-bold">Quy trình nạp PDF</span>
                  <ol className="list-decimal pl-5 space-y-1.5">
                    <li><strong className="text-on-surface">Tải lên</strong>: chọn lĩnh vực và file PDF.</li>
                    <li><strong className="text-on-surface">Rà soát OCR</strong>: đối chiếu từng trang PDF và sửa nội dung trong trình soạn thảo.</li>
                    <li><strong className="text-on-surface">So sánh thay đổi</strong>: xem Điều nào mới, thay thế, không đổi, và các Điều của văn bản khác bị sửa đổi.</li>
                    <li><strong className="text-on-surface">Xác nhận</strong>: lập chỉ mục vào kho tra cứu.</li>
                  </ol>
                </div>
              </div>
            )}
          </div>
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
                  <span className="font-label-statute text-label-statute uppercase tracking-wider text-secondary font-bold">
                    {selectedDoc?.document_type === 'phap_dien_html'
                      ? 'Cấu trúc Chi tiết Đề mục'
                      : 'Cấu trúc Chi tiết Văn bản'}
                  </span>
                  {selectedDoc?.document_number && (
                    <span className="font-label-code text-label-statute px-2 py-0.5 rounded bg-surface-container text-secondary font-semibold">
                      {selectedDoc.document_type === 'phap_dien_html'
                        ? selectedDoc.document_number
                        : `Số hiệu: ${selectedDoc.document_number}`}
                    </span>
                  )}
                </div>
                <h2 className="font-headline-md text-headline-md text-on-surface leading-snug">
                  {selectedDoc?.title || 'Chưa chọn mục'}
                </h2>
                <div className="font-label-code text-label-code text-on-surface-variant text-[11px] flex flex-wrap items-center gap-1.5">
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
                      className="bg-surface-container text-on-surface px-1.5 py-0.5 rounded font-label-code text-[11px] border border-outline-variant/40 cursor-pointer disabled:opacity-50"
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
              </div>

              {/* Breakdown Stats */}
              <div className="grid grid-cols-3 gap-2 bg-surface-container-low p-space-sm rounded-lg text-center">
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Chương / Mục</div>
                  <div className="font-metric-num text-metric-num text-on-surface">
                    {docStats.chuong > 0 ? `${docStats.chuong} Ch.` : 'Toàn văn'}
                    {docStats.muc > 0 ? ` • ${docStats.muc} Mục` : ''}
                  </div>
                </div>
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Điều luật</div>
                  <div className="font-metric-num text-metric-num text-secondary">
                    {docStats.dieu > 0 ? `${docStats.dieu} Điều` : 'Toàn văn'}
                  </div>
                </div>
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Khoản & Điểm</div>
                  <div className="font-metric-num text-metric-num text-on-surface">
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
                {selectedDocAST && !showJson && <span className="text-[11px] text-muted">Bấm để mở rộng</span>}
              </div>

              <div className="p-2.5 rounded-2xl bg-white border border-ink/10 max-h-[600px] overflow-auto legal-scroll">
                {selectedDocAST ? (
                  showJson
                    ? <pre className="font-mono text-[11px] text-ink-2 overflow-auto">{JSON.stringify(selectedDocAST, null, 2)}</pre>
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
                    className="w-full flex items-center justify-center gap-2 px-space-md py-2.5 rounded-xl bg-secondary text-white hover:bg-opacity-95 shadow-sm transition-all font-headline-sm text-body-sm"
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


