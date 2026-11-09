'use client';

import React, { useState } from 'react';
import { useChatStore } from '../../stores/chatStore';

export const ChatInput: React.FC = () => {
  const [question, setQuestion] = useState('');
  const { sendMessage, isSending } = useChatStore();

  const handleSubmit = () => {
    if (!question.trim() || isSending) return;
    sendMessage(question);
    setQuestion('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-space-md shrink-0 bg-surface-container-lowest shadow-sm border-t border-outline-variant/30">
      {/* Input Cockpit Dock */}
      <div className="p-2.5 rounded-2xl bg-surface-container-low flex flex-col gap-2 focus-within:bg-surface-container-lowest transition-all shadow-xs border border-outline-variant/40">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Đặt câu hỏi về các trường hợp ngoại lệ, chế tài bồi thường, hoặc tra cứu thêm điều khoản..."
          rows={2}
          disabled={isSending}
          className="w-full bg-transparent border-0 focus:outline-none resize-none font-body-md text-body-md text-on-surface placeholder:text-on-surface-variant px-1"
        />

        <div className="flex items-center justify-between pt-1 border-t border-outline-variant/20">
          <div className="flex items-center gap-1.5">
            <button
              className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
              title="Đính kèm tài liệu hồ sơ"
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">attach_file</span>
            </button>
            <button
              className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
              title="Nhập liệu bằng giọng nói"
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">mic</span>
            </button>
            <span className="font-label-code text-label-code text-on-surface-variant px-2 py-0.5 rounded bg-surface-container text-[11px]">
              Ngữ cảnh: BLLĐ 2019 + NĐ 145
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="font-label-code text-label-code text-on-surface-variant hidden sm:inline text-[11px]">
              Ctrl + Enter để gửi
            </span>
            <button
              onClick={handleSubmit}
              disabled={isSending || !question.trim()}
              className="w-9 h-9 rounded-xl bg-primary text-on-primary flex items-center justify-center hover:opacity-90 active:scale-95 transition-all shadow-sm disabled:opacity-50"
              type="button"
            >
              {isSending ? (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
              ) : (
                <span className="material-symbols-outlined text-[20px]">arrow_upward</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
