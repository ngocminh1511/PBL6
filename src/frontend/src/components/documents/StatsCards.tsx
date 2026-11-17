'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { SystemStats } from '../../lib/types';

export const StatsCards: React.FC = () => {
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    api.getSystemStats().then(setStats).catch(() => setStats(null));
  }, []);

  const totalDocs = stats?.total_documents ?? '—';
  const totalArticles = stats?.total_articles ?? '—';
  const totalClauses = stats?.total_clauses ?? '—';
  const totalPoints = stats?.total_points ?? '—';

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md w-full">
      {/* Card 1: Kho Văn bản Quy phạm */}
      <div className="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col justify-between border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface-variant font-bold">
            Kho Văn bản Quy phạm
          </span>
          <div className="w-8 h-8 rounded-lg bg-surface-container-low flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[20px]">auto_stories</span>
          </div>
        </div>
        <div className="my-space-sm flex items-baseline gap-space-xs">
          <span className="font-display-lg text-display-lg text-on-surface font-bold">
            {typeof totalDocs === 'number' ? totalDocs.toLocaleString() : totalDocs}
          </span>
          <span className="font-headline-sm text-headline-sm text-on-surface-variant">Văn bản</span>
        </div>
        <div className="flex flex-col gap-1 pt-space-xs bg-surface-container-low rounded-lg p-2 text-[12px]">
          <div className="flex items-center justify-between font-label-code text-on-surface">
            <span>• Pháp luật Lao động</span>
            <span className="font-metric-num text-secondary">
              {typeof totalDocs === 'number' ? `${totalDocs} văn bản` : 'Đang cập nhật'}
            </span>
          </div>
          <div className="flex items-center justify-between font-label-code text-on-surface-variant">
            <span>• Các lĩnh vực khác</span>
            <span className="font-metric-num text-on-surface">Sẵn sàng mở rộng</span>
          </div>
        </div>
      </div>

      {/* Card 2: Điều luật Quy chuẩn */}
      <div className="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col justify-between border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface-variant font-bold">
            Điều luật Quy chuẩn
          </span>
          <div className="w-8 h-8 rounded-lg bg-surface-container-low flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[20px]">gavel</span>
          </div>
        </div>
        <div className="my-space-sm flex items-baseline gap-space-xs">
          <span className="font-display-lg text-display-lg text-secondary font-bold">
            {typeof totalArticles === 'number' ? totalArticles.toLocaleString() : totalArticles}
          </span>
          <span className="font-headline-sm text-headline-sm text-on-surface-variant">Điều luật</span>
        </div>
        <div className="flex flex-col gap-1 pt-space-xs bg-surface-container-low rounded-lg p-2 text-[12px]">
          <div className="flex items-center justify-between font-label-code text-on-surface">
            <span>• Tình trạng số hóa:</span>
            <span className="font-metric-num text-emerald-700 font-semibold">Đầy đủ toàn văn</span>
          </div>
          <div className="flex items-center justify-between font-label-code text-on-surface-variant">
            <span>• Mục đích:</span>
            <span className="text-on-surface text-[11px]">Căn cứ pháp lý tra cứu & trích dẫn</span>
          </div>
        </div>
      </div>

      {/* Card 3: Khoản & Điểm Quy định */}
      <div className="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col justify-between border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface-variant font-bold">
            Khoản & Điểm Quy định
          </span>
          <div className="w-8 h-8 rounded-lg bg-surface-container-low flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[20px]">format_list_numbered</span>
          </div>
        </div>
        <div className="my-space-sm flex items-baseline gap-space-xs">
          <span className="font-display-lg text-display-lg text-on-surface font-bold">
            {typeof totalClauses === 'number' ? totalClauses.toLocaleString() : totalClauses}
          </span>
          <span className="font-headline-sm text-headline-sm text-on-surface-variant">Khoản</span>
          {typeof totalPoints === 'number' && (
            <span className="text-xs text-on-surface-variant ml-1 font-label-code">
              ({totalPoints.toLocaleString()} Điểm)
            </span>
          )}
        </div>
        <div className="flex flex-col gap-1 pt-space-xs bg-surface-container-low rounded-lg p-2 text-[12px]">
          <div className="flex items-center justify-between font-label-code text-on-surface">
            <span>• Phân rã quy định:</span>
            <span className="font-metric-num text-secondary">Quy chuẩn chi tiết</span>
          </div>
          <div className="flex items-center justify-between font-label-code text-on-surface-variant">
            <span>• Điều kiện & Chế tài:</span>
            <span className="text-on-surface text-[11px]">Từng trường hợp áp dụng cụ thể</span>
          </div>
        </div>
      </div>
    </div>
  );
};



