'use client';

import React, { useState } from 'react';
import { PipelineTrace as PipelineTraceType } from '../../lib/types';

interface PipelineTraceProps {
  trace: PipelineTraceType;
}

export const PipelineTrace: React.FC<PipelineTraceProps> = ({ trace }) => {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="rounded-xl bg-surface-container-low p-space-md flex flex-col gap-space-md shadow-xs border border-outline-variant/30">
      {/* Trace Toggle Bar */}
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-space-xs">
          <span className="material-symbols-outlined text-secondary text-[20px]">account_tree</span>
          <span className="font-headline-sm text-headline-sm text-on-surface">
            Tiến trình Xử lý Suy luận (Truy vết LexRAG)
          </span>
          <span className="font-label-statute text-label-statute px-2 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed font-semibold">
            {trace.step4_verification.status}
          </span>
        </div>
        <div className="flex items-center gap-1 font-label-code text-label-code text-secondary">
          <span>{isOpen ? 'Thu gọn' : 'Chi tiết 4 bước'}</span>
          <span className="material-symbols-outlined text-[18px]">
            {isOpen ? 'expand_less' : 'expand_more'}
          </span>
        </div>
      </div>

      {/* Trace Accordion Body */}
      {isOpen && (
        <div className="flex flex-col gap-space-md pt-space-xs">
          {/* Step 1: Context Resolution & Query Rewrite */}
          <div className="flex flex-col gap-1.5 p-space-sm rounded-lg bg-surface-container-lowest">
            <div className="flex items-center justify-between">
              <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                1. Viết lại truy vấn & Giải quyết đại từ
              </span>
              <span className="font-label-code text-label-code text-secondary font-semibold">
                {trace.step1_query_rewrite.activated ? 'Tự động kích hoạt (LexRAG Context)' : 'Lượt hỏi đơn lập'}
              </span>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              {trace.step1_query_rewrite.pronoun_resolved || 'Xử lý đại từ phụ thuộc ngữ cảnh hội thoại.'}
            </p>
            <div className="p-space-xs rounded bg-surface-container font-label-code text-label-code text-on-surface flex items-start gap-2">
              <span className="material-symbols-outlined text-secondary text-[16px] shrink-0 mt-0.5">
                prompt_suggestion
              </span>
              <span>
                <strong>Truy vấn độc lập:</strong> "{trace.step1_query_rewrite.standalone_query}"
              </span>
            </div>
          </div>

          {/* Step 2: Hybrid Retrieval */}
          <div className="flex flex-col gap-1.5 p-space-sm rounded-lg bg-surface-container-lowest">
            <div className="flex items-center justify-between">
              <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                2. Truy vấn kết hợp (Vector kNN + Đồ thị tri thức)
              </span>
              <span className="font-metric-num text-metric-num text-on-tertiary-container bg-tertiary-fixed px-1.5 rounded">
                Tích hợp thành công
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-space-xs">
              {/* Vector Pillar */}
              <div className="p-space-xs rounded bg-surface-container flex flex-col gap-1">
                <div className="flex items-center justify-between font-label-statute text-label-statute">
                  <span className="text-on-surface font-semibold">Vector Ngữ nghĩa (Qdrant)</span>
                  <span className="font-metric-num text-metric-num text-secondary">
                    {trace.step2_hybrid_retrieval.vector_hits_count} Đoạn (Chunks)
                  </span>
                </div>
                <span className="font-body-sm text-body-sm text-on-surface-variant text-[11px]">
                  Cosine Sim: {trace.step2_hybrid_retrieval.vector_score_range} • BGE-m3 Embedding
                </span>
              </div>
              {/* Graph Pillar */}
              <div className="p-space-xs rounded bg-surface-container flex flex-col gap-1">
                <div className="flex items-center justify-between font-label-statute text-label-statute">
                  <span className="text-on-surface font-semibold">Duyệt Đồ thị (Neo4j)</span>
                  <span className="font-label-statute text-label-statute text-on-secondary-fixed bg-secondary-fixed px-1 rounded">
                    {trace.step2_hybrid_retrieval.graph_hops_count} Bước nhảy [REFERS_TO]
                  </span>
                </div>
                <span className="font-label-code text-label-code text-on-surface truncate text-[11px]">
                  {trace.step2_hybrid_retrieval.refers_to_targets.length > 0
                    ? trace.step2_hybrid_retrieval.refers_to_targets.join(' • ')
                    : 'Duyệt cấu trúc phân cấp CONTAINS/PART_OF'}
                </span>
              </div>
            </div>
          </div>

          {/* Step 3 & 4: Reranker Pruning & Verification */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-xs">
            <div className="p-space-xs rounded-lg bg-surface-container-lowest flex items-center justify-between">
              <div className="flex flex-col">
                <span className="font-label-statute text-label-statute text-on-surface-variant uppercase font-bold">
                  3. Tái xếp hạng (Cross-Encoder)
                </span>
                <span className="font-body-sm text-body-sm text-on-surface">
                  Giữ {trace.step3_rerank.retained_count} đoạn • Loại {trace.step3_rerank.pruned_count} đoạn
                </span>
              </div>
              <span className="font-metric-num text-metric-num px-2 py-0.5 rounded bg-error-container text-on-error-container font-mono text-[11px]">
                Loại theo ngưỡng điểm
              </span>
            </div>

            <div className="p-space-xs rounded-lg bg-surface-container-lowest flex items-center justify-between">
              <div className="flex flex-col">
                <span className="font-label-statute text-label-statute text-on-surface-variant uppercase font-bold">
                  4. Kiểm chứng trích dẫn
                </span>
                <span className="font-body-sm text-body-sm text-on-surface">
                  Đối chiếu Điều / Khoản / Điểm
                </span>
              </div>
              <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-bold">
                {trace.step4_verification.status}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

