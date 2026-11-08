'use client';

import React, { useEffect, useState } from 'react';
import { StatsCards } from '../../components/documents/StatsCards';
import { DocumentTable } from '../../components/documents/DocumentTable';
import { IngestionProgress } from '../../components/documents/IngestionProgress';
import { UploadModal } from '../../components/documents/UploadModal';
import { ASTTree } from '../../components/documents/ASTTree';
import { api, errorMessage } from '../../lib/api';
import type { HealthResponse } from '../../lib/types';
import { useDocumentStore } from '../../stores/documentStore';

export default function DocumentsPage() {
  const { fetchDocuments, activeTask, selectedDocId, selectedDocAST, documents, selectDocument, error } = useDocumentStore();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [probeError, setProbeError] = useState('');
  const [probing, setProbing] = useState(false);
  async function probe() {
    setProbing(true); setProbeError('');
    try { setHealth(await api.health(true)); } catch (e) { setProbeError(errorMessage(e)); }
    finally { setProbing(false); }
  }
  const [rightTab, setRightTab] = useState<'tree' | 'json'>('tree');

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  useEffect(() => { if (!selectedDocId && documents.length) selectDocument(documents[0].id); }, [documents, selectedDocId, selectDocument]);

  const selectedDoc = documents.find((d) => d.id === selectedDocId) || documents[0];

  return (
    <div className="flex flex-col w-full bg-surface">
      {/* Sub-Header / Workspace Strip */}
      <div className="w-full bg-surface-container-low px-gutter py-space-sm flex flex-wrap items-center justify-between gap-space-md shadow-sm border-b border-outline-variant/30">
        <div className="flex items-center gap-space-md">
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-surface-container">
            <span className="flex items-center gap-space-xs px-space-md py-1.5 rounded-lg bg-surface-container-lowest text-secondary shadow-sm font-headline-sm text-body-sm">
              <span className="material-symbols-outlined text-[18px]">folder_special</span>
              <span>Kho Văn bản & Quản lý Chỉ mục Kép</span>
              <span className="w-2 h-2 rounded-full bg-secondary"></span>
            </span>
          </div>
          <div className="hidden md:flex items-center gap-space-xs font-label-statute text-label-statute text-on-surface-variant">
            <span>Giai đoạn:</span>
            <span className="px-2 py-0.5 rounded bg-surface-container text-on-surface font-label-code">
              Tiền xử lý & Lập chỉ mục kép (Data Ingestion Pipeline)
            </span>
          </div>
        </div>

        {/* Dual Sync Operational Status */}
        <div className="flex items-center gap-space-sm">
          <div className="flex items-center gap-space-xs px-2.5 py-1 rounded-lg bg-surface-container-lowest shadow-sm border border-outline-variant/30">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-on-tertiary-container opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-on-tertiary-container"></span>
            </span>
            <span className="font-label-code text-label-code text-on-surface-variant">
              Neo4j: <strong className="text-on-surface font-metric-num">{health?.neo4j.connection || "Chưa kiểm tra"}</strong>
            </span>
            <span className="text-outline-variant">•</span>
            <span className="font-label-code text-label-code text-on-surface-variant">
              Qdrant: <strong className="text-on-surface font-metric-num">{health?.qdrant.connection || "Chưa kiểm tra"}</strong>
            </span>
          </div>

          <button
            onClick={probe} disabled={probing}
            className="flex items-center gap-space-xs px-space-md py-1.5 rounded-lg bg-secondary text-white hover:bg-opacity-95 shadow-sm transition-all font-headline-sm text-body-sm"
          >
            <span className="material-symbols-outlined text-[17px]">verified_user</span>
            <span>{probing ? 'Đang kiểm tra…' : 'Kiểm tra kết nối chỉ mục'}</span>
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

            {/* Ingestion Stream Log */}
            <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col gap-space-sm border border-outline-variant/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-space-xs">
                  <span className="material-symbols-outlined text-secondary text-[18px]">terminal</span>
                  <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface font-bold">
                    Trạng thái tác vụ và văn bản
                  </span>
                </div>
                <span className="font-label-code text-label-statute text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                  {activeTask ? activeTask.status : 'Chưa có tác vụ nạp'}
                </span>
              </div>
              <div className="bg-surface-container-low p-space-sm rounded-lg font-label-code text-label-statute text-on-surface-variant flex flex-col gap-1 overflow-x-auto text-[11px]">
                <div className="flex items-center gap-space-xs text-on-tertiary-container">
                  <span>[TÁC_VỤ]</span>
                  <span>{activeTask?.current_step || 'Chưa chạy tác vụ nạp tài liệu.'}</span>
                </div>
                <div className="flex items-center gap-space-xs text-on-surface">
                  <span>[CHUNK]</span>
                  <span>{selectedDoc ? selectedDoc.chunks_count + ' chunk của văn bản đang chọn.' : 'Chưa chọn văn bản.'}</span>
                </div>
                <div className="flex items-center gap-space-xs text-secondary">
                  <span>[ĐỒ_THỊ]</span>
                  <span>{selectedDoc ? selectedDoc.nodes_count + ' node · ' + selectedDoc.edges_count + ' quan hệ trong dữ liệu.' : 'Chưa có dữ liệu đồ thị của văn bản.'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: Hierarchy-aware Parsing & Inspector Preview (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-space-md">
            <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col gap-space-md border border-outline-variant/30">
              {/* Header */}
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center justify-between">
                  <span className="font-label-statute text-label-statute uppercase tracking-wider text-secondary font-bold">
                    Thanh tra Cấu trúc Phân cấp
                  </span>
                  <span className="font-label-code text-label-statute px-2 py-0.5 rounded bg-surface-container text-on-surface">
                    Mã văn bản: {selectedDoc?.id || '—'}
                  </span>
                </div>
                <h2 className="font-headline-md text-headline-md text-on-surface leading-snug">
                  Kiểm tra Cấu trúc Phân cấp: {selectedDoc?.title || 'Chưa chọn văn bản'}
                </h2>
                <div className="font-label-code text-label-code text-on-surface-variant text-[11px]">
                  Mã số hiệu: {selectedDoc?.document_number || '—'}
                </div>
              </div>

              {/* Breakdown Stats */}
              <div className="grid grid-cols-3 gap-2 bg-surface-container-low p-space-sm rounded-lg text-center">
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Node trong dữ liệu</div>
                  <div className="font-metric-num text-metric-num text-on-surface">{selectedDoc?.nodes_count ?? '—'}</div>
                </div>
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Chunk văn bản</div>
                  <div className="font-metric-num text-metric-num text-secondary">
                    {selectedDoc?.chunks_count ?? '—'}
                  </div>
                </div>
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Quan hệ</div>
                  <div className="font-metric-num text-metric-num text-on-surface">
                    {selectedDoc?.edges_count ?? '—'}
                  </div>
                </div>
                <div className="p-1 col-span-3 bg-surface-container rounded mt-1 flex items-center justify-between px-3">
                  <span className="font-label-statute text-label-statute text-on-surface-variant">
                    Tổng quan hệ trong dữ liệu:
                  </span>
                  <span className="font-label-code text-label-code font-bold text-secondary">
                    {selectedDoc?.edges_count ?? '—'} cạnh
                  </span>
                </div>
              </div>

              {/* View Switcher */}
              <div className="flex items-center justify-between pt-space-xs">
                <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg">
                  <button
                    onClick={() => setRightTab('tree')}
                    className={`px-space-sm py-1 rounded text-body-sm font-headline-sm transition-all ${
                      rightTab === 'tree' ? 'bg-surface-container-lowest text-on-surface shadow-sm' : 'text-on-surface-variant'
                    }`}
                  >
                    Cây Phân cấp Trực quan
                  </button>
                  <button
                    onClick={() => setRightTab('json')}
                    className={`px-space-sm py-1 rounded text-body-sm font-headline-sm transition-all ${
                      rightTab === 'json' ? 'bg-surface-container-lowest text-on-surface shadow-sm' : 'text-on-surface-variant'
                    }`}
                  >
                    Mã AST / Graph JSON
                  </button>
                </div>
                <span className="font-label-statute text-label-statute text-outline">{selectedDocAST ? 'Cấu trúc từ dữ liệu' : 'Chưa có cấu trúc'}</span>
              </div>

              {/* AST Tree View */}
              <div className="bg-surface-container-low p-space-md rounded-xl border border-outline-variant/30 max-h-[560px] overflow-auto">
                {selectedDocAST ? (rightTab === 'tree' ? <ASTTree node={selectedDocAST} /> :
                  <pre className="font-label-code text-label-statute text-[11px]">{JSON.stringify(selectedDocAST, null, 2)}</pre>) :
                  <p className="font-body-sm text-body-sm text-on-surface-variant">Chọn một văn bản để xem cấu trúc.</p>}
              </div>

              {/* Embedding & Storage card */}
              <div className="bg-surface-container-low p-space-md rounded-xl flex flex-col gap-space-xs border border-outline-variant/30 text-[12px]">
                <div className="flex items-center justify-between font-label-statute text-on-surface-variant">
                  <span>Thuộc tính Vector & Topology</span>
                  <span className="font-label-code text-secondary">Cấu trúc dữ liệu nguồn</span>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-outline-variant/20 font-label-code">
                  <span>Embedding Model:</span>
                  <strong className="text-on-surface">{health?.embedding?.model || 'Đang đọc cấu hình'}</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <UploadModal />
    </div>
  );
}

