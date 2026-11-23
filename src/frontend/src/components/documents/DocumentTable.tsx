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
    totalDocuments,
    hasMore, nextCursor, fetchDocuments, isLoading,
  } = useDocumentStore();

  return (
    <div className="flex flex-col gap-space-md">
      {/* Control Strip: Search, Scope Chips, Filter */}
      <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col gap-space-md border border-outline-variant/30">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-space-md">
          {/* Search Field */}
          <div className="relative flex-1">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 text-[18px]">
              search
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm mã đề mục (VD: 20.2), số hiệu (45/2019/QH14), tên văn bản..."
              className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface-container-low text-ink text-[13px] placeholder:text-muted focus:outline-none focus:bg-surface-container transition-colors border border-outline-variant/30"
            />
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center justify-between gap-space-xs pt-space-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setSelectedDomain('all')}
              className={`px-2.5 py-1 rounded text-[12px] font-medium transition-all ${
                selectedDomain === 'all'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-ink hover:bg-surface-container-high'
              }`}
            >
              Tất cả{selectedDomain === 'all' ? ` (${totalDocuments})` : ''}
            </button>
            <button
              onClick={() => setSelectedDomain('lao_dong')}
              className={`px-2.5 py-1 rounded text-[12px] font-medium transition-all ${
                selectedDomain === 'lao_dong'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-ink hover:bg-surface-container-high'
              }`}
            >
              Lao động{selectedDomain === 'lao_dong' ? ` (${totalDocuments})` : ''}
            </button>
            <button
              onClick={() => setSelectedDomain('khac')}
              className={`px-2.5 py-1 rounded text-[12px] font-medium transition-all ${
                selectedDomain === 'khac'
                  ? 'bg-secondary text-on-secondary shadow-sm'
                  : 'bg-surface-container text-ink hover:bg-surface-container-high'
              }`}
            >
              Lĩnh vực khác{selectedDomain === 'khac' ? ` (${totalDocuments})` : ''}
            </button>
          </div>

          <div className="flex items-center gap-1 text-[12px] font-medium text-ink-3">
            <span>Nguồn:</span>
            <select
              value={selectedDocType}
              onChange={(e) => setSelectedDocType(e.target.value)}
              className="bg-surface-container text-ink px-2 py-1 rounded text-[12px] font-medium outline-none border border-outline-variant/30 cursor-pointer"
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
          <span className="text-[13px] font-semibold text-ink">
            Danh mục đề mục Pháp điển &amp; văn bản OCR
          </span>
          <span className="text-[12px] text-ink-3">
            Hiển thị {documents.length} / {totalDocuments} mục
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container text-ink-3 font-medium text-[11.5px]">
                <th className="py-2.5 px-space-md">Đề mục / Tên văn bản</th>
                <th className="py-2.5 px-space-sm">Lĩnh vực</th>
                <th className="py-2.5 px-space-sm text-center">Cơ cấu quy định</th>
                <th className="py-2.5 px-space-sm text-center">Ngày hiệu lực</th>
                <th className="py-2.5 px-space-md text-right">Tình trạng</th>
              </tr>
            </thead>
            <tbody className="text-[13px] divide-y divide-outline-variant/20">
              {!documents.length && <tr><td colSpan={5} className="p-space-lg text-center text-ink-3">{isLoading ? 'Đang tải danh mục…' : 'Chưa có mục phù hợp.'}</td></tr>}
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
                        ? 'bg-surface-container-high text-ink shadow-sm border-l-4 border-secondary'
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
                              className={`text-[14px] font-semibold ${
                                isSelected ? 'text-secondary' : 'text-ink'
                              }`}
                            >
                              {doc.title}
                            </span>
                            {doc.document_number && (
                              <span className="text-[12px] px-1.5 py-0.5 rounded bg-surface-container-lowest text-secondary shadow-xs font-semibold">
                                {doc.document_number}
                              </span>
                            )}
                          </div>
                          <span className="text-ink-3 truncate text-[11.5px]">
                            {isPhapDien ? 'Đề mục Bộ Pháp điển' : 'Văn bản từ PDF (OCR)'}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-space-sm">
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-surface-container text-ink text-[11.5px]">
                        {domainLabel}
                      </span>
                    </td>

                    <td className="py-3 px-space-sm text-center">
                      <div className="text-[14px] font-semibold tabular-nums text-ink">
                        {doc.articles_count ? `${doc.articles_count} Điều` : 'Toàn văn'}
                      </div>
                      <div className="font-medium text-muted text-[11.5px]">
                        {doc.clauses_count ? `${doc.clauses_count.toLocaleString()} Khoản` : 'Quy chuẩn'}
                      </div>
                    </td>

                    <td className="py-3 px-space-sm text-center">
                      <span className="text-[11.5px] text-ink">
                        {isPhapDien ? 'Hiện hành (Pháp điển)' : doc.effective_from_date || 'Đang cập nhật'}
                      </span>
                    </td>

                    <td className="py-3 px-space-md text-right">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-lowest text-emerald-700 font-medium shadow-xs text-[11.5px]">
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
          <span className="text-ink-3 text-[11.5px]">
            Danh mục văn bản pháp luật phục vụ tra cứu
          </span>
          <div className="flex items-center gap-space-xs">
            <button disabled={!hasMore || isLoading} onClick={() => fetchDocuments(nextCursor || undefined)}
              className="px-3 py-1.5 rounded-lg bg-secondary text-on-secondary text-[12.5px] disabled:opacity-40">
              {isLoading ? 'Đang tải…' : hasMore ? 'Tải thêm văn bản' : 'Đã hiển thị hết'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

