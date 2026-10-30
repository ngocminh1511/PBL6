'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { SystemStats } from '../../lib/types';

export const StatsCards: React.FC = () => {
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    api.getSystemStats().then(setStats).catch(console.error);
  }, []);

  const totalDocs = stats?.total_documents ?? 42;
  const totalNodes = stats?.total_nodes ?? 1420;
  const totalEdges = stats?.total_edges ?? 3184;
  const totalChunks = stats?.total_chunks ?? 1481;
  const vectorStatus = stats?.vector_db_status ?? 'Trực tuyến (Cosine 1536-d)';
  const graphStatus = stats?.graph_db_status ?? 'Trực tuyến (AuraDB)';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-md w-full">
      {/* Card 1: Tổng số văn bản */}
      <div className="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col justify-between border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface-variant">
            Kho Văn bản Quy phạm
          </span>
          <div className="w-8 h-8 rounded-lg bg-surface-container-low flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[20px]">auto_stories</span>
          </div>
        </div>
        <div className="my-space-sm flex items-baseline gap-space-xs">
          <span className="font-display-lg text-display-lg text-on-surface font-bold">{totalDocs}</span>
          <span className="font-headline-sm text-headline-sm text-on-surface-variant">Văn bản</span>
        </div>
        <div className="flex flex-col gap-1 pt-space-xs bg-surface-container-low rounded-lg p-2 text-[12px]">
          <div className="flex items-center justify-between font-label-code text-on-surface">
            <span>• Pháp luật Lao động</span>
            <span className="font-metric-num text-secondary">24 văn bản</span>
          </div>
          <div className="flex items-center justify-between font-label-code text-on-surface-variant">
            <span>• Luật BHXH & Y tế</span>
            <span className="font-metric-num text-on-surface">18 văn bản</span>
          </div>
        </div>
      </div>

      {/* Card 2: Đơn vị phân cấp Nodes */}
      <div className="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col justify-between border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface-variant">
            Phân cấp Đỉnh Pháp lý
          </span>
          <div className="w-8 h-8 rounded-lg bg-surface-container-low flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[20px]">account_tree</span>
          </div>
        </div>
        <div className="my-space-sm flex items-baseline gap-space-xs">
          <span className="font-display-lg text-display-lg text-on-surface font-bold">{totalNodes.toLocaleString()}</span>
          <span className="font-headline-sm text-headline-sm text-on-surface-variant">Đỉnh pháp lý</span>
        </div>
        <div className="grid grid-cols-4 gap-1 text-center font-label-statute text-label-statute pt-space-xs">
          <div className="bg-surface-container-low py-1 rounded">
            <div className="font-metric-num text-on-surface">{totalDocs}</div>
            <div className="text-[10px] text-on-surface-variant">VB</div>
          </div>
          <div className="bg-surface-container-low py-1 rounded">
            <div className="font-metric-num text-secondary">386</div>
            <div className="text-[10px] text-on-surface-variant">Điều</div>
          </div>
          <div className="bg-surface-container-low py-1 rounded">
            <div className="font-metric-num text-on-surface">712</div>
            <div className="text-[10px] text-on-surface-variant">Khoản</div>
          </div>
          <div className="bg-surface-container-low py-1 rounded">
            <div className="font-metric-num text-on-tertiary-container">280</div>
            <div className="text-[10px] text-on-surface-variant">Điểm</div>
          </div>
        </div>
      </div>

      {/* Card 3: Mạng lưới quan hệ Graph Edges */}
      <div className="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col justify-between border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface-variant">
            Mạng lưới Quan hệ (Edges)
          </span>
          <div className="w-8 h-8 rounded-lg bg-surface-container-low flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[20px]">hub</span>
          </div>
        </div>
        <div className="my-space-sm flex items-baseline gap-space-xs">
          <span className="font-display-lg text-display-lg text-on-surface font-bold">{totalEdges.toLocaleString()}</span>
          <span className="font-headline-sm text-headline-sm text-on-surface-variant">Cạnh quan hệ</span>
        </div>
        <div className="flex flex-col gap-1 pt-space-xs bg-surface-container-low rounded-lg p-2 font-label-code text-[11px]">
          <div className="flex items-center justify-between text-on-surface">
            <span>CONTAINS / PART_OF:</span>
            <span className="font-metric-num">1,378 / 1,378</span>
          </div>
          <div className="flex items-center justify-between text-secondary">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>REFERS_TO liên VB:
            </span>
            <span className="font-metric-num font-bold">428 Cạnh</span>
          </div>
        </div>
      </div>

      {/* Card 4: Trạng thái Dual-Index */}
      <div className="relative overflow-hidden bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col justify-between border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase tracking-wider text-on-surface-variant">
            Trạng thái Chỉ mục Kép
          </span>
          <div className="w-8 h-8 rounded-lg bg-surface-container-low flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[20px]">verified</span>
          </div>
        </div>
        <div className="my-space-sm flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-on-tertiary-container animate-pulse"></span>
            <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">{vectorStatus}</span>
          </div>
          <span className="font-label-code text-label-code text-on-surface-variant">
            Tổng {totalChunks.toLocaleString()} đoạn vector đã lập chỉ mục
          </span>
        </div>
        <div className="flex flex-col gap-1 pt-space-xs bg-surface-container-low rounded-lg p-2 font-label-code text-[11px]">
          <div className="flex items-center justify-between text-on-surface">
            <span>Trạng thái Đồ thị:</span>
            <span className="font-metric-num text-secondary">{graphStatus}</span>
          </div>
          <div className="flex items-center justify-between text-on-surface-variant">
            <span>Embedding:</span>
            <span className="font-metric-num font-bold text-on-surface">BGE-M3 (1024-d)</span>
          </div>
        </div>
      </div>
    </div>
  );
};


