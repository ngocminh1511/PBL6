'use client';

import React from 'react';
import { useDocumentStore } from '../../stores/documentStore';

export const DocumentTable: React.FC = () => {
  const {
    documents,
    selectedDocId,
    selectDocument,
    searchQuery,
    setSearchQuery,
    selectedDomain,
    setSelectedDomain,
    setUploadModalOpen,
    totalDocuments,
  } = useDocumentStore();

  return (
    <div className="flex flex-col gap-space-md">
      {/* Control Strip: Search, Scope Chips, Filter & Ingestion Trigger */}
      <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col gap-space-md border border-outline-variant/30">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-space-md">
          {/* Search Field */}
          <div className="relative flex-1">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">
              search
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm số hiệu (VD: 45/2019/QH14), trích yếu văn bản..."
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface-container-low text-on-surface font-body-md text-body-md placeholder:text-outline focus:outline-none focus:bg-surface-container transition-colors border border-outline-variant/30"
            />
          </div>

          {/* Ingest Button */}
          <button
            onClick={() => setUploadModalOpen(true)}
            type="button"
            className="shrink-0 flex items-center justify-center gap-space-xs px-space-md py-2 rounded-lg bg-[#0F172A] text-white hover:bg-opacity-90 shadow-sm transition-all font-headline-sm text-body-sm"
          >
            <span className="material-symbols-outlined text-[18px]">post_add</span>
            <span>+ Nạp văn bản mới</span>
          </button>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center justify-between gap-space-xs pt-space-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setSelectedDomain('all')}
              className={`px-2.5 py-1 rounded font-label-statute text-label-statute transition-all ${
                selectedDomain === 'all'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              Tất cả ({totalDocuments})
            </button>
            <button
              onClick={() => setSelectedDomain('lao_dong')}
              className={`px-2.5 py-1 rounded font-label-statute text-label-statute transition-all ${
                selectedDomain === 'lao_dong'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              Lao động (24)
            </button>
            <button
              onClick={() => setSelectedDomain('bhxh')}
              className={`px-2.5 py-1 rounded font-label-statute text-label-statute transition-all ${
                selectedDomain === 'bhxh'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              Bảo hiểm xã hội (18)
            </button>
          </div>

          <div className="flex items-center gap-1 font-label-statute text-label-statute text-on-surface-variant">
            <span>Loại VB:</span>
            <select className="bg-surface-container text-on-surface px-2 py-1 rounded font-label-statute text-label-statute outline-none border border-outline-variant/30">
              <option>Tất cả loại hình</option>
              <option>Bộ luật / Luật</option>
              <option>Nghị định</option>
              <option>Thông tư</option>
            </select>
          </div>
        </div>
      </div>

      {/* Document Table Ledger */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col border border-outline-variant/30">
        <div className="px-space-md py-space-sm bg-surface-container-low flex items-center justify-between border-b border-outline-variant/20">
          <span className="font-label-statute text-label-statute uppercase text-on-surface-variant tracking-wider font-bold">
            Danh mục Văn bản Đã Lập Chỉ mục Kép
          </span>
          <span className="font-label-code text-label-code text-on-surface-variant">
            Hiển thị {documents.length} / {totalDocuments} văn bản trọng điểm
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container text-on-surface-variant font-label-statute text-label-statute uppercase tracking-wider text-[11px]">
                <th className="py-2.5 px-space-md">Số hiệu / Tên văn bản</th>
                <th className="py-2.5 px-space-sm text-center">Phân cấp Đỉnh (Nodes)</th>
                <th className="py-2.5 px-space-sm text-center">Tham chiếu (REFERS_TO)</th>
                <th className="py-2.5 px-space-sm">Vector Nhúng</th>
                <th className="py-2.5 px-space-md text-right">Trạng thái Cây</th>
              </tr>
            </thead>
            <tbody className="font-body-md text-body-md divide-y divide-outline-variant/20">
              {documents.map((doc) => {
                const isSelected = doc.id === selectedDocId;
                return (
                  <tr
                    key={doc.id}
                    onClick={() => selectDocument(doc.id)}
                    className={`cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-surface-container-high text-on-surface shadow-sm border-l-4 border-secondary'
                        : 'hover:bg-surface-container-low'
                    }`}
                  >
                    <td className="py-3 px-space-md">
                      <div className="flex items-start gap-space-xs">
                        <span className="material-symbols-outlined text-secondary text-[20px] shrink-0 mt-0.5">
                          {isSelected ? 'verified' : 'description'}
                        </span>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-space-xs">
                            <span
                              className={`font-headline-sm text-headline-sm font-semibold ${
                                isSelected ? 'text-secondary' : 'text-on-surface'
                              }`}
                            >
                              {doc.title}
                            </span>
                            {doc.document_number && (
                              <span className="font-label-code text-label-statute px-1.5 py-0.5 rounded bg-surface-container-lowest text-secondary shadow-xs">
                                {doc.document_number}
                              </span>
                            )}
                          </div>
                          <span className="font-body-sm text-body-sm text-on-surface-variant truncate text-[11px]">
                            Hiệu lực: {doc.effective_from_date || '01/01/2021'} • Lĩnh vực:{' '}
                            {doc.domain === 'lao_dong' ? 'Lao động' : doc.domain}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-space-sm text-center">
                      <div className="font-metric-num text-metric-num text-on-surface">
                        {doc.nodes_count || 817} Đỉnh AST
                      </div>
                      <div className="font-label-statute text-label-statute text-outline text-[10px]">
                        Điều • Khoản • Điểm
                      </div>
                    </td>

                    <td className="py-3 px-space-sm text-center">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-surface-container text-on-surface font-metric-num text-label-code text-[11px]">
                        {doc.edges_count || 142} Cạnh
                      </span>
                    </td>

                    <td className="py-3 px-space-sm">
                      <div className="flex flex-col">
                        <span className="font-metric-num text-label-code text-on-surface text-[12px]">
                          {doc.chunks_count || 412} Đoạn (Chunks)
                        </span>
                        <span className="font-label-statute text-label-statute text-outline text-[10px]">
                          BAAI/bge-m3
                        </span>
                      </div>
                    </td>

                    <td className="py-3 px-space-md text-right">
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-surface-container-lowest text-on-tertiary-container font-label-statute text-label-statute shadow-xs text-[11px]">
                        <span className="w-1.5 h-1.5 rounded-full bg-on-tertiary-container animate-pulse"></span>
                        100% Phân giải
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Cursor Pagination Footer */}
        <div className="p-space-md bg-surface-container-low flex items-center justify-between border-t border-outline-variant/30">
          <span className="font-label-code text-label-code text-on-surface-variant text-[11px]">
            Hiển thị danh mục văn bản số hóa (Phân trang con trỏ Cursor)
          </span>
          <div className="flex items-center gap-space-xs">
            <button className="px-2.5 py-1 rounded bg-surface-container text-outline hover:text-on-surface text-body-sm transition-colors text-[12px]">
              Trước
            </button>
            <button className="px-2.5 py-1 rounded bg-secondary text-on-secondary font-metric-num text-body-sm text-[12px]">
              1
            </button>
            <button className="px-2.5 py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-metric-num text-body-sm text-[12px]">
              2
            </button>
            <button className="px-2.5 py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-metric-num text-body-sm text-[12px]">
              3
            </button>
            <button className="px-2.5 py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high text-body-sm text-[12px]">
              Sau
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

