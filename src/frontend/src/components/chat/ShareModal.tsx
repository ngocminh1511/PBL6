'use client';

import React, { useState } from 'react';
import type { ChatMessage, ChatSession } from '../../lib/types';

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  session: ChatSession | undefined;
  sessionId: string | null;
  messages: ChatMessage[];
}

export const ShareModal: React.FC<ShareModalProps> = ({
  isOpen,
  onClose,
  session,
  sessionId,
  messages,
}) => {
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedText, setCopiedText] = useState(false);

  if (!isOpen) return null;

  const currentUrl = typeof window !== 'undefined'
    ? `${window.location.origin}/chat${sessionId ? `?session=${sessionId}` : ''}`
    : '';

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(currentUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      // Fallback
      prompt('Sao chép liên kết:', currentUrl);
    }
  };

  const handleCopyText = async () => {
    const title = session?.title || 'Phiên hỏi đáp pháp luật Việt Nam';
    let summary = `📋 BÁO CÁO PHIÊN TRA CỨU PHÁP LUẬT: ${title}\n`;
    summary += `🔗 Liên kết phiên: ${currentUrl}\n`;
    summary += `⏱️ Thời gian: ${new Date().toLocaleString('vi-VN')}\n\n`;
    summary += `--- NỘI DUNG TRA CỨU ---\n\n`;

    messages.forEach((m, idx) => {
      if (m.role === 'user') {
        summary += `❓ [Câu hỏi ${idx + 1}]:\n${m.content}\n\n`;
      } else {
        summary += `⚖️ [Trả lời từ Trợ lý Pháp lý]:\n${m.content}\n\n`;
        if (m.legal_evidence && m.legal_evidence.length > 0) {
          summary += `📚 [Căn cứ pháp lý trích dẫn]:\n`;
          m.legal_evidence.forEach((e, eIdx) => {
            summary += `  ${eIdx + 1}. ${e.citation || ''} - ${e.meta_de_muc || e.ten || e.source || ''}\n`;
          });
          summary += '\n';
        }
      }
    });

    try {
      await navigator.clipboard.writeText(summary);
      setCopiedText(true);
      setTimeout(() => setCopiedText(false), 2000);
    } catch {
      alert('Không thể sao chép tự động. Vui lòng thử lại.');
    }
  };

  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: session?.title || 'Phiên tra cứu pháp luật Việt Nam',
          text: `Phiên tra cứu pháp luật: ${session?.title || ''}`,
          url: currentUrl,
        });
      } catch {
        // User cancelled share
      }
    } else {
      handleCopyLink();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl shadow-2xl border border-outline-variant/30 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-outline-variant/20 bg-surface-container-low">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center">
              <span className="material-symbols-outlined text-[20px]">share</span>
            </div>
            <div>
              <h2 className="font-headline-sm text-headline-sm text-on-surface font-bold">
                Chia sẻ phiên tra cứu
              </h2>
              <p className="font-label-code text-[11px] text-on-surface-variant">
                Ngữ cảnh làm việc hiện tại ({messages.length} tin nhắn)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-surface-container text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-colors"
            type="button"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Content */}
        <div className="p-4 flex flex-col gap-4">
          {/* Session preview info */}
          <div className="p-3 rounded-xl bg-surface-container-low border border-outline-variant/20 flex flex-col gap-1">
            <span className="font-label-statute text-[11px] text-secondary font-semibold uppercase">
              Tên phiên
            </span>
            <p className="font-body-sm text-body-sm font-medium text-on-surface line-clamp-2">
              {session?.title || 'Phiên hỏi đáp mới'}
            </p>
          </div>

          {/* Link box */}
          <div className="flex flex-col gap-1.5">
            <label className="font-label-statute text-label-statute text-on-surface-variant font-medium">
              Liên kết phiên tra cứu:
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={currentUrl}
                className="flex-1 px-3 py-2 rounded-xl bg-surface-container border border-outline-variant/30 font-label-code text-[12px] text-on-surface select-all focus:outline-none focus:border-secondary"
              />
              <button
                onClick={handleCopyLink}
                className={`px-3 py-2 rounded-xl font-headline-sm text-headline-sm transition-all flex items-center gap-1 shrink-0 ${
                  copiedLink
                    ? 'bg-emerald-600 text-white'
                    : 'bg-secondary text-white hover:opacity-90'
                }`}
                type="button"
              >
                <span className="material-symbols-outlined text-[16px]">
                  {copiedLink ? 'check' : 'content_copy'}
                </span>
                <span>{copiedLink ? 'Đã chép' : 'Chép link'}</span>
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-2 pt-1">
            <button
              onClick={handleCopyText}
              className={`w-full py-2.5 px-4 rounded-xl border font-headline-sm text-body-sm transition-all flex items-center justify-center gap-2 ${
                copiedText
                  ? 'bg-emerald-50 border-emerald-500 text-emerald-700'
                  : 'bg-surface-container hover:bg-surface-container-high border-outline-variant/30 text-on-surface'
              }`}
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">
                {copiedText ? 'check_circle' : 'description'}
              </span>
              <span>{copiedText ? 'Đã sao chép nội dung phiên!' : 'Sao chép văn bản tóm tắt phiên'}</span>
            </button>

            {typeof navigator !== 'undefined' && typeof navigator.share === 'function' && (
              <button
                onClick={handleNativeShare}
                className="w-full py-2.5 px-4 rounded-xl bg-primary text-on-primary font-headline-sm text-body-sm hover:opacity-90 transition-all flex items-center justify-center gap-2 shadow-xs"
                type="button"
              >
                <span className="material-symbols-outlined text-[18px]">ios_share</span>
                <span>Chia sẻ qua ứng dụng khác</span>
              </button>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 bg-surface-container-low border-t border-outline-variant/20 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-body-sm text-body-sm transition-colors"
            type="button"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};

