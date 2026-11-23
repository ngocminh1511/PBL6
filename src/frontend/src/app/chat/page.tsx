'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Download, Info, PanelLeftOpen, PanelRightClose, PanelRightOpen, Scale, Share2, Sparkles } from 'lucide-react';
import { SessionList } from '../../components/chat/SessionList';
import { ChatMessage } from '../../components/chat/ChatMessage';
import { TokenUsage } from '../../components/chat/TokenUsage';
import { ChatInput } from '../../components/chat/ChatInput';
import { ShareModal } from '../../components/chat/ShareModal';
import { PanelResizer } from '../../components/chat/PanelResizer';
import { CollapsedRail } from '../../components/chat/CollapsedRail';
import { HierarchyTree } from '../../components/inspector/HierarchyTree';
import { GraphView } from '../../components/inspector/GraphView';
import { EvidencePanel } from '../../components/inspector/EvidencePanel';
import { useChatStore } from '../../stores/chatStore';
import { exportSessionToPDF } from '../../lib/exportPdf';

const LEFT_DEFAULT = 276;
const RIGHT_DEFAULT = 400;

const SAMPLE_PROMPTS = [
  'Thời hạn báo trước khi đơn phương chấm dứt hợp đồng lao động không xác định thời hạn là bao nhiêu ngày?',
  'Đối với ngành nghề đặc thù như phi công hoặc người quản lý doanh nghiệp thì thời hạn báo trước quy định thế nào?',
  'Người lao động có quyền đơn phương chấm dứt hợp đồng lao động mà không cần lý do chính đáng hay không?',
];

