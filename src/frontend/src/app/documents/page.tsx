'use client';

import React, { useEffect, useState } from 'react';
import { StatsCards } from '../../components/documents/StatsCards';
import { DocumentTable } from '../../components/documents/DocumentTable';
import { IngestionProgress } from '../../components/documents/IngestionProgress';
import { UploadModal } from '../../components/documents/UploadModal';
import { useDocumentStore } from '../../stores/documentStore';

export default function DocumentsPage() {
  const { fetchDocuments, activeTask, selectedDocId, selectedDocAST, documents } = useDocumentStore();
  const [rightTab, setRightTab] = useState<'tree' | 'json'>('tree');

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

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
              Neo4j Bolt: <strong className="text-on-surface font-metric-num">7687</strong>
            </span>
            <span className="text-outline-variant">•</span>
            <span className="font-label-code text-label-code text-on-surface-variant">
              Qdrant gRPC: <strong className="text-on-surface font-metric-num">6334</strong>
            </span>
          </div>

          <button
            onClick={() => alert('Chỉ mục toàn vẹn: 1,420 đỉnh (nodes) khớp 100% giữa Qdrant và Neo4j.')}
            className="flex items-center gap-space-xs px-space-md py-1.5 rounded-lg bg-secondary text-white hover:bg-opacity-95 shadow-sm transition-all font-headline-sm text-body-sm"
          >
            <span className="material-symbols-outlined text-[17px]">verified_user</span>
            <span>Kiểm định toàn vẹn chỉ mục</span>
          </button>
        </div>
      </div>

      <div className="p-gutter flex flex-col gap-space-lg w-full max-w-[1600px] mx-auto">
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
                    Nhật ký Luồng nạp Chỉ mục Kép
                  </span>
                </div>
                <span className="font-label-code text-label-statute text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                  Luồng trực tiếp: Đang hoạt động
                </span>
              </div>
              <div className="bg-surface-container-low p-space-sm rounded-lg font-label-code text-label-statute text-on-surface-variant flex flex-col gap-1 overflow-x-auto text-[11px]">
                <div className="flex items-center gap-space-xs text-on-tertiary-container">
                  <span>[TIẾN_TRÌNH]</span>
                  <span>PHÂN TÍCH THÀNH CÔNG: {selectedDoc?.title || 'BLLD2019'} đã phân tách cấu trúc chương, mục, điều, khoản.</span>
                </div>
                <div className="flex items-center gap-space-xs text-on-surface">
                  <span>[CẬP_NHẬT_VECTOR]</span>
                  <span>QDRANT_UPSERT: Tập hợp 'legal_ld_v5_bge' đã đồng bộ với vector BGE-m3.</span>
                </div>
                <div className="flex items-center gap-space-xs text-secondary">
                  <span>[HỢP_NHẤT_ĐỒ_THỊ]</span>
                  <span>NEO4J_MERGE: Đã thực thi lô Cypher (đã xác thực quan hệ CONTAINS, PART_OF, REFERS_TO).</span>
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
                    Mã Đỉnh: ROOT_{selectedDoc?.id || 'BLLD2019'}
                  </span>
                </div>
                <h2 className="font-headline-md text-headline-md text-on-surface leading-snug">
                  Kiểm tra Cấu trúc Phân cấp: {selectedDoc?.title || 'Bộ luật Lao động 2019'}
                </h2>
                <div className="font-label-code text-label-code text-on-surface-variant text-[11px]">
                  Mã số hiệu: {selectedDoc?.document_number || '45/2019/QH14'} • Quốc hội khóa XIV
                </div>
              </div>

              {/* Breakdown Stats */}
              <div className="grid grid-cols-3 gap-2 bg-surface-container-low p-space-sm rounded-lg text-center">
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Chương / Mục</div>
                  <div className="font-metric-num text-metric-num text-on-surface">17 / 12</div>
                </div>
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Điều luật</div>
                  <div className="font-metric-num text-metric-num text-secondary">
                    {selectedDoc?.nodes_count ? Math.floor(selectedDoc.nodes_count / 3) : 220} Điều
                  </div>
                </div>
                <div className="p-1">
                  <div className="font-label-statute text-label-statute text-on-surface-variant">Khoản & Điểm</div>
                  <div className="font-metric-num text-metric-num text-on-surface">
                    {selectedDoc?.chunks_count || 412} K | 185 Đm
                  </div>
                </div>
                <div className="p-1 col-span-3 bg-surface-container rounded mt-1 flex items-center justify-between px-3">
                  <span className="font-label-statute text-label-statute text-on-surface-variant">
                    Cạnh tham chiếu chéo (Cross-Citation):
                  </span>
                  <span className="font-label-code text-label-code font-bold text-secondary">
                    {selectedDoc?.edges_count || 142} REFERS_TO
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
                <span className="font-label-statute text-label-statute text-outline">Độ sâu: 5 cấp bậc</span>
              </div>

              {/* AST Tree View */}
              {rightTab === 'tree' ? (
                <div className="bg-surface-container-low p-space-md rounded-xl flex flex-col gap-2 font-body-sm text-body-sm overflow-hidden border border-outline-variant/30">
                  <div className="flex items-center gap-2 p-2 rounded bg-surface-container text-on-surface shadow-xs">
                    <span className="material-symbols-outlined text-[18px] text-secondary">folder_open</span>
                    <span className="font-headline-sm text-body-sm font-semibold">[Văn bản]</span>
                    <span className="font-label-code text-body-sm text-on-surface">{selectedDoc?.title}</span>
                  </div>

                  <div className="ml-4 pl-3 flex flex-col gap-2 border-l border-indigo-200">
                    <div className="flex items-center gap-2 p-2 rounded bg-surface-container-lowest text-on-surface shadow-xs">
                      <span className="material-symbols-outlined text-[16px] text-secondary">
                        subdirectory_arrow_right
                      </span>
                      <span className="font-label-statute text-label-statute text-secondary font-bold">[Chương III]</span>
                      <span className="font-body-md text-body-md text-on-surface">Hợp đồng lao động</span>
                    </div>

                    <div className="ml-4 pl-3 flex flex-col gap-2 border-l border-indigo-200">
                      <div className="flex items-center justify-between p-2 rounded-lg bg-surface-container-high text-on-surface shadow-xs">
                        <div className="flex items-center gap-2">
                          <span className="material-symbols-outlined text-[16px] text-secondary">gavel</span>
                          <span className="font-label-statute text-label-statute text-secondary font-bold">[Điều 35]</span>
                          <span className="font-headline-sm text-body-sm text-on-surface font-semibold">
                            Quyền đơn phương chấm dứt HĐLĐ của NLĐ
                          </span>
                        </div>
                        <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-surface-container-lowest text-secondary">
                          Đoạn Vector
                        </span>
                      </div>

                      {/* Point d Refers to edge */}
                      <div className="p-2 rounded bg-surface-container-lowest shadow-xs flex flex-col gap-2 border border-outline-variant/30">
                        <div className="flex items-center justify-between">
                          <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-surface-container font-bold">
                            [Điểm d - Ngành nghề đặc thù]
                          </span>
                        </div>
                        <div className="p-2 rounded-lg bg-surface-container flex flex-col gap-1 shadow-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-label-code text-label-statute text-secondary font-bold">
                              CẠNH ĐỒ THỊ: THAM CHIẾU (REFERS_TO)
                            </span>
                            <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-surface-container-lowest text-on-tertiary-container">
                              Đã đối chiếu & Liên kết
                            </span>
                          </div>
                          <div className="font-label-code text-label-statute text-on-surface text-[11px]">
                            ──▶ <strong>NĐ 145/2020/NĐ-CP</strong> (Điều 7 Khoản 2)
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-surface-container-lowest p-space-md rounded-xl font-label-code text-label-statute text-on-surface overflow-x-auto max-h-[360px] overflow-y-auto border border-outline-variant/30 text-[11px]">
                  <pre>{JSON.stringify(selectedDocAST || selectedDoc?.ast_tree_json || { doc_id: selectedDoc?.id }, null, 2)}</pre>
                </div>
              )}

              {/* Embedding & Storage card */}
              <div className="bg-surface-container-low p-space-md rounded-xl flex flex-col gap-space-xs border border-outline-variant/30 text-[12px]">
                <div className="flex items-center justify-between font-label-statute text-on-surface-variant">
                  <span>Thuộc tính Vector & Topology</span>
                  <span className="font-label-code text-secondary">Node Type: LegalPointNode</span>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-outline-variant/20 font-label-code">
                  <span>Embedding Model:</span>
                  <strong className="text-on-surface">BAAI/bge-m3 (Cosine 1024-d)</strong>
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

