'use client';

import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

/** Pager with a typed page number and a "from–to of total" summary; `page` is 1-based. */
export function Pagination({ page, pageSize, total, onChange, disabled = false }: {
  page: number; pageSize: number; total: number; onChange: (page: number) => void; disabled?: boolean;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);
  const [draft, setDraft] = useState(String(page));

  useEffect(() => { setDraft(String(page)); }, [page]);

  const go = (next: number) => {
    const clamped = Math.min(Math.max(next, 1), pageCount);
    setDraft(String(clamped));
    if (clamped !== page) onChange(clamped);
  };
  const commit = () => {
    const parsed = parseInt(draft.trim(), 10);
    if (Number.isNaN(parsed)) setDraft(String(page)); else go(parsed);
  };

  const button = 'h-8 w-8 rounded-lg flex items-center justify-center text-ink hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

  return (
    <nav aria-label="Phân trang" className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-[12px] text-ink-3 tabular-nums">
        {total ? <><strong className="text-ink font-semibold">{from}–{to}</strong> trên {total.toLocaleString('vi-VN')}</> : '0 kết quả'}
      </span>
      <div className="flex items-center gap-0.5">
        <button type="button" onClick={() => go(1)} disabled={disabled || page <= 1} aria-label="Trang đầu" className={button}>
          <ChevronsLeft size={16} />
        </button>
        <button type="button" onClick={() => go(page - 1)} disabled={disabled || page <= 1} aria-label="Trang trước" className={button}>
          <ChevronLeft size={16} />
        </button>
        <label className="flex items-center gap-1.5 px-1 text-[12.5px] text-ink-3">
          Trang
          <input type="text" inputMode="numeric" value={draft} disabled={disabled || pageCount <= 1}
            onChange={(e) => setDraft(e.target.value.replace(/\D/g, ''))}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit(); } }}
            onBlur={commit} onFocus={(e) => e.target.select()}
            aria-label={`Số trang, từ 1 đến ${pageCount}`}
            className="w-12 h-8 rounded-lg border border-outline-variant/40 bg-surface-container-lowest text-center text-[12.5px] font-medium text-ink tabular-nums focus:outline-none focus:border-secondary disabled:opacity-60" />
          <span className="tabular-nums">/ {pageCount}</span>
        </label>
        <button type="button" onClick={() => go(page + 1)} disabled={disabled || page >= pageCount} aria-label="Trang sau" className={button}>
          <ChevronRight size={16} />
        </button>
        <button type="button" onClick={() => go(pageCount)} disabled={disabled || page >= pageCount} aria-label="Trang cuối" className={button}>
          <ChevronsRight size={16} />
        </button>
      </div>
    </nav>
  );
}
