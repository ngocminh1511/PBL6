'use client';

import React, { useEffect, useState } from 'react';
import { BookOpen, Check, CheckCircle2, Copy, FileText, MessageSquare, ThumbsDown, ThumbsUp } from 'lucide-react';
import { ChatMessage as ChatMessageType } from '../../lib/types';
import { PipelineTrace } from './PipelineTrace';
import { CitationChip } from './CitationChip';
import { TokenUsage } from './TokenUsage';

export type ProseFont = 'sans' | 'serif';
type Feedback = 'up' | 'down';

interface ChatMessageProps {
  message: ChatMessageType;
  index: number;
  proseFont?: ProseFont;
}

/** Answer feedback is kept in this browser only; there is no feedback API yet. */
const FEEDBACK_KEY = 'lexgraph_feedback';

const readFeedback = (id: string): Feedback | null => {
  try {
    const value = JSON.parse(localStorage.getItem(FEEDBACK_KEY) || '{}')[id];
    return value === 'up' || value === 'down' ? value : null;
  } catch {
    return null;
  }
};

const writeFeedback = (id: string, value: Feedback | null) => {
  try {
    const all = JSON.parse(localStorage.getItem(FEEDBACK_KEY) || '{}');
    if (value) all[id] = value;
    else delete all[id];
    localStorage.setItem(FEEDBACK_KEY, JSON.stringify(all));
  } catch {}
};

const formatTime = (dateStr: string) => {
  try {
    const iso = !dateStr.endsWith('Z') && !dateStr.includes('+') ? dateStr + 'Z' : dateStr;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleTimeString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return '';
  }
};

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, index, proseFont = 'sans' }) => {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  useEffect(() => {
    setFeedback(readFeedback(message.id));
  }, [message.id]);

  if (message.role === 'user') {
    const time = formatTime(message.created_at);
    return (
      <div className="flex flex-col items-end gap-1.5">
        <div className="text-[11.5px] text-muted tabular-nums pr-1">
          Lượt hỏi {Math.floor(index / 2) + 1}{time ? ` · ${time}` : ''}
        </div>
        <div className="max-w-[85%] rounded-2xl bg-[#F4F2EC] text-ink px-4 py-3 text-[15px] leading-relaxed whitespace-pre-line">
          {message.content}
        </div>
      </div>
    );
  }

  const check = message.citation_check;
  const verified = !!check?.all_verified && check.verified.length > 0;
  const proseClass = proseFont === 'serif' ? 'font-serif' : 'font-sans';

  const handleCopy = () => {
    navigator.clipboard?.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const toggleFeedback = (value: Feedback) => {
    const next = feedback === value ? null : value;
    setFeedback(next);
    writeFeedback(message.id, next);
  };

  return (
    <article className="space-y-5">
      {/* Explainable pipeline trace */}
      {message.pipeline_trace ? (
        <PipelineTrace trace={message.pipeline_trace} executionMs={message.execution_time_ms} />
      ) : (
        <div className="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3">
          <MessageSquare className="w-3.5 h-3.5 text-navy" />
          <span>Phản hồi trực tiếp</span>
        </div>
      )}

      {message.warnings?.map((warning, i) => (
        <div key={i} className="rounded-xl border border-[#9A6B2F]/25 bg-[#FAF7F0] px-4 py-3 text-[13.5px] leading-relaxed text-[#473822]">
          {warning}
        </div>
      ))}

      {/* Legal answer prose */}
      <div className={`${proseClass} text-[15.5px] leading-[1.7] text-[#262521] whitespace-pre-line`}>
        {message.content}
      </div>

      {/* Citation strip from retrieved evidence */}
      {message.legal_evidence && message.legal_evidence.length > 0 && (
        <div className="pt-2 flex flex-wrap items-center gap-2">
          <span className="text-[12px] font-medium text-muted inline-flex items-center gap-1 mr-1">
            <BookOpen className="w-3.5 h-3.5" />
            Căn cứ đối chiếu:
          </span>
          {message.legal_evidence.map((ev, i) => (
            <CitationChip
              key={ev.chunk_id || i}
              index={i + 1}
              citation={ev.citation}
              href={ev.appendix_id ? '/appendices?' + new URLSearchParams({ appendix_id: ev.appendix_id, chunk_id: ev.chunk_id }).toString() : undefined}
              isGraphRef={ev.source.includes('graph') || ev.source.includes('REFERS_TO')}
            />
          ))}
        </div>
      )}

      {/* Appendix attachments */}
      {message.attachments?.map(item => (
        <div key={item.appendix_id} className="rounded-xl border border-ink/10 bg-paper px-3.5 py-3 space-y-2">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-navy shrink-0" />
            <CitationChip citation={item.title} href={'/appendices?appendix_id=' + encodeURIComponent(item.appendix_id)} />
          </div>
          {item.files && item.files.length > 0 && (
            <div className="flex flex-wrap gap-3 text-[12px]">
              {item.files.map(file => (
                <a key={file.artifact_id} className="font-medium text-navy hover:underline" href={file.download_url}>
                  Tải {file.format.toUpperCase()} nguồn
                </a>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Verification meta */}
      {message.pipeline_trace && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ink-3">
          <span className={`inline-flex items-center gap-1 font-medium ${verified ? 'text-[#166534]' : ''}`}>
            <CheckCircle2 className="w-3.5 h-3.5" />
            {verified ? 'Trích dẫn khớp chứng cứ truy hồi' : check?.unverified.length ? 'Có trích dẫn cần đối chiếu' : 'Chưa có kết quả đối chiếu'}
          </span>
          <span aria-hidden="true">·</span>
          <span className="font-mono tabular-nums">Trích dẫn khớp: {check?.verified.length ?? 0}</span>
          <span aria-hidden="true">·</span>
          <span className="font-mono tabular-nums">
            Thời gian thực thi: {message.execution_time_ms == null ? '—' : message.execution_time_ms + 'ms'}
          </span>
        </div>
      )}

      {/* Response action bar */}
      <div className="pt-2 border-t border-ink/6 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12.5px] font-medium text-ink-3 hover:bg-stone hover:text-ink transition-colors"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-[#166534]" />
              <span>Đã sao chép</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Sao chép</span>
            </>
          )}
        </button>

        <div className="flex items-center gap-1">
          <button
            type="button"
            title="Câu trả lời chính xác"
            aria-pressed={feedback === 'up'}
            onClick={() => toggleFeedback('up')}
            className={`p-1.5 rounded-lg transition-colors ${
              feedback === 'up' ? 'bg-navy/10 text-navy' : 'text-muted hover:bg-stone hover:text-ink'
            }`}
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            title="Cần kiểm tra lại trích dẫn"
            aria-pressed={feedback === 'down'}
            onClick={() => toggleFeedback('down')}
            className={`p-1.5 rounded-lg transition-colors ${
              feedback === 'down' ? 'bg-[#B91C1C]/10 text-[#B91C1C]' : 'text-muted hover:bg-stone hover:text-ink'
            }`}
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <TokenUsage usage={message.token_usage} />
    </article>
  );
};
