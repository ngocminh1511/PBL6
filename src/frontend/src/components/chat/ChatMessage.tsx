'use client';

import React from 'react';
import { ChatMessage as ChatMessageType } from '../../lib/types';
import { PipelineTrace } from './PipelineTrace';
import { CitationChip } from './CitationChip';

interface ChatMessageProps {
  message: ChatMessageType;
  index: number;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, index }) => {
  if (message.role === 'user') {
    return (
      <div className="flex items-start gap-space-sm self-end max-w-3xl">
        <div className="flex flex-col items-end gap-1">
          <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-surface-container text-on-surface-variant">
            Lượt hỏi {Math.floor(index / 2) + 1}
          </span>
          <div className="p-space-md rounded-2xl rounded-tr-xs bg-primary text-on-primary font-body-md text-body-md shadow-xs">
            {message.content}
          </div>
        </div>
        <div className="w-7 h-7 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center shrink-0 mt-1 font-label-statute text-label-statute font-bold">
          LS
        </div>
      </div>
    );
  }

  const check = message.citation_check;
  const verified = !!check?.all_verified && check.verified.length > 0;
  // Assistant response turn
  return (
    <div className="flex items-start gap-space-sm self-start max-w-4xl w-full">
      <div className="w-7 h-7 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-1 shadow-sm text-on-secondary">
        <span className="material-symbols-outlined text-[16px]">neurology</span>
      </div>

      <div className="flex flex-col gap-space-md flex-1 w-full">
        {/* Header Meta */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-space-xs">
            <span className="font-headline-sm text-headline-sm text-on-surface">Hệ thống Pháp luật Việt Nam (Hybrid GraphRAG)</span>
            {message.pipeline_trace && (
              <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-bold">
                {message.pipeline_trace.trace_id}
              </span>
            )}
          </div>
          <span className="font-label-code text-label-code text-on-surface-variant">
            Thời gian thực thi: {message.execution_time_ms == null ? '—' : message.execution_time_ms + 'ms'}
          </span>
        </div>

        {/* Explainable Pipeline Trace Accordion */}
        {message.pipeline_trace && <PipelineTrace trace={message.pipeline_trace} />}

        {/* Final Legal Answer Card */}
        <article className="p-space-lg rounded-2xl bg-surface-container-lowest shadow-md flex flex-col gap-space-md border border-outline-variant/30">
          {/* Verified Status Header Badge */}
          <div className="flex items-center justify-between">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container text-on-surface-variant font-label-statute text-label-statute font-bold">
              <span className="material-symbols-outlined text-[15px]">verified_user</span>
              <span>{verified ? 'TRÍCH DẪN KHỚP CHỨNG CỨ TRUY HỒI' : check?.unverified.length ? 'CÓ TRÍCH DẪN CẦN ĐỐI CHIẾU' : 'CHƯA CÓ KẾT QUẢ ĐỐI CHIẾU'}</span>
            </div>
            <span className="font-label-code text-label-code text-on-surface-variant font-mono">
              Trích dẫn khớp: {check?.verified.length ?? 0}
            </span>
          </div>

          {message.warnings?.map((warning, i) => <p key={i} className="p-space-sm rounded-lg bg-amber-50 text-amber-900 font-body-sm text-body-sm">{warning}</p>)}
          {/* Legal Answer Content */}
          <div className="space-y-4 text-on-surface font-body-md text-body-md leading-relaxed whitespace-pre-line">
            {message.content}
          </div>

          {/* Embedded Interactive Citation Chips from retrieved evidence */}
          {message.legal_evidence && message.legal_evidence.length > 0 && (
            <div className="pt-2 border-t border-outline-variant/30 flex flex-col gap-1.5">
              <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Căn cứ pháp lý trích dẫn:
              </span>
              <div className="flex flex-wrap gap-2">
                {message.legal_evidence.map((ev, i) => (
                  <CitationChip
                    key={ev.chunk_id || i}
                    citation={ev.citation}
                    href={ev.appendix_id ? '/appendices?' + new URLSearchParams({ appendix_id: ev.appendix_id, chunk_id: ev.chunk_id }).toString() : undefined}
                    isGraphRef={ev.source.includes('graph') || ev.source.includes('REFERS_TO')}
                  />
                ))}
              </div>
            </div>
          )}

          {message.attachments?.map(item => <div key={item.appendix_id} className="p-space-sm rounded-xl bg-surface-container-low border border-outline-variant/30">
            <CitationChip citation={item.title} href={'/appendices?appendix_id=' + encodeURIComponent(item.appendix_id)} />
            <div className="flex flex-wrap gap-space-md mt-space-sm font-label-code text-label-code">{item.files?.map(file => <a key={file.artifact_id} className="text-secondary underline" href={file.download_url}>Tải {file.format.toUpperCase()} nguồn</a>)}</div>
          </div>)}
          {/* Card Meta Actions */}
          <div className="pt-space-xs flex items-center justify-between font-label-code text-label-code text-on-surface-variant border-t border-outline-variant/20">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigator.clipboard.writeText(message.content)}
                className="flex items-center gap-1 hover:text-on-surface transition-colors"
                type="button"
              >
                <span className="material-symbols-outlined text-[16px]">content_copy</span> Sao chép luận cứ
              </button>
              <button disabled title="Chức năng chưa được triển khai" className="flex items-center gap-1 opacity-50" type="button">
                <span className="material-symbols-outlined text-[16px]">bookmark_add</span> Lưu vào hồ sơ án
              </button>
            </div>
            <div className="flex items-center gap-1">
              <span className="material-symbols-outlined text-[16px] text-on-tertiary-container">verified</span>
              <span>Chứng cứ truy hồi của phiên</span>
            </div>
          </div>
        </article>
      </div>
    </div>
  );
};

