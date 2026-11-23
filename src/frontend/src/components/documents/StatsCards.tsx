'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { SystemStats } from '../../lib/types';

const format = (value: number | null | undefined) =>
  typeof value === 'number' ? value.toLocaleString('vi-VN') : '—';

/** One compact strip of corpus counts; '—' when the store could not be read. */
export const StatsCards: React.FC<{ refreshKey?: unknown }> = ({ refreshKey }) => {
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    api.getSystemStats().then(setStats).catch(() => setStats(null));
  }, [refreshKey]);

  const items = [
    { icon: 'auto_stories', label: 'Đề mục & văn bản', value: format(stats?.total_documents),
      hint: stats ? `${format(stats.total_demuc)} đề mục · ${format(stats.total_pdf_docs)} PDF` : '' },
    { icon: 'gavel', label: 'Điều', value: format(stats?.total_articles), hint: '' },
    { icon: 'format_list_numbered', label: 'Khoản', value: format(stats?.total_clauses), hint: '' },
    { icon: 'segment', label: 'Điểm', value: format(stats?.total_points), hint: '' },
  ];

  return (
    <div className="w-full bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/30 grid grid-cols-2 md:grid-cols-4 divide-x divide-outline-variant/20">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-space-sm px-space-md py-space-sm min-w-0">
          <span className="material-symbols-outlined text-[20px] text-secondary shrink-0">{item.icon}</span>
          <div className="flex flex-col min-w-0">
            <span className="flex items-baseline gap-1.5">
              <span className="text-[18px] text-ink font-semibold">{item.value}</span>
              <span className="text-[12px] font-medium text-ink-3 truncate">{item.label}</span>
            </span>
            {item.hint && <span className="text-[11.5px] text-ink-3 truncate">{item.hint}</span>}
          </div>
        </div>
      ))}
    </div>
  );
};
