'use client';

import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, ChevronDown, Database, Mic, MicOff } from 'lucide-react';
import { api } from '../../lib/api';
import { useChatStore } from '../../stores/chatStore';

// File attachments are hidden until the backend reads them (PDF/DOCX/OCR) as case context;
// sending only a file name made answers look as if the document had been read.
export const ChatInput: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);

  const { sendMessage, isSending } = useChatStore();
  const { selectedDomain, setSelectedDomain } = useChatStore();
  const [scopeMenuOpen, setScopeMenuOpen] = useState(false);
  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const scopeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.listDocuments('all', undefined, undefined, 1)
      .then(page => setDocumentCount(page.total_count ?? 0))
      .catch(() => setDocumentCount(null));
  }, []);

  useEffect(() => {
    if (!scopeMenuOpen) return;
    const handleOutside = (e: MouseEvent) => {
      if (scopeRef.current && !scopeRef.current.contains(e.target as Node)) setScopeMenuOpen(false);
    };
    window.addEventListener('mousedown', handleOutside);
    return () => window.removeEventListener('mousedown', handleOutside);
  }, [scopeMenuOpen]);

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

  const handleSubmit = () => {
    if (isSending) return;
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;
    sendMessage(trimmedQuestion);
    setQuestion('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const scopeOptions = [
    { id: 'all', label: 'Toàn bộ kho số hóa' },
    { id: 'lao_dong', label: 'Pháp luật Lao động' },
  ];
  const activeScopeLabel = scopeOptions.find((o) => o.id === selectedDomain)?.label ?? scopeOptions[0].label;
  const canSend = !isSending && !!question.trim();

  return (
    <div className="px-5 sm:px-8 pb-4 pt-2 shrink-0 bg-white">
      <div className="max-w-[760px] mx-auto relative">
        <div className="rounded-2xl border border-ink/14 bg-paper focus-within:bg-white focus-within:border-navy/45 shadow-[0_2px_12px_rgba(28,27,24,0.04)] transition-colors px-4 pt-3 pb-2.5">
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
            className="w-full resize-none bg-transparent text-[14.5px] text-ink placeholder:text-[#8A867E] focus:outline-none leading-relaxed"
          />

          <div className="mt-2 flex items-center justify-between gap-2">
            <div ref={scopeRef} className="relative flex items-center gap-1.5">
              <button
                onClick={toggleSpeechRecognition}
                className={`p-1.5 rounded-lg transition-colors ${
                  isListening ? 'bg-[#B91C1C] text-white animate-pulse' : 'text-ink-3 hover:bg-stone hover:text-ink'
                }`}
                title={isListening ? 'Đang lắng nghe tiếng Việt... Nhấn để dừng' : 'Nhập liệu bằng giọng nói (Tiếng Việt)'}
                type="button"
              >
                {isListening ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
              </button>

              <button
                type="button"
                onClick={() => setScopeMenuOpen((o) => !o)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-ink/10 hover:border-navy/35 text-[12px] font-medium text-ink-2 transition-colors"
                title="Phạm vi lập luận"
              >
                <Database className="w-3.5 h-3.5 text-navy" />
                <span>{activeScopeLabel}</span>
                {documentCount != null && <span className="text-muted tabular-nums">({documentCount} VB)</span>}
                <ChevronDown className="w-3 h-3 text-muted" />
              </button>

              {scopeMenuOpen && (
                <div className="absolute bottom-9 left-0 z-20 w-64 rounded-xl bg-white border border-ink/12 shadow-lg p-1.5 space-y-0.5">
                  {scopeOptions.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => {
                        setSelectedDomain(option.id);
                        setScopeMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-[12.5px] transition-colors ${
                        option.id === selectedDomain ? 'bg-stone text-navy font-medium' : 'text-ink-2 hover:bg-paper'
                      }`}
                    >
                      <span>{option.label}</span>
                      <span className="text-[11px] font-mono text-muted">{documentCount == null ? '—' : `${documentCount} VB`}</span>
                    </button>
                  ))}
                  <button
                    type="button"
                    disabled
                    className="w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-[12.5px] opacity-50 cursor-not-allowed text-muted"
                  >
                    <span>Luật BHXH & Y tế</span>
                    <span className="text-[11px] font-mono">Chưa nạp</span>
                  </button>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2.5">
              <span className="hidden sm:inline text-[11.5px] text-[#8A867E]">Ctrl + Enter để gửi</span>
              <button
                onClick={handleSubmit}
                disabled={!canSend}
                aria-label="Gửi câu hỏi"
                className={`w-8 h-8 rounded-xl flex items-center justify-center transition-colors ${
                  canSend ? 'bg-navy text-white hover:bg-navy-dark' : 'bg-stone-3 text-[#9A968D] cursor-not-allowed'
                }`}
                type="button"
              >
                {isSending ? (
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <ArrowUp className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>

        <p className="mt-1.5 text-center text-[11.5px] text-[#8A867E]">
          Nội dung trả lời luôn đi kèm trích dẫn từ văn bản pháp luật đã nạp chỉ mục để đối chiếu trực tiếp.
        </p>
      </div>
    </div>
  );
};
