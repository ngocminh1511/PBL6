'use client';

import React, { useState } from 'react';
import type { IngestionTaskSummary, TaskState } from '../../lib/types';
import { TASK_STATES } from '../../lib/ingestionTasks';
import { foldText } from '../../lib/articleOutline';

const FILTERS: { key: 'all' | TaskState; label: string }[] = [
  { key: 'all', label: 'Tất cả' },
  { key: 'awaiting_review', label: 'Chờ rà soát' },
  { key: 'editing', label: 'Đang sửa' },
  { key: 'indexed', label: 'Trong kho' },
  { key: 'removed', label: 'Đã gỡ' },
];

/** "24/11/2026 lúc 11:31" in the viewer's time; the server stores naive UTC timestamps. */
const date = (value: string) => {
  const when = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
  const day = when.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const time = when.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  return `${day} lúc ${time}`;
};

/** Every upload, newest first; picking one opens it on the right. */
export function IngestionList({ tasks, loading, error, selectedId, onSelect, onUpload }: {
  tasks: IngestionTaskSummary[];
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onUpload: () => void;
}) {
  const [filter, setFilter] = useState<'all' | TaskState>('all');
  const [query, setQuery] = useState('');
  const needle = foldText(query.trim());
  const shown = tasks.filter((t) => (filter === 'all' || t.state === filter)
    && (!needle || foldText(`${t.file_name} ${t.document_number ?? ''} ${t.document_id ?? ''}`).includes(needle)));

  return (
    <div className="h-full min-h-0 bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/30 flex flex-col overflow-hidden">
      <div className="p-space-sm flex flex-col gap-space-sm border-b border-outline-variant/20">
        <button type="button" onClick={onUpload}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-secondary text-white text-[13px] font-medium shadow-sm hover:opacity-90">
          <span className="material-symbols-outlined text-[18px]">add</span>
          Nạp văn bản
        </button>
        <div className="relative">
          <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3 text-[16px]">search</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm theo tên file hoặc số hiệu…"
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-surface-container-low text-ink text-[12.5px] placeholder:text-muted border border-outline-variant/30 focus:outline-none focus:bg-surface-container" />
        </div>
        <div role="group" aria-label="Lọc theo trạng thái" className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button key={f.key} type="button" onClick={() => setFilter(f.key)} aria-pressed={filter === f.key}
              className={`px-2 py-0.5 rounded-md text-[12px] font-medium transition-colors ${
                filter === f.key ? 'bg-secondary text-white' : 'bg-surface-container text-ink-3 hover:text-ink'}`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="px-space-sm py-1.5 text-[12px] text-ink-3 bg-surface-container-low/60 border-b border-outline-variant/20 flex justify-between">
        <span>{tasks.length} lượt nạp</span>
        {shown.length !== tasks.length && <span>đang hiện {shown.length}</span>}
      </div>

      <ul className="flex-1 min-h-0 overflow-y-auto legal-scroll divide-y divide-outline-variant/20">
        {error && <li role="alert" className="p-space-sm text-[12.5px] text-red-700">{error}</li>}
        {!error && !shown.length && (
          <li className="p-space-lg text-center text-[12.5px] text-ink-3">
            {loading ? 'Đang tải danh sách…' : tasks.length ? 'Không có lượt nạp phù hợp.' : 'Chưa có lượt nạp nào.'}
          </li>
        )}
        {shown.map((t) => {
          const selected = t.id === selectedId;
          const state = TASK_STATES[t.state];
          return (
            <li key={t.id}>
              <button type="button" onClick={() => onSelect(t.id)} aria-current={selected || undefined}
                className={`w-full text-left flex flex-col gap-1 px-space-sm py-2.5 border-l-[3px] transition-colors ${
                  selected ? 'bg-secondary/[0.06] border-secondary' : 'border-transparent hover:bg-surface-container-low'}`}>
                <span className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-[18px] text-amber-800 shrink-0 mt-px">
                    {t.document_type === 'pdf' ? 'picture_as_pdf' : 'html'}
                  </span>
                  <span className={`flex-1 min-w-0 text-[13px] font-semibold leading-snug break-words ${selected ? 'text-secondary' : 'text-ink'}`}>
                    {t.file_name}
                  </span>
                  <span className={`shrink-0 px-1.5 py-0.5 rounded text-[11.5px] font-semibold ${state.tone}`}>
                    {t.state === 'running' ? `${state.label} ${Math.round(t.progress)}%` : state.label}
                  </span>
                </span>
                <span className="pl-[26px] text-[12px] text-ink-3 flex flex-wrap gap-x-1.5">
                  {[t.document_number || t.document_id, t.total_pages ? `${t.total_pages} trang` : null,
                    t.edited_pages ? `${t.edited_pages} trang đã sửa` : null, date(t.created_at)]
                    .filter(Boolean).join(' · ')}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
