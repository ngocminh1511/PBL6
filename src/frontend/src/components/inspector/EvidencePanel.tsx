'use client';

import React from 'react';
import { ArrowUpRight, FilterX } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';

export const EvidencePanel: React.FC = () => {
  const { selectedEvidences, messages, selectedCitation, setSelectedCitation, setInspectorTab } = useChatStore();

  const trace = [...messages].reverse().find(message => message.role === 'assistant')?.pipeline_trace;
  return (
    <div className="flex-1 overflow-y-auto legal-scroll p-3.5 flex flex-col gap-3">
      <div className="flex items-center justify-between px-0.5">
        <span className="text-[11.5px] font-medium text-ink-2">Hồ sơ căn cứ pháp lý</span>
        <span className="font-mono text-[11px] px-2 py-0.5 rounded-md bg-[#DCEFE3] text-[#166534]">
          {selectedEvidences.length} chứng cứ giữ lại
        </span>
      </div>

      {/* Retained Evidence List */}
      <div className="flex flex-col gap-3">
        {selectedEvidences.length > 0 ? (
          selectedEvidences.map((ev, idx) => {
            const highlighted = selectedCitation === ev.citation;
            return (
              <div
                key={ev.chunk_id || idx}
                className={`rounded-2xl border p-3.5 transition-colors ${
                  highlighted ? 'bg-paper border-navy/40' : 'bg-white border-ink/10 hover:border-ink/20'
                }`}
              >
                <h4 className="text-[13px] font-semibold text-ink leading-snug">{ev.citation}</h4>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-[#6E6B64]">
                  {ev.ten && <span className="line-clamp-1">{ev.ten}</span>}
                  {ev.ten && <span aria-hidden="true">·</span>}
                  <span className="font-mono tabular-nums">Điểm {ev.score.toFixed(3)}</span>
                </div>
                <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink-2 line-clamp-4">{ev.text}</p>
                {ev.amendments && ev.amendments.length > 0 && (
                  <div className="mt-2.5 rounded-xl border border-[#9A6B2F]/25 bg-[#FAF7F0] px-3 py-2 text-[11.5px] text-[#473822]">
                    <strong className="font-semibold text-[#7A521E]">Được sửa đổi bởi:</strong> {ev.amendments.map((a) => a.citation).join(', ')}
                  </div>
                )}
                {ev.document_id && (
                  <div className="mt-3 pt-2.5 border-t border-ink/6">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedCitation(ev.citation);
                        setInspectorTab('tab-hierarchy');
                      }}
                      className="inline-flex items-center gap-1 text-[12px] font-medium text-navy hover:underline"
                    >
                      <span>Xem trong Cây phân cấp</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="py-12 text-center text-[13px] text-muted">
            Chứng cứ sẽ hiển thị tại đây sau khi có kết quả truy hồi.
          </div>
        )}
      </div>

      {/* Pruned Evidence Ledger */}
      <div className="flex flex-col gap-2 pt-3 border-t border-ink/8">
        <span className="text-[11.5px] font-medium text-[#9F1239] flex items-center gap-1.5">
          <FilterX className="w-3.5 h-3.5" />
          Nhật ký loại trừ bằng chứng
        </span>

        {trace?.step3_rerank.pruned_citations.length ? trace.step3_rerank.pruned_citations.map((citation, index) =>
          <div key={index} className="rounded-xl border border-[#FECDD3] bg-[#FFF5F6] px-3 py-2 flex flex-col gap-0.5 text-[12px]">
            <span className="text-[#9F1239] font-medium line-through">{citation}</span>
            <span className="text-[#BE123C]/80 italic">Không được giữ lại trong tập chứng cứ.</span>
          </div>) : <p className="text-[12.5px] text-muted">Chưa có dữ liệu loại trừ.</p>}
      </div>
    </div>
  );
};
