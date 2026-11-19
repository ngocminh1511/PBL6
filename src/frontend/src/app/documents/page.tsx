'use client';

import React, { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { StatsCards } from '../../components/documents/StatsCards';
import { DocumentTable } from '../../components/documents/DocumentTable';
import { IngestionProgress } from '../../components/documents/IngestionProgress';
import { UploadModal } from '../../components/documents/UploadModal';
import { ASTTree } from '../../components/documents/ASTTree';
import { api, errorMessage } from '../../lib/api';
import type { HealthResponse } from '../../lib/types';
import { useDocumentStore } from '../../stores/documentStore';

export default function DocumentsPage() {
  const { fetchDocuments, activeTask, selectedDocId, selectedDocAST, documents, selectDocument, updateDocumentDomain, error } = useDocumentStore();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [probeError, setProbeError] = useState('');
  const [probing, setProbing] = useState(false);
  const [updatingDomain, setUpdatingDomain] = useState(false);

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

  return (
    <div className="flex flex-col w-full bg-surface">
      {/* Sub-Header / Workspace Strip */}
      <div className="w-full bg-surface-container-low px-gutter py-space-sm flex flex-wrap items-center justify-between gap-space-md shadow-sm border-b border-outline-variant/30">
        <div className="flex items-center gap-space-md">
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-surface-container">
            <span className="flex items-center gap-space-xs px-space-md py-1.5 rounded-lg bg-surface-container-lowest text-secondary shadow-sm font-headline-sm text-body-sm">
              <span className="material-symbols-outlined text-[18px]">folder_special</span>
              <span>Kho Văn bản Quy phạm Pháp luật</span>
              <span className="w-2 h-2 rounded-full bg-secondary"></span>
            </span>
          </div>
          <div className="hidden md:flex items-center gap-space-xs font-label-statute text-label-statute text-on-surface-variant">
            <span>Dữ liệu số hóa phục vụ tra cứu & hỏi đáp</span>
          </div>
        </div>

        {/* Operational Status (Option 2: Thân thiện người dùng) */}
        <div className="flex items-center gap-space-sm">
          <div className="flex items-center gap-space-xs px-2.5 py-1 rounded-lg bg-surface-container-lowest shadow-sm border border-outline-variant/30">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
            </span>
            <span className="font-label-code text-label-code text-on-surface-variant">
              Hệ thống Dữ liệu & Đồ thị Tri thức:{' '}
              <strong className="text-emerald-700 font-semibold">
                {health?.neo4j?.connection === 'connected' && health?.qdrant?.connection === 'connected'
                  ? 'Sẵn sàng'
                  : 'Đang hoạt động'}
              </strong>
            </span>
          </div>

          <button
            onClick={probe} disabled={probing}
            className="flex items-center gap-space-xs px-space-md py-1.5 rounded-lg bg-secondary text-white hover:bg-opacity-95 shadow-sm transition-all font-headline-sm text-body-sm"
          >
            <span className="material-symbols-outlined text-[17px]">verified_user</span>
            <span>{probing ? 'Đang kiểm tra…' : 'Kiểm tra trạng thái kho dữ liệu'}</span>
          </button>
        </div>
      </div>

      <div className="p-gutter flex flex-col gap-space-lg w-full max-w-[1600px] mx-auto">
        {(error || probeError) && <p role="alert" className="p-space-md rounded-xl bg-error-container text-on-error-container font-body-sm text-body-sm">{error || probeError}</p>}
        {/* TOP KPI BANNER */}
        <StatsCards />

        {/* INGESTION REAL-TIME PROGRESS BAR (if active task) */}
        {activeTask && <IngestionProgress task={activeTask} />}

        {/* MAIN WORKSPACE: 60% Left / 40% Right */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg w-full items-start">
          {/* LEFT COLUMN: Document Corpus Management (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-space-md">
            <DocumentTable />

            {/* Document Status Stream */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col gap-space-sm border border-outline-variant/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-secondary text-[18px]">info</span>
                  <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface font-bold">
                    Tình trạng & Cập nhật Văn bản
                  </span>
                </div>
                <span className="font-label-code text-label-statute text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                  {activeTask ? (activeTask.status === 'completed' ? 'Đã hoàn tất nạp' : 'Đang xử lý') : 'Hệ thống sẵn sàng'}
                </span>
              </div>
              <div className="bg-surface-container-low p-space-sm rounded-lg font-label-code text-label-statute text-on-surface-variant flex flex-col gap-1.5 text-[11px]">
                <div className="flex items-center gap-space-xs text-on-tertiary-container">
                  <span className="font-bold text-secondary">[TIẾN TRÌNH]</span>
                  <span>{activeTask?.current_step || 'Không có tác vụ nạp mới đang chạy.'}</span>
                </div>
                <div className="flex items-center gap-space-xs text-on-surface">
                  <span className="font-bold text-on-surface">[ĐANG CHỌN]</span>
                  <span>{selectedDoc ? `${selectedDoc.title}${selectedDoc.document_number ? ` (${selectedDoc.document_number})` : ''}` : 'Chưa chọn mục.'}</span>
                </div>
                <div className="flex items-center gap-space-xs text-secondary">
                  <span className="font-bold text-emerald-700">[TRẠNG THÁI]</span>
                  <span>{selectedDoc ? 'Đã hoàn tất bóc tách cấu trúc, sẵn sàng phục vụ hỏi đáp và đối soát trích dẫn.' : '—'}</span>
                </div>
              </div>
            </div>
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

              {/* Tree Header */}
              <div className="flex items-center justify-between pt-space-xs border-t border-outline-variant/20">
                <div className="flex items-center gap-1.5 font-headline-sm text-body-sm text-on-surface">
                  <span className="material-symbols-outlined text-[18px] text-secondary">format_list_bulleted</span>
                  <span>Mục lục & Toàn văn Điều khoản</span>
                </div>
                <span className="font-label-statute text-label-statute text-on-surface-variant text-[11px]">
                  {selectedDocAST ? 'Bấm từng điều để mở rộng' : ''}
                </span>
              </div>

              {/* AST Tree View */}
              <div className="bg-surface-container-low p-space-md rounded-xl border border-outline-variant/30 max-h-[600px] overflow-auto">
                {selectedDocAST ? (
                  <ASTTree node={selectedDocAST} />
                ) : (
                  <p className="font-body-sm text-body-sm text-on-surface-variant">Chọn một văn bản trong danh mục để xem cấu trúc.</p>
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
        </div>
      </div>

      <UploadModal />
    </div>
  );
}


