'use client';

import React, { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import { PipelineTrace as PipelineTraceType } from '../../lib/types';

interface PipelineTraceProps {
  trace: PipelineTraceType;
  executionMs?: number | null;
}

interface StepRow {
  title: string;
  detail: React.ReactNode;
  secondary?: React.ReactNode;
  status: string;
}

export const PipelineTrace: React.FC<PipelineTraceProps> = ({ trace, executionMs }) => {
  const [isOpen, setIsOpen] = useState(false);
  const ms = executionMs ?? trace.execution_time_ms;
  const rewrite = trace.step1_query_rewrite;
  const retrieval = trace.step2_hybrid_retrieval;
  const rerank = trace.step3_rerank;

  const steps: StepRow[] = [
    {
      title: 'Viết lại truy vấn & Giải quyết đại từ',
      detail: rewrite.pronoun_resolved || 'Xử lý đại từ phụ thuộc ngữ cảnh hội thoại.',
      secondary: <>Truy vấn độc lập: &quot;{rewrite.standalone_query}&quot;</>,
      status: rewrite.activated ? 'Tự động kích hoạt' : 'Lượt hỏi đơn lập',
    },
    {
      title: 'Truy vấn kết hợp (Vector kNN + Đồ thị tri thức)',
      detail: (
        <>
          Vector ngữ nghĩa (Qdrant): {retrieval.vector_hits_count} đoạn · Cosine {retrieval.vector_score_range}
          <br />
          Duyệt đồ thị (Neo4j): {retrieval.graph_hops_count} chứng cứ đồ thị
        </>
      ),
      secondary: retrieval.refers_to_targets.length > 0
        ? retrieval.refers_to_targets.join(' • ')
        : 'Không có chứng cứ đồ thị được trả về',
      status: `${retrieval.vector_hits_count + retrieval.graph_hops_count} kết quả`,
    },
    {
      title: 'Tái xếp hạng bằng LLM',
      detail: `Giữ ${rerank.retained_count} đoạn • Loại ${rerank.pruned_count} đoạn`,
      status: 'Chọn theo mức liên quan',
    },
    {
      title: 'Kiểm chứng trích dẫn',
      detail: 'Đối chiếu Điều / Khoản / Điểm',
      status: trace.step4_verification.status,
    },
  ];

  return (
    <div className="rounded-2xl border border-ink/10 bg-paper overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 flex items-center justify-between gap-3 text-left hover:bg-stone/70 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          <CheckCircle2 className="w-4 h-4 text-navy shrink-0" />
          <span className="text-[13px] font-medium text-ink truncate">Tiến trình lập luận pháp lý</span>
          <span className="text-[12px] text-muted tabular-nums hidden sm:inline">
            · {steps.length} bước{ms == null ? '' : ` · ${(ms / 1000).toFixed(2)}s`}
          </span>
        </div>
        <span className="inline-flex items-center gap-1 text-[12px] font-medium text-ink-3 shrink-0">
          <span>{isOpen ? 'Thu gọn' : 'Xem chi tiết'}</span>
          {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </span>
      </button>

      {isOpen && (
        <div className="px-4 pb-4 pt-2 border-t border-ink/8 space-y-3 bg-white">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start justify-between gap-4 py-1.5 border-b last:border-b-0 border-ink/6">
              <div className="flex items-start gap-2.5 min-w-0">
                <span className="font-mono text-[11.5px] font-semibold text-navy mt-0.5 tabular-nums shrink-0">0{i + 1}.</span>
                <div className="min-w-0 space-y-0.5">
                  <div className="text-[13px] font-medium text-ink">{step.title}</div>
                  <div className="text-[12.5px] text-ink-3 leading-relaxed">{step.detail}</div>
                  {step.secondary && (
                    <div className="text-[12px] text-[#6E6B64] font-mono bg-paper px-2.5 py-1.5 rounded-lg mt-1 break-words">
                      {step.secondary}
                    </div>
                  )}
                </div>
              </div>
              <span className="text-[11.5px] font-medium text-ink-3 text-right shrink-0 mt-0.5 max-w-[40%]">{step.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
