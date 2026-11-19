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
    selectedDocType,
    setSelectedDocType,
    setUploadModalOpen,
    totalDocuments,
    hasMore, nextCursor, fetchDocuments, isLoading,
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
              placeholder="Tìm mã đề mục (VD: 20.2), số hiệu (45/2019/QH14), tên văn bản..."
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
              Tất cả{selectedDomain === 'all' ? ` (${totalDocuments})` : ''}
            </button>
            <button
              onClick={() => setSelectedDomain('lao_dong')}
              className={`px-2.5 py-1 rounded font-label-statute text-label-statute transition-all ${
                selectedDomain === 'lao_dong'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              Lao động{selectedDomain === 'lao_dong' ? ` (${totalDocuments})` : ''}
            </button>
            <button
              onClick={() => setSelectedDomain('khac')}
              className={`px-2.5 py-1 rounded font-label-statute text-label-statute transition-all ${
                selectedDomain === 'khac'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
              }`}
            >
              Lĩnh vực khác{selectedDomain === 'khac' ? ` (${totalDocuments})` : ''}
            </button>
          </div>

          <div className="flex items-center gap-1 font-label-statute text-label-statute text-on-surface-variant">
            <span>Nguồn:</span>
            <select
              value={selectedDocType}
              onChange={(e) => setSelectedDocType(e.target.value)}
              className="bg-surface-container text-on-surface px-2 py-1 rounded font-label-statute text-label-statute outline-none border border-outline-variant/30 cursor-pointer"
            >
              <option value="all">Tất cả nguồn</option>
              <option value="phap_dien_html">Đề mục Pháp điển</option>
              <option value="pdf">Văn bản PDF (OCR)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Document Table Ledger */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden flex flex-col border border-outline-variant/30">
        <div className="px-space-md py-space-sm bg-surface-container-low flex items-center justify-between border-b border-outline-variant/20">
          <span className="font-label-statute text-label-statute uppercase text-on-surface-variant tracking-wider font-bold">
            Danh mục Đề mục Pháp điển &amp; Văn bản OCR
          </span>
          <span className="font-label-code text-label-code text-on-surface-variant">
            Hiển thị {documents.length} / {totalDocuments} mục
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container text-on-surface-variant font-label-statute text-label-statute uppercase tracking-wider text-[11px]">
                <th className="py-2.5 px-space-md">Đề mục / Tên văn bản</th>
                <th className="py-2.5 px-space-sm">Lĩnh vực</th>
                <th className="py-2.5 px-space-sm text-center">Cơ cấu quy định</th>
                <th className="py-2.5 px-space-sm text-center">Ngày hiệu lực</th>
                <th className="py-2.5 px-space-md text-right">Tình trạng</th>
              </tr>
            </thead>
            <tbody className="font-body-md text-body-md divide-y divide-outline-variant/20">
              {!documents.length && <tr><td colSpan={5} className="p-space-lg text-center text-on-surface-variant">{isLoading ? 'Đang tải danh mục…' : 'Chưa có mục phù hợp.'}</td></tr>}
              {documents.map((doc) => {
                const isSelected = doc.id === selectedDocId;
                const isPhapDien = doc.document_type === 'phap_dien_html';
                const domainLabel = doc.domain === 'lao_dong' ? 'Lao động' : doc.domain === 'khac' ? 'Lĩnh vực khác' : doc.domain;
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
                          {isSelected ? 'verified' : isPhapDien ? 'menu_book' : 'picture_as_pdf'}
                        </span>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-space-xs flex-wrap">
                            <span
                              className={`font-headline-sm text-headline-sm font-semibold ${
                                isSelected ? 'text-secondary' : 'text-on-surface'
                              }`}
                            >
                              {doc.title}
                            </span>
                            {doc.document_number && (
                              <span className="font-label-code text-label-statute px-1.5 py-0.5 rounded bg-surface-container-lowest text-secondary shadow-xs font-semibold">
                                {doc.document_number}
                              </span>
                            )}
                          </div>
                          <span className="font-body-sm text-body-sm text-on-surface-variant truncate text-[11px]">
                            {isPhapDien ? 'Đề mục Bộ Pháp điển' : 'Văn bản từ PDF (OCR)'}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-space-sm">
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container text-on-surface font-label-statute text-[11px]">
                        {domainLabel}
                      </span>
                    </td>

                    <td className="py-3 px-space-sm text-center">
                      <div className="font-metric-num text-metric-num text-on-surface">
                        {doc.articles_count ? `${doc.articles_count} Điều` : 'Toàn văn'}
                      </div>
                      <div className="font-label-statute text-label-statute text-outline text-[10px]">
                        {doc.clauses_count ? `${doc.clauses_count.toLocaleString()} Khoản` : 'Quy chuẩn'}
                      </div>
                    </td>

                    <td className="py-3 px-space-sm text-center">
                      <span className="font-label-code text-[11px] text-on-surface">
                        {isPhapDien ? 'Hiện hành (Pháp điển)' : doc.effective_from_date || 'Đang cập nhật'}
                      </span>
                    </td>

                    <td className="py-3 px-space-md text-right">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-lowest text-emerald-700 font-label-statute text-label-statute shadow-xs text-[11px]">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        Sẵn sàng tra cứu
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
            Danh mục văn bản pháp luật phục vụ tra cứu
          </span>
          <div className="flex items-center gap-space-xs">
            <button disabled={!hasMore || isLoading} onClick={() => fetchDocuments(nextCursor || undefined)}
              className="px-3 py-1.5 rounded-lg bg-secondary text-on-secondary font-body-sm text-body-sm disabled:opacity-40">
              {isLoading ? 'Đang tải…' : hasMore ? 'Tải thêm văn bản' : 'Đã hiển thị hết'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