export default function ChatPage() {
  const {
    messages,
    activeSessionId,
    sessions,
    fetchSessions,
    inspectorTab,
    setInspectorTab,
    isLoading,
    isSending,
    selectedDomain,
  } = useChatStore();

  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [leftWidth, setLeftWidth] = useState(LEFT_DEFAULT);
  const [rightWidth, setRightWidth] = useState(RIGHT_DEFAULT);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, isSending]);

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const scopeLabel = selectedDomain === 'lao_dong' ? 'Pháp luật Lao động' : 'Toàn bộ kho số hóa';

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

  const inspectorTabs: Array<{ tab: typeof inspectorTab; label: string }> = [
    { tab: 'tab-hierarchy', label: 'Cây phân cấp' },
    { tab: 'tab-graph', label: 'Đồ thị tri thức' },
    { tab: 'tab-rerank', label: `Bằng chứng (${evidenceCount})` },
  ];

  const headerIconBtn = 'p-1.5 rounded-lg text-[#6E6B64] hover:text-ink hover:bg-stone transition-colors';

  return (
    <div className="h-screen w-screen flex bg-stone overflow-hidden p-3 text-ink">
      {/* ==================== LEFT: SESSIONS ==================== */}
      {leftOpen ? (
        <>
          <aside
            style={{ width: leftWidth }}
            className="shrink-0 bg-white rounded-2xl border border-ink/8 flex flex-col h-full overflow-hidden"
          >
            <SessionList
              onToggleCollapse={() => setLeftOpen(false)}
              onShareSession={(s) => {
                if (s.id !== activeSessionId) {
                  useChatStore.getState().selectSession(s.id);
                }
                setIsShareModalOpen(true);
              }}
            />
          </aside>
          <PanelResizer
            side="left"
            currentWidth={leftWidth}
            minWidth={220}
            maxWidth={420}
            snapCollapseBelow={165}
            onResize={setLeftWidth}
            onCollapse={() => setLeftOpen(false)}
            onResetWidth={() => setLeftWidth(LEFT_DEFAULT)}
          />
        </>
      ) : (
        <CollapsedRail
          side="left"
          onExpand={() => setLeftOpen(true)}
          onDragExpand={() => {
            setLeftWidth(LEFT_DEFAULT);
            setLeftOpen(true);
          }}
          onNewSession={() => {
            setLeftOpen(true);
            useChatStore.getState().createSession();
          }}
        />
      )}

      {/* ==================== CENTER: CONVERSATION ==================== */}
      <main className="flex-1 min-w-0 bg-white rounded-2xl border border-ink/8 flex flex-col h-full overflow-hidden">
        <div className="h-12 px-4 sm:px-5 border-b border-ink/6 flex items-center justify-between gap-4 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {!leftOpen && (
              <button type="button" onClick={() => setLeftOpen(true)} title="Mở lịch sử tra cứu" className={`${headerIconBtn} shrink-0`}>
                <PanelLeftOpen className="w-4 h-4" />
              </button>
            )}
            <div className="flex items-center gap-2 text-[13.5px] min-w-0">
              <span className="text-muted hidden sm:inline whitespace-nowrap">{scopeLabel}</span>
              <span className="text-[#C9C5BC] hidden sm:inline">/</span>
              <h1 className="font-semibold text-ink truncate">
                {activeSession ? activeSession.title : 'Phiên hỏi đáp mới'}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button type="button" onClick={handleExportPDF} title="Xuất báo cáo PDF phiên này" className={headerIconBtn}>
              <Download className="w-4 h-4" />
            </button>
            <button type="button" onClick={handleShare} title="Chia sẻ phiên tra cứu này" className={headerIconBtn}>
              <Share2 className="w-4 h-4" />
            </button>
            {!rightOpen && (
              <button
                type="button"
                onClick={() => setRightOpen(true)}
                title="Mở cây phân cấp & bằng chứng"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[12px] font-medium text-[#47453F] bg-stone hover:bg-[#EAE7DF] transition-colors"
              >
                <PanelRightOpen className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Tra cứu nguồn</span>
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mx-4 sm:mx-5 mt-3 rounded-xl border border-[#B91C1C]/20 bg-[#FDF2F2] px-4 py-3 text-[13px] text-[#7F1D1D] space-y-2 shrink-0">
            <p role="alert">{error}</p>
            {errorUsage && <TokenUsage usage={errorUsage} />}
          </div>
        )}

        <div className="flex-1 overflow-y-auto legal-scroll px-5 sm:px-8 py-6">
          <div className="max-w-[760px] mx-auto space-y-8">
            {isLoading && messages.length === 0 ? (
              <div className="py-24 flex items-center justify-center gap-2 text-[13.5px] text-ink-3">
                <span className="w-4 h-4 border-2 border-navy border-t-transparent rounded-full animate-spin" />
                <span>Đang tải lịch sử phiên hỏi đáp...</span>
              </div>
            ) : messages.length === 0 ? (
              <div className="py-10 space-y-8">
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-2xl bg-navy/8 text-navy flex items-center justify-center">
                    <Scale className="w-5 h-5" />
                  </div>
                  <h2 className="text-[26px] font-semibold tracking-tight text-ink">
                    Tra cứu & lập luận pháp luật Việt Nam
                  </h2>
                  <p className="text-[14.5px] leading-relaxed text-ink-3 max-w-[56ch]">
                    Đặt câu hỏi bằng ngôn ngữ tự nhiên. Hệ thống đối chiếu trực tiếp từ kho văn bản đã chuẩn hóa, hiển thị đồ thị liên kết và trích dẫn điều khoản kiểm chứng ở khung bên phải.
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {SAMPLE_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      disabled={isSending}
                      onClick={() => useChatStore.getState().sendMessage(prompt)}
                      className="text-left p-4 rounded-2xl border border-ink/10 bg-paper hover:bg-stone hover:border-navy/30 transition-colors space-y-1.5 disabled:opacity-60"
                    >
                      <div className="text-[11.5px] font-medium text-navy">Gợi ý tra cứu 0{idx + 1}</div>
                      <div className="text-[13.5px] font-medium text-ink leading-snug">{prompt}</div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m, idx) => <ChatMessage key={m.id} message={m} index={idx} />)
            )}

            {isSending && (
              <div className="rounded-2xl border border-ink/10 bg-paper p-4 flex items-center gap-3 text-[13.5px] text-ink-2">
                <Sparkles className="w-4 h-4 text-navy animate-spin" />
                <span>Đang truy hồi Vector kNN, duyệt Đồ thị Tri thức và đối chiếu điều khoản...</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <ChatInput />
      </main>

      {/* ==================== RIGHT: INSPECTOR ==================== */}
      {rightOpen ? (
        <>
          <PanelResizer
            side="right"
            currentWidth={rightWidth}
            minWidth={300}
            maxWidth={600}
            snapCollapseBelow={215}
            onResize={setRightWidth}
            onCollapse={() => setRightOpen(false)}
            onResetWidth={() => setRightWidth(RIGHT_DEFAULT)}
          />
          <aside
            style={{ width: rightWidth }}
            className="shrink-0 bg-white rounded-2xl border border-ink/8 flex flex-col h-full overflow-hidden"
          >
            <div className="h-12 px-3 flex items-center justify-between gap-2 border-b border-ink/6 shrink-0">
              <div className="flex items-center gap-1 bg-stone p-1 rounded-xl min-w-0 overflow-x-auto">
                {inspectorTabs.map(({ tab, label }) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setInspectorTab(tab)}
                    className={`px-2.5 py-1 text-[12px] font-medium rounded-lg whitespace-nowrap transition-colors ${
                      inspectorTab === tab
                        ? 'bg-white text-ink shadow-[0_1px_2px_rgba(28,27,24,0.06)]'
                        : 'text-ink-3 hover:text-ink'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button type="button" onClick={() => setRightOpen(false)} title="Thu gọn bảng tra cứu" className={`${headerIconBtn} shrink-0`}>
                <PanelRightClose className="w-4 h-4" />
              </button>
            </div>

            {inspectorTab === 'tab-hierarchy' && <HierarchyTree />}
            {inspectorTab === 'tab-graph' && <GraphView />}
            {inspectorTab === 'tab-rerank' && <EvidencePanel />}
          </aside>
        </>
      ) : (
        <CollapsedRail
          side="right"
          onExpand={() => setRightOpen(true)}
          onDragExpand={() => {
            setRightWidth(RIGHT_DEFAULT);
            setRightOpen(true);
          }}
          onSelectTab={setInspectorTab}
          activeTab={inspectorTab}
          evidenceCount={evidenceCount}
        />
      )}

      <ShareModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        session={activeSession}
        sessionId={activeSessionId}
        messages={messages}
      />

      {toastMessage && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl bg-ink/90 text-white text-[13px] shadow-xl flex items-center gap-2">
          <Info className="w-4 h-4 text-amber-300" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
