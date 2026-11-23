'use client';

import React, { useEffect, useState } from 'react';
import { BookOpen, Check, CheckCircle2, Copy, Download, FileText, MessageSquare, ThumbsDown, ThumbsUp } from 'lucide-react';
import { ChatMessage as ChatMessageType, MessageFeedback as Feedback } from '../../lib/types';
import { api, appendixDocxUrl, chunkFromViewUrl } from '../../lib/api';
import { PipelineTrace } from './PipelineTrace';
import { CitationChip } from './CitationChip';
import { TokenUsage } from './TokenUsage';

interface ChatMessageProps {
  message: ChatMessageType;
  index: number;
}

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

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, index }) => {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(message.feedback ?? null);
  const [feedbackSaving, setFeedbackSaving] = useState(false);
  const [feedbackError, setFeedbackError] = useState(false);

  useEffect(() => {
    setFeedback(message.feedback ?? null);
  }, [message.id, message.feedback]);

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

  const handleCopy = () => {
    navigator.clipboard?.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  // Shown only after the server stored it; a failed save keeps the previous rating.
  const toggleFeedback = async (value: Feedback) => {
    if (feedbackSaving) return;
    const next = feedback === value ? null : value;
    setFeedbackSaving(true);
    setFeedbackError(false);
    try {
      const saved = await api.setMessageFeedback(message.id, { feedback: next });
      setFeedback(saved.feedback ?? null);
    } catch {
      setFeedbackError(true);
    } finally {
      setFeedbackSaving(false);
    }
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
      <div className="text-[15.5px] leading-[1.7] text-[#262521] whitespace-pre-line">
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
              appendix={ev.appendix_id ? { id: ev.appendix_id, chunkId: chunkFromViewUrl(ev.view_url) } : undefined}
            />
          ))}
        </div>
      )}

      {/* Appendix attachments */}
      {message.attachments?.map(item => (
        <div key={item.appendix_id} className="rounded-xl border border-ink/10 bg-paper px-3.5 py-3 space-y-2">
          <div className="flex items-start gap-2">
            <FileText className="w-4 h-4 text-navy shrink-0 mt-1.5" />
            <CitationChip citation={item.title} appendix={{ id: item.appendix_id }} />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[12px] pl-6">
            <span className="text-muted">Phụ lục {item.number} · {item.document_number}{item.forms?.length ? ` · ${item.forms.length} mẫu` : ''}</span>
            <a className="inline-flex items-center gap-1 font-medium text-navy hover:underline" href={appendixDocxUrl(item.appendix_id)} download>
              <Download className="w-3.5 h-3.5" />Tải phụ lục (.docx)
            </a>
          </div>
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
          {feedbackError && <span role="alert" className="text-[11.5px] text-[#B91C1C] mr-1">Chưa lưu được đánh giá</span>}
          <button
            type="button"
            disabled={feedbackSaving}
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
            disabled={feedbackSaving}
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
