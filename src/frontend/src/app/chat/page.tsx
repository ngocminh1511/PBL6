'use client';

import React, { useEffect, useState } from 'react';
import { SessionList } from '../../components/chat/SessionList';
import { ChatMessage } from '../../components/chat/ChatMessage';
import { TokenUsage } from '../../components/chat/TokenUsage';
import { ChatInput } from '../../components/chat/ChatInput';
import { ShareModal } from '../../components/chat/ShareModal';
import { HierarchyTree } from '../../components/inspector/HierarchyTree';
import { GraphView } from '../../components/inspector/GraphView';
import { EvidencePanel } from '../../components/inspector/EvidencePanel';
import { useChatStore } from '../../stores/chatStore';
import { exportSessionToPDF } from '../../lib/exportPdf';

export default function ChatPage() {
  const {
    messages,
    activeSessionId,
    sessions,
    fetchSessions,
    inspectorTab,
    setInspectorTab,
    isLoading,
  } = useChatStore();

  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  useEffect(() => {
    fetchSessions().then(() => {
      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search);
        const sessionParam = params.get('session') || params.get('session_id');
        if (sessionParam) {
          useChatStore.getState().selectSession(sessionParam);
        }
      }
    });
  }, [fetchSessions]);

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  const handleExportPDF = () => {
    if (messages.length === 0) {
      showToast('Phiên làm việc hiện tại chưa có nội dung trao đổi để xuất báo cáo.');
      return;
    }
    exportSessionToPDF(activeSession, activeSessionId, messages);
  };

  const handleShare = () => {
    if (messages.length === 0) {
      showToast('Chưa có nội dung trao đổi trong phiên để chia sẻ.');
      return;
    }
    setIsShareModalOpen(true);
  };

  const error = useChatStore(state => state.error);
  const errorUsage = useChatStore(state => state.errorTokenUsage);
  const evidenceCount = useChatStore(state => state.selectedEvidences.length);

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-row overflow-hidden bg-surface text-on-surface">
      {/* ==================== CỘT TRÁI: LEGAL CONTEXT & SESSIONS ==================== */}
      <div className={`relative flex flex-col shrink-0 transition-all duration-300 ease-in-out ${leftOpen ? 'w-[280px]' : 'w-12'} bg-surface-container-low border-r border-outline-variant/30 shadow-sm overflow-hidden`}>
        {/* Nội dung khi thu gọn */}
        {!leftOpen && (
          <div className="flex flex-col items-center py-3 gap-3 w-full">
            <button
              onClick={() => setLeftOpen(true)}
              className="w-8 h-8 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-all shadow-xs border border-outline-variant/30"
              title="Mở rộng thanh bên"
              type="button"
            >
              <span className="material-symbols-outlined text-[16px]">chevron_right</span>
            </button>
            <button
              onClick={() => { setLeftOpen(true); useChatStore.getState().createSession(); }}
              className="w-8 h-8 rounded-xl text-white flex items-center justify-center shadow-sm hover:opacity-95 transition-all"
              style={{ background: 'linear-gradient(135deg, #1565c0 0%, #0288d1 60%, #00acc1 100%)' }}
              title="Tạo phiên hỏi đáp mới"
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">add</span>
            </button>
            <div className="w-5 h-px bg-outline-variant/30 my-1" />
            <button
              onClick={() => setLeftOpen(true)}
              className="w-8 h-8 rounded-xl hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-all"
              title="Lịch sử phiên (Bấm để mở)"
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">history</span>
            </button>
          </div>
        )}
        {/* Nội dung đầy đủ khi mở */}
        {leftOpen && (
          <SessionList
            onToggleCollapse={() => setLeftOpen(false)}
            onShareSession={(s) => {
              if (s.id !== activeSessionId) {
                useChatStore.getState().selectSession(s.id);
              }
              setIsShareModalOpen(true);
            }}
          />
        )}
      </div>

      {/* ==================== CỘT GIỮA: MULTI-TURN SYNTHESIS & REASONING (FLEX-1) ==================== */}
      <main className="flex-1 flex flex-col bg-surface-container-lowest overflow-hidden shadow-xs border-r border-outline-variant/30">
        {/* Session Workspace Header Bar */}
        <header className="h-14 px-space-lg flex items-center justify-between shrink-0 bg-surface-container-lowest shadow-xs border-b border-outline-variant/30">
          <div className="flex items-center gap-space-sm min-w-0">
            <div className="w-2 h-2 rounded-full bg-secondary shrink-0"></div>
            <h1 className="font-headline-md text-headline-md text-on-surface truncate">
              {activeSession ? activeSession.title : 'Phiên hỏi đáp mới'}
            </h1>
          </div>

          <div className="flex items-center gap-space-xs shrink-0">
            <button
              onClick={handleExportPDF}
              className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-secondary transition-colors"
              title="Xuất báo cáo PDF phiên này"
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">download</span>
            </button>
            <button
              onClick={handleShare}
              className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-secondary transition-colors"
              title="Chia sẻ phiên tra cứu này"
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">share</span>
            </button>
          </div>
        </header>

        {error && <div className="p-3 bg-red-50 text-red-800 text-sm space-y-2">
          <p role="alert">{error}</p>
          {errorUsage && <TokenUsage usage={errorUsage} />}
        </div>}
        {/* Scrollable Multi-turn Message Stream */}
        <div className="flex-1 overflow-y-auto px-space-lg py-space-md flex flex-col gap-space-lg">
          {isLoading && messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-on-surface-variant">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 border-2 border-secondary border-t-transparent rounded-full animate-spin"></span>
                <span>Đang tải lịch sử phiên hỏi đáp...</span>
              </div>
            </div>
          ) : messages.length === 0 ? (
            /* Interactive Welcome Prompt when session is empty */
            <div className="flex flex-col items-center justify-center my-auto py-12 px-space-md text-center max-w-2xl mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-secondary/10 text-secondary flex items-center justify-center mb-4 shadow-sm border border-secondary/20">
                <span className="material-symbols-outlined text-[32px]">account_balance</span>
              </div>
              <h2 className="font-headline-lg text-headline-lg text-on-surface mb-6 font-bold tracking-tight">
                Hệ thống Hỏi đáp &amp; Tra cứu Pháp luật Việt Nam
              </h2>

              <div className="w-full flex flex-col gap-2.5 text-left">
                <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold tracking-wider px-1">
                  Chọn câu hỏi tình huống thực tế để kiểm tra suy luận:
                </span>
                {[
                  'Thời hạn báo trước khi đơn phương chấm dứt hợp đồng lao động không xác định thời hạn là bao nhiêu ngày?',
                  'Đối với ngành nghề đặc thù như phi công hoặc người quản lý doanh nghiệp thì thời hạn báo trước quy định thế nào?',
                  'Người lao động có quyền đơn phương chấm dứt hợp đồng lao động mà không cần lý do chính đáng hay không?'
                ].map((samplePrompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => useChatStore.getState().sendMessage(samplePrompt)}
                    className="p-3.5 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-body-sm text-body-sm transition-all flex items-center justify-between group shadow-xs border border-outline-variant/30 text-left"
                  >
                    <span className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-secondary text-[18px]">gavel</span>
                      <span>{samplePrompt}</span>
                    </span>
                    <span className="material-symbols-outlined text-on-surface-variant group-hover:text-secondary text-[18px] transition-colors shrink-0 ml-2">
                      arrow_forward
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, idx) => <ChatMessage key={m.id} message={m} index={idx} />)
          )}
        </div>

        {/* Input Bar */}
        <ChatInput />
      </main>

      {/* ==================== CỘT PHẢI: CONTEXT & EVIDENTIARY INSPECTOR ==================== */}
      <div className={`relative flex flex-col shrink-0 transition-all duration-300 ease-in-out ${rightOpen ? 'w-[440px]' : 'w-12'} bg-surface-container-low overflow-hidden shadow-sm`}>
        {/* Nội dung khi thu gọn */}
        {!rightOpen && (
          <div className="flex flex-col items-center py-3 gap-2.5 w-full">
            <button
              onClick={() => setRightOpen(true)}
              className="w-8 h-8 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-all shadow-xs border border-outline-variant/30"
              title="Mở rộng thanh kiểm tra"
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">chevron_left</span>
            </button>
            <div className="w-5 h-px bg-outline-variant/30 my-1" />
            <button
              onClick={() => {
                setRightOpen(true);
                setInspectorTab('tab-hierarchy');
              }}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all ${inspectorTab === 'tab-hierarchy'
                  ? 'bg-surface-container-highest text-secondary shadow-xs border border-secondary/40'
                  : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
                }`}
              title="Cây Phân cấp (Bấm để mở)"
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">account_tree</span>
            </button>
            <button
              onClick={() => {
                setRightOpen(true);
                setInspectorTab('tab-graph');
              }}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all ${inspectorTab === 'tab-graph'
                  ? 'bg-surface-container-highest text-secondary shadow-xs border border-secondary/40'
                  : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
                }`}
              title="Đồ thị Tri thức (Bấm để mở)"
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">hub</span>
            </button>
            <button
              onClick={() => {
                setRightOpen(true);
                setInspectorTab('tab-rerank');
              }}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all relative ${inspectorTab === 'tab-rerank'
                  ? 'bg-surface-container-highest text-secondary shadow-xs border border-secondary/40'
                  : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
                }`}
              title={`Bằng chứng (${evidenceCount}) (Bấm để mở)`}
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">fact_check</span>
              {evidenceCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-0.5 rounded-full bg-secondary text-white text-[9px] flex items-center justify-center font-bold">
                  {evidenceCount}
                </span>
              )}
            </button>
          </div>
        )}
        {/* Nội dung đầy đủ khi mở */}
        {rightOpen && (
          <>
            {/* Inspector Tabs Bar */}
            <nav className="h-14 px-space-md pl-11 shrink-0 bg-surface-container-lowest flex items-center justify-between gap-1 shadow-xs border-b border-outline-variant/30">
              <button
                onClick={() => setRightOpen(false)}
                className="absolute top-3.5 left-2.5 z-10 w-7 h-7 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-all shadow-xs border border-outline-variant/30"
                title="Thu gọn thanh kiểm tra"
                type="button"
              >
                <span className="material-symbols-outlined text-[16px]">chevron_right</span>
              </button>
              <button
                onClick={() => setInspectorTab('tab-hierarchy')}
                className={`flex-1 py-2 rounded-lg font-headline-sm text-headline-sm text-center transition-all ${inspectorTab === 'tab-hierarchy'
                    ? 'bg-surface-container text-on-surface shadow-xs font-bold'
                    : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                  }`}
              >
                Cây Phân cấp
              </button>
              <button
                onClick={() => setInspectorTab('tab-graph')}
                className={`flex-1 py-2 rounded-lg font-headline-sm text-headline-sm text-center transition-all ${inspectorTab === 'tab-graph'
                    ? 'bg-surface-container text-on-surface shadow-xs font-bold'
                    : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                  }`}
              >
                Đồ thị Tri thức
              </button>
              <button
                onClick={() => setInspectorTab('tab-rerank')}
                className={`flex-1 py-2 rounded-lg font-headline-sm text-headline-sm text-center transition-all ${inspectorTab === 'tab-rerank'
                    ? 'bg-surface-container text-on-surface shadow-xs font-bold'
                    : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                  }`}
              >
                Bằng chứng ({evidenceCount})
              </button>
            </nav>

            {/* Tab Content Rendering */}
            {inspectorTab === 'tab-hierarchy' && <HierarchyTree />}
            {inspectorTab === 'tab-graph' && <GraphView />}
            {inspectorTab === 'tab-rerank' && <EvidencePanel />}
          </>
        )}
      </div>

      {/* Share Modal */}
      <ShareModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        session={activeSession}
        sessionId={activeSessionId}
        messages={messages}
      />

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl bg-slate-900/90 text-white font-body-sm text-body-sm shadow-xl border border-slate-700/60 flex items-center gap-2 animate-fadeIn">
          <span className="material-symbols-outlined text-amber-400 text-[18px]">info</span>
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
