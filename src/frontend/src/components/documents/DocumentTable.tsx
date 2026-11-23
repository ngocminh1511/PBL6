'use client';

import React, { useEffect, useState } from 'react';
import { useDocumentStore } from '../../stores/documentStore';
import { api } from '../../lib/api';
import type { DocumentRecord, SystemStats } from '../../lib/types';

const SOURCES = [
  { key: 'all', label: 'Tất cả' },
  { key: 'phap_dien_html', label: 'Pháp điển' },
  { key: 'pdf', label: 'PDF' },
] as const;

const count = (value?: number | null) => (typeof value === 'number' ? value.toLocaleString('vi-VN') : '—');

/** "20.2 · Bộ Pháp điển" or "45/2019/QH14 · PDF (OCR) · hiệu lực 2021-01-01". */
function subtitle(doc: DocumentRecord) {
  if (doc.document_type === 'phap_dien_html') return [doc.document_number || doc.id, 'Bộ Pháp điển'];
  return [doc.document_number, 'PDF (OCR)', doc.effective_from_date ? `hiệu lực ${doc.effective_from_date}` : null]
    .filter(Boolean) as string[];
}

/** The corpus list; refreshKey reloads the corpus totals after an upload or a removal. */
export const DocumentTable: React.FC<{ refreshKey?: unknown }> = ({ refreshKey }) => {
  const {
    documents, selectedDocId, selectDocument, searchQuery, setSearchQuery,
    selectedDocType, setSelectedDocType, totalDocuments, hasMore, nextCursor, fetchDocuments, isLoading,
  } = useDocumentStore();
  const [stats, setStats] = useState<SystemStats | null>(null);
  useEffect(() => { api.getSystemStats().then(setStats).catch(() => setStats(null)); }, [refreshKey]);
  const totals = stats ? [`${count(stats.total_articles)} Điều`, `${count(stats.total_clauses)} khoản`, `${count(stats.total_points)} điểm`] : [];

  return (
    <div className="h-full min-h-0 bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/30 flex flex-col overflow-hidden">
      {/* Search + source filter */}
      <div className="p-space-sm flex flex-col gap-space-sm border-b border-outline-variant/20">
        <div className="relative flex-1">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 text-[18px]">search</span>
          <input
            type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm đề mục (20.2), số hiệu (45/2019/QH14) hoặc tên văn bản…"
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface-container-low text-ink text-[13px] placeholder:text-muted focus:outline-none focus:bg-surface-container transition-colors border border-outline-variant/30"
          />
        </div>
        <div role="group" aria-label="Lọc theo nguồn" className="grid grid-cols-3 gap-1 p-1 rounded-lg bg-surface-container">
          {SOURCES.map((s) => (
            <button key={s.key} type="button" onClick={() => setSelectedDocType(s.key)} aria-pressed={selectedDocType === s.key}
              className={`px-2.5 py-1 rounded-md text-[12.5px] font-medium transition-colors ${
                selectedDocType === s.key ? 'bg-surface-container-lowest text-ink shadow-sm' : 'text-ink-3 hover:text-ink'}`}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="px-space-sm py-2 flex flex-col gap-0.5 text-[12px] text-ink-3 bg-surface-container-low/60 border-b border-outline-variant/20">
        <span className="flex justify-between">
          <span>{totalDocuments} mục{stats ? ` · ${count(stats.total_demuc)} đề mục, ${count(stats.total_pdf_docs)} PDF` : ''}</span>
          {documents.length < totalDocuments && <span className="tabular-nums">đang hiện {documents.length}</span>}
        </span>
        {totals.length > 0 && <span className="tabular-nums">Toàn kho: {totals.join(' · ')}</span>}
      </div>

      {/* Entries */}
      <ul className="flex-1 min-h-0 overflow-y-auto legal-scroll divide-y divide-outline-variant/20">
        {!documents.length && (
          <li className="p-space-lg text-center text-[13px] text-ink-3">{isLoading ? 'Đang tải danh mục…' : 'Chưa có mục phù hợp.'}</li>
        )}
        {documents.map((doc) => {
          const selected = doc.id === selectedDocId;
          const isPhapDien = doc.document_type === 'phap_dien_html';
          return (
            <li key={doc.id}>
              <button type="button" onClick={() => selectDocument(doc.id)} aria-current={selected || undefined}
                className={`w-full text-left flex items-center gap-3 px-space-sm py-2.5 transition-colors border-l-[3px] ${
                  selected ? 'bg-secondary/[0.06] border-secondary' : 'border-transparent hover:bg-surface-container-low'}`}>
                <span className={`w-8 h-8 rounded-lg shrink-0 flex items-center justify-center ${
                  isPhapDien ? 'bg-secondary/10 text-secondary' : 'bg-amber-50 text-amber-800'}`}>
                  <span className="material-symbols-outlined text-[18px]">{isPhapDien ? 'menu_book' : 'picture_as_pdf'}</span>
                </span>
                <span className="flex-1 min-w-0 flex flex-col gap-0.5">
                  <span className={`text-[13px] font-semibold leading-snug ${selected ? 'text-secondary' : 'text-ink'}`}>{doc.title}</span>
                  <span className="text-[12px] text-ink-3 truncate">{subtitle(doc).join(' · ')}</span>
                </span>
                <span className="shrink-0 text-right flex flex-col">
                  <span className="text-[13px] font-semibold text-ink tabular-nums">{doc.articles_count ? `${count(doc.articles_count)} Điều` : 'Toàn văn'}</span>
                  <span className="text-[12px] text-ink-3 tabular-nums">{count(doc.clauses_count)} khoản</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      {hasMore && (
        <div className="p-space-sm flex justify-center border-t border-outline-variant/20">
          <button type="button" disabled={isLoading} onClick={() => fetchDocuments(nextCursor || undefined)}
            className="px-3 py-1.5 rounded-lg text-[12.5px] font-medium text-secondary hover:bg-secondary/10 disabled:opacity-50">
            {isLoading ? 'Đang tải…' : 'Tải thêm'}
          </button>
        </div>
      )}
    </div>
  );
};
