'use client';

import React, { useRef, useState } from 'react';
import { useChatStore } from '../../stores/chatStore';

export const ChatInput: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  const { sendMessage, isSending } = useChatStore();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      // Chỉ nhận đúng 1 file đơn lẻ
      const file = e.target.files[0];
      if (file.size > 25 * 1024 * 1024) {
        alert('Dung lượng file vượt quá giới hạn cho phép (tối đa 25MB).');
        return;
      }
      setAttachedFile(file);
      // Reset input value để có thể chọn lại nếu muốn
      e.target.value = '';
    }
  };

  const removeAttachedFile = () => {
    setAttachedFile(null);
  };

  const toggleSpeechRecognition = () => {
    if (typeof window === 'undefined') return;

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Trình duyệt hiện tại chưa hỗ trợ nhận diện giọng nói (Web Speech API). Vui lòng sử dụng Google Chrome hoặc Microsoft Edge.');
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'vi-VN';
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        setIsListening(true);
        setSpeechError(null);
      };

      recognition.onresult = (event: any) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          }
        }
        if (finalTranscript) {
          setQuestion((prev) => (prev ? `${prev.trim()} ${finalTranscript}` : finalTranscript));
        }
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
          alert('Vui lòng cấp quyền truy cập Microphone cho trình duyệt để sử dụng tính năng này.');
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error('Speech recognition start failed:', err);
      setIsListening(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async () => {
    if (isSending) return;
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion && !attachedFile) return;

    let finalPrompt = trimmedQuestion;

    if (attachedFile) {
      const isTextFile = /\.(txt|md|json|csv|html|xml|log)$/i.test(attachedFile.name);
      if (isTextFile) {
        try {
          const textContent = await attachedFile.text();
          const truncatedText = textContent.slice(0, 10000);
          finalPrompt = `[Tài liệu đính kèm: ${attachedFile.name}]\n--- NỘI DUNG TÀI LIỆU ---\n${truncatedText}\n-------------------------\n\n${trimmedQuestion || 'Hãy đọc và phân tích nội dung tài liệu đính kèm trên theo quy định pháp luật.'}`;
        } catch {
          finalPrompt = `[Tài liệu đính kèm: ${attachedFile.name} (${formatFileSize(attachedFile.size)})]\n\n${trimmedQuestion || 'Hãy phân tích tài liệu này theo quy định pháp luật.'}`;
        }
      } else {
        finalPrompt = `[Tài liệu đính kèm: ${attachedFile.name} (${formatFileSize(attachedFile.size)})]\n\n${trimmedQuestion || 'Hãy phân tích nội dung hồ sơ đính kèm này.'}`;
      }
    }

    sendMessage(finalPrompt);
    setQuestion('');
    setAttachedFile(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-space-md shrink-0 bg-surface-container-lowest shadow-sm border-t border-outline-variant/30">
      {/* Hidden File Input (Single file only) */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
        accept=".pdf,.doc,.docx,.txt,.md,.json,.csv,.rtf,image/*"
      />

      {/* Input Cockpit Dock */}
      <div className="p-2.5 rounded-2xl bg-surface-container-low flex flex-col gap-2 focus-within:bg-surface-container-lowest transition-all shadow-xs border border-outline-variant/40">
        {/* Single File Attachment Preview Chip */}
        {attachedFile && (
          <div className="flex items-center gap-2 p-2 rounded-xl bg-surface-container border border-secondary/30 self-start max-w-full animate-fadeIn">
            <span className="material-symbols-outlined text-secondary text-[20px]">
              {/\.pdf$/i.test(attachedFile.name) ? 'picture_as_pdf' : 'description'}
            </span>
            <div className="flex flex-col min-w-0 pr-1">
              <span className="font-body-sm text-[12px] font-medium text-on-surface truncate max-w-[260px]">
                {attachedFile.name}
              </span>
              <span className="font-label-code text-[10px] text-on-surface-variant">
                {formatFileSize(attachedFile.size)} • 1 file đơn lẻ
              </span>
            </div>
            <button
              onClick={removeAttachedFile}
              className="w-6 h-6 rounded-full hover:bg-surface-container-high text-on-surface-variant hover:text-red-500 flex items-center justify-center transition-colors ml-1"
              title="Gỡ bỏ tài liệu này"
              type="button"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        )}

        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isListening
              ? '🎤 Đang lắng nghe bạn nói tiếng Việt... Hãy đặt câu hỏi.'
              : 'Đặt câu hỏi về các trường hợp ngoại lệ, chế tài bồi thường, hoặc tra cứu thêm điều khoản...'
          }
          rows={2}
          disabled={isSending}
          maxLength={4000}
          className="w-full bg-transparent border-0 focus:outline-none resize-none font-body-md text-body-md text-on-surface placeholder:text-on-surface-variant px-1"
        />

        <div className="flex items-center justify-between pt-1 border-t border-outline-variant/20">
          <div className="flex items-center gap-1.5">
            {/* Attach Single File Button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className={`p-1.5 rounded-lg transition-colors flex items-center justify-center ${
                attachedFile
                  ? 'bg-secondary/15 text-secondary font-bold'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
              title={attachedFile ? 'Đã đính kèm 1 file (bấm để đổi file khác)' : 'Đính kèm tài liệu hồ sơ (1 file đơn lẻ)'}
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">attach_file</span>
            </button>

            {/* Microphone Button */}
            <button
              onClick={toggleSpeechRecognition}
              className={`p-1.5 rounded-lg transition-all flex items-center justify-center ${
                isListening
                  ? 'bg-red-500 text-white animate-pulse shadow-sm shadow-red-500/30'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
              title={isListening ? 'Đang lắng nghe tiếng Việt... Nhấn để dừng' : 'Nhập liệu bằng giọng nói (Tiếng Việt)'}
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">
                {isListening ? 'mic' : 'mic_none'}
              </span>
            </button>

            <span className="font-label-code text-label-code text-on-surface-variant px-2 py-0.5 rounded bg-surface-container text-[11px]">
              Phạm vi: dữ liệu Lao động
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="font-label-code text-label-code text-on-surface-variant hidden sm:inline text-[11px]">
              Ctrl + Enter để gửi
            </span>
            <button
              onClick={handleSubmit}
              disabled={isSending || (!question.trim() && !attachedFile)}
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

