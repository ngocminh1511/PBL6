'use client';

import React, { useEffect } from 'react';
import { SessionList } from '../../components/chat/SessionList';
import { ChatMessage } from '../../components/chat/ChatMessage';
import { ChatInput } from '../../components/chat/ChatInput';
import { HierarchyTree } from '../../components/inspector/HierarchyTree';
import { GraphView } from '../../components/inspector/GraphView';
import { EvidencePanel } from '../../components/inspector/EvidencePanel';
import { useChatStore } from '../../stores/chatStore';

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

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-row overflow-hidden bg-surface text-on-surface">
      {/* ==================== CỘT TRÁI: LEGAL CONTEXT & SESSIONS (280px) ==================== */}
      <SessionList />

      {/* ==================== CỘT GIỮA: MULTI-TURN SYNTHESIS & REASONING (FLEX-1) ==================== */}
      <main className="flex-1 flex flex-col bg-surface-container-lowest overflow-hidden shadow-xs border-r border-outline-variant/30">
        {/* Session Workspace Header Bar */}
        <header className="h-14 px-space-lg flex items-center justify-between shrink-0 bg-surface-container-lowest shadow-xs border-b border-outline-variant/30">
          <div className="flex items-center gap-space-sm min-w-0">
            <div className="w-2 h-2 rounded-full bg-secondary shrink-0"></div>
            <h1 className="font-headline-md text-headline-md text-on-surface truncate">
              {activeSession ? activeSession.title : 'Đơn phương chấm dứt HĐLĐ không xác định thời hạn & Ngành đặc thù'}
            </h1>
            <span className="font-label-statute text-label-statute px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-mono shrink-0">
              #VN-LEG-2026-88
            </span>
          </div>

          <div className="flex items-center gap-space-xs shrink-0">
            <button
              className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
              title="Xuất báo cáo PDF"
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">download</span>
            </button>
            <button
              className="p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors"
              title="Chia sẻ phiên tra cứu"
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">share</span>
            </button>
          </div>
        </header>

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
              <h2 className="font-headline-lg text-headline-lg text-on-surface mb-2 font-bold">
                Hệ thống Hỏi đáp & Tra cứu Pháp luật Việt Nam
              </h2>
              <p className="font-body-md text-body-md text-on-surface-variant mb-6 leading-relaxed">
                Hệ thống tích hợp <strong>Hybrid GraphRAG</strong>: kết hợp truy vấn vector ngữ nghĩa (Qdrant) và duyệt đồ thị quan hệ quy phạm pháp luật (Neo4j) cùng mô hình sinh suy luận có kiểm chứng trích dẫn Điều / Khoản / Điểm.
              </p>

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

      {/* ==================== CỘT PHẢI: CONTEXT & EVIDENTIARY INSPECTOR (440px) ==================== */}
      <aside className="w-[440px] shrink-0 bg-surface-container-low flex flex-col h-full overflow-hidden shadow-sm">
        {/* Inspector Tabs Bar */}
        <nav className="h-14 px-space-md shrink-0 bg-surface-container-lowest flex items-center justify-between gap-1 shadow-xs border-b border-outline-variant/30">
          <button
            onClick={() => setInspectorTab('tab-hierarchy')}
            className={`flex-1 py-2 rounded-lg font-headline-sm text-headline-sm text-center transition-all ${
              inspectorTab === 'tab-hierarchy'
                ? 'bg-surface-container text-on-surface shadow-xs font-bold'
                : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
            }`}
          >
            Cây Phân cấp
          </button>
          <button
            onClick={() => setInspectorTab('tab-graph')}
            className={`flex-1 py-2 rounded-lg font-headline-sm text-headline-sm text-center transition-all ${
              inspectorTab === 'tab-graph'
                ? 'bg-surface-container text-on-surface shadow-xs font-bold'
                : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
            }`}
          >
            Đồ thị Tri thức
          </button>
          <button
            onClick={() => setInspectorTab('tab-rerank')}
            className={`flex-1 py-2 rounded-lg font-headline-sm text-headline-sm text-center transition-all ${
              inspectorTab === 'tab-rerank'
                ? 'bg-surface-container text-on-surface shadow-xs font-bold'
                : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
            }`}
          >
            Bằng chứng (4/6)
          </button>
        </nav>

        {/* Tab Content Rendering */}
        {inspectorTab === 'tab-hierarchy' && <HierarchyTree />}
        {inspectorTab === 'tab-graph' && <GraphView />}
        {inspectorTab === 'tab-rerank' && <EvidencePanel />}
      </aside>
    </div>
  );
}

