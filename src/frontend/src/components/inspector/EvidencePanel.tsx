'use client';

import React from 'react';
import { useChatStore } from '../../stores/chatStore';

export const EvidencePanel: React.FC = () => {
  const { selectedEvidences, messages } = useChatStore();

  const trace = [...messages].reverse().find(message => message.role === 'assistant')?.pipeline_trace;
  return (
    <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
          Hồ sơ Căn cứ Pháp lý
        </span>
        <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-semibold">
          {selectedEvidences.length} chứng cứ giữ lại
        </span>
      </div>

      {/* Retained Evidence List */}
      <div className="flex flex-col gap-2.5">
        {selectedEvidences.length > 0 ? (
          selectedEvidences.map((ev, idx) => (
            <div
              key={ev.chunk_id || idx}
              className="p-3 rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-xs flex flex-col gap-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-surface-container text-secondary font-bold">
                  {ev.citation}
                </span>
                <span className="font-label-code text-label-code text-on-tertiary-container font-bold text-[11px]">
                  Điểm: {ev.score.toFixed(3)}
                </span>
              </div>
              <h4 className="font-headline-sm text-headline-sm text-on-surface line-clamp-1">{ev.ten}</h4>
              <p className="font-body-sm text-body-sm text-on-surface-variant line-clamp-3">
                {ev.text}
              </p>
              {ev.amendments && ev.amendments.length > 0 && (
                <div className="mt-1 p-2 rounded bg-amber-50 border border-amber-200 text-[11px] text-amber-800">
                  <strong>Được sửa đổi bởi:</strong> {ev.amendments.map((a) => a.citation).join(', ')}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="p-space-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-xs font-body-sm text-body-sm text-on-surface-variant">
            Chứng cứ sẽ hiển thị tại đây sau khi có kết quả truy hồi.
          </div>
        )}
      </div>

      {/* Pruned Evidence Ledger (Rose State) */}
      <div className="flex flex-col gap-2 pt-2 border-t border-outline-variant/30">
        <span className="font-label-statute text-label-statute uppercase text-rose-700 font-bold flex items-center gap-1">
          <span className="material-symbols-outlined text-[15px]">filter_alt_off</span>
          Nhật ký Loại trừ bằng chứng:
        </span>

        {trace?.step3_rerank.pruned_citations.length ? trace.step3_rerank.pruned_citations.map((citation, index) =>
          <div key={index} className="p-3 rounded-xl bg-[#FFF1F2] border border-[#FECDD3] flex flex-col gap-1 text-[12px]">
            <span className="text-rose-800 font-semibold line-through">{citation}</span>
            <span className="text-rose-600 italic">Không được giữ lại trong tập chứng cứ.</span>
          </div>) : <p className="font-body-sm text-body-sm text-on-surface-variant">Chưa có dữ liệu loại trừ.</p>}

      </div>
    </div>
  );
};

