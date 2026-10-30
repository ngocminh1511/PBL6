'use client';

import React from 'react';
import { useChatStore } from '../../stores/chatStore';
import { RetrievalMode } from '../../lib/types';

export const SessionList: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    selectSession,
    createSession,
    selectedDomain,
    setSelectedDomain,
    selectedRetrievalMode,
    setSelectedRetrievalMode,
  } = useChatStore();

  return (
    <aside className="w-[280px] shrink-0 bg-surface-container-low flex flex-col justify-between overflow-hidden shadow-sm border-r border-outline-variant/30">
      <div className="p-space-md flex flex-col gap-space-md overflow-y-auto">
        {/* New Session Action Button */}
        <button
          onClick={() => createSession()}
          className="w-full flex items-center justify-center gap-space-xs py-2.5 px-space-md rounded-xl bg-primary text-on-primary font-headline-sm text-headline-sm hover:opacity-90 active:scale-[0.98] transition-all shadow-sm"
          type="button"
        >
          <span className="material-symbols-outlined text-[18px]">add_circle</span>
          <span>Tạo phiên hỏi đáp mới</span>
        </button>

        {/* Session History (Lịch sử đa lượt) */}
        <div className="flex flex-col gap-space-xs">
          <div className="flex items-center justify-between px-1">
            <span className="font-label-statute text-label-statute uppercase text-on-surface-variant tracking-wider">
              Lịch sử tra cứu gần đây
            </span>
            <span className="font-metric-num text-metric-num text-on-surface-variant">
              {sessions.length} phiên
            </span>
          </div>

          <div className="flex flex-col gap-1.5 max-h-[220px] overflow-y-auto pr-1">
            {sessions.map((s) => {
              const isActive = s.id === activeSessionId;
              return (
                <div
                  key={s.id}
                  onClick={() => selectSession(s.id)}
                  className={`p-space-sm rounded-xl cursor-pointer transition-all flex flex-col gap-1 ${
                    isActive
                      ? 'bg-surface-container-lowest shadow-sm border-l-4 border-secondary'
                      : 'bg-surface-container hover:bg-surface-container-high'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`font-label-statute text-label-statute px-1.5 py-0.5 rounded font-semibold ${
                        isActive
                          ? 'bg-secondary-fixed text-on-secondary-fixed'
                          : 'bg-surface-variant text-on-surface-variant'
                      }`}
                    >
                      {s.domain === 'lao_dong' ? 'Lao động' : s.domain === 'bhxh' ? 'BHXH' : 'Tổng hợp'}
                    </span>
                    <span className="font-label-code text-label-code text-on-surface-variant text-[11px]">
                      {new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="font-headline-sm text-headline-sm text-on-surface line-clamp-1 leading-snug">
                    {s.title}
                  </p>
                  <div className="flex items-center gap-space-xs text-on-surface-variant font-body-sm text-body-sm">
                    <span className="material-symbols-outlined text-[14px] text-secondary">forum</span>
                    <span>{s.message_count || 2} lượt hỏi • Dấu vết truy vấn</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Domain Filter (Bộ lọc lĩnh vực) */}
        <div className="flex flex-col gap-space-xs pt-space-xs">
          <span className="font-label-statute text-label-statute uppercase text-on-surface-variant tracking-wider px-1">
            Phạm vi lập luận
          </span>
          <div className="flex flex-col gap-1 bg-surface-container p-1 rounded-xl">
            <label className="flex items-center justify-between p-2 rounded-lg bg-surface-container-lowest shadow-xs cursor-pointer">
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="domain"
                  checked={selectedDomain === 'all'}
                  onChange={() => setSelectedDomain('all')}
                  className="accent-secondary h-3.5 w-3.5"
                />
                <span className="font-body-sm text-body-sm font-medium text-on-surface">Toàn bộ kho số hóa</span>
              </div>
              <span className="font-metric-num text-metric-num text-on-surface-variant bg-surface-variant px-1.5 rounded">
                42 VB
              </span>
            </label>

            <label className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-container-high cursor-pointer transition-colors">
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="domain"
                  checked={selectedDomain === 'lao_dong'}
                  onChange={() => setSelectedDomain('lao_dong')}
                  className="accent-secondary h-3.5 w-3.5"
                />
                <span className="font-body-sm text-body-sm text-on-surface">Pháp luật Lao động</span>
              </div>
              <span className="font-metric-num text-metric-num text-on-surface-variant">24 VB</span>
            </label>

            <label className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-container-high cursor-pointer transition-colors">
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="domain"
                  checked={selectedDomain === 'bhxh'}
                  onChange={() => setSelectedDomain('bhxh')}
                  className="accent-secondary h-3.5 w-3.5"
                />
                <span className="font-body-sm text-body-sm text-on-surface">Luật BHXH & Y tế</span>
              </div>
              <span className="font-metric-num text-metric-num text-on-surface-variant">18 VB</span>
            </label>
          </div>
        </div>

        {/* Retrieval Mode (Ablation Configuration) */}
        <div className="flex flex-col gap-space-xs pt-space-xs">
          <div className="flex items-center justify-between px-1">
            <span className="font-label-statute text-label-statute uppercase text-on-surface-variant tracking-wider">
              Cơ chế Thử nghiệm (Ablation)
            </span>
            <span className="font-label-statute text-label-statute text-on-tertiary-container bg-tertiary-fixed px-1.5 py-0.5 rounded font-semibold">
              Tối ưu hóa
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            {/* Mode 1 */}
            <label
              onClick={() => setSelectedRetrievalMode('hybrid')}
              className={`p-2.5 rounded-xl flex flex-col gap-1 cursor-pointer transition-all ${
                selectedRetrievalMode === 'hybrid'
                  ? 'bg-surface-container-lowest shadow-sm border border-secondary/30'
                  : 'bg-surface-container hover:bg-surface-container-high'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    name="retrieval_mode"
                    checked={selectedRetrievalMode === 'hybrid'}
                    onChange={() => setSelectedRetrievalMode('hybrid')}
                    className="accent-secondary h-3.5 w-3.5"
                  />
                  <span className="font-headline-sm text-headline-sm text-on-surface">Hybrid GraphRAG</span>
                </div>
                <span className="font-label-statute text-label-statute bg-secondary-fixed text-on-secondary-fixed px-1 rounded">
                  Đề xuất
                </span>
              </div>
              <span className="font-label-code text-label-code text-on-surface-variant pl-5 text-[11px]">
                Vector kNN + REFERS_TO Tri thức
              </span>
            </label>

            {/* Mode 2 */}
            <label
              onClick={() => setSelectedRetrievalMode('vector_only')}
              className={`p-2 rounded-xl flex items-center gap-2 cursor-pointer transition-colors ${
                selectedRetrievalMode === 'vector_only'
                  ? 'bg-surface-container-lowest shadow-sm border border-secondary/30'
                  : 'bg-surface-container hover:bg-surface-container-high'
              }`}
            >
              <input
                type="radio"
                name="retrieval_mode"
                checked={selectedRetrievalMode === 'vector_only'}
                onChange={() => setSelectedRetrievalMode('vector_only')}
                className="accent-secondary h-3.5 w-3.5"
              />
              <div className="flex flex-col">
                <span className="font-body-sm text-body-sm text-on-surface">Chỉ truy vấn Vector</span>
                <span className="font-label-code text-label-code text-on-surface-variant text-[11px]">
                  Đường cơ sở • Không duyệt đồ thị
                </span>
              </div>
            </label>

            {/* Mode 3 */}
            <label
              onClick={() => setSelectedRetrievalMode('graph_only')}
              className={`p-2 rounded-xl flex items-center gap-2 cursor-pointer transition-colors ${
                selectedRetrievalMode === 'graph_only'
                  ? 'bg-surface-container-lowest shadow-sm border border-secondary/30'
                  : 'bg-surface-container hover:bg-surface-container-high'
              }`}
            >
              <input
                type="radio"
                name="retrieval_mode"
                checked={selectedRetrievalMode === 'graph_only'}
                onChange={() => setSelectedRetrievalMode('graph_only')}
                className="accent-secondary h-3.5 w-3.5"
              />
              <div className="flex flex-col">
                <span className="font-body-sm text-body-sm text-on-surface">Chỉ Đồ thị Tri thức</span>
                <span className="font-label-code text-label-code text-on-surface-variant text-[11px]">
                  Đường cơ sở • Tra cứu thực thể thuần túy
                </span>
              </div>
            </label>
          </div>
        </div>
      </div>

      {/* Left Column Footer */}
      <div className="p-space-sm bg-surface-container text-on-surface-variant flex items-center justify-between font-label-statute text-label-statute border-t border-outline-variant/30">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-on-tertiary-container animate-pulse"></span>
          <span>Chỉ mục: 42 Văn bản</span>
        </div>
        <span className="font-metric-num text-metric-num">v2.4.8 (Neo4j+Qdrant)</span>
      </div>
    </aside>
  );
};

