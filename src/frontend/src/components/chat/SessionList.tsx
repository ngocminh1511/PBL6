'use client';

import React, { useEffect, useRef, useState } from 'react';
import { api } from '../../lib/api';
import { useChatStore } from '../../stores/chatStore';
import type { ChatSession } from '../../lib/types';

interface SessionListProps {
  onToggleCollapse?: () => void;
  onShareSession?: (session: ChatSession) => void;
}

export const SessionList: React.FC<SessionListProps> = ({
  onToggleCollapse,
  onShareSession,
}) => {
  const {
    sessions,
    activeSessionId,
    selectSession,
    createSession,
    renameSession,
    deleteSession,
    pinnedSessionIds,
    togglePinSession,
    selectedDomain,
    setSelectedDomain,
  } = useChatStore();

  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const [menuOpenSessionId, setMenuOpenSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteConfirmSessionId, setDeleteConfirmSessionId] = useState<string | null>(null);
  const [copiedSessionId, setCopiedSessionId] = useState<string | null>(null);

  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.listDocuments('all', undefined, undefined, 1)
      .then(page => setDocumentCount(page.total_count ?? 0))
      .catch(() => setDocumentCount(null));
  }, []);

  // Close popup menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenSessionId(null);
      }
    };
    if (menuOpenSessionId) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [menuOpenSessionId]);

  // Sort sessions: pinned sessions first, then by updated_at descending
  const sortedSessions = [...sessions].sort((a, b) => {
    const aPin = pinnedSessionIds.includes(a.id);
    const bPin = pinnedSessionIds.includes(b.id);
    if (aPin && !bPin) return -1;
    if (!aPin && bPin) return 1;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });

  // Filter: Do not show empty sessions in history
  const validSessions = sortedSessions.filter((s) => (s.message_count ?? 0) > 0);

  const formatVNTime = (dateStr: string) => {
    try {
      const isoStr = !dateStr.endsWith('Z') && !dateStr.includes('+') ? dateStr + 'Z' : dateStr;
      const d = new Date(isoStr);
      return d.toLocaleTimeString('vi-VN', {
        timeZone: 'Asia/Ho_Chi_Minh',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return '';
    }
  };

  const handleStartRename = (session: ChatSession) => {
    setEditingSessionId(session.id);
    setEditTitle(session.title);
    setMenuOpenSessionId(null);
  };

  const handleSaveRename = async (sessionId: string) => {
    if (editTitle.trim()) {
      await renameSession(sessionId, editTitle.trim());
    }
    setEditingSessionId(null);
  };

  const handleShare = async (session: ChatSession) => {
    setMenuOpenSessionId(null);
    if (onShareSession) {
      onShareSession(session);
      return;
    }
    const url = typeof window !== 'undefined'
      ? `${window.location.origin}/chat?session=${session.id}`
      : '';
    try {
      await navigator.clipboard.writeText(url);
      setCopiedSessionId(session.id);
      setTimeout(() => setCopiedSessionId(null), 2500);
    } catch {
      prompt('Sao chép liên kết phiên tra cứu:', url);
    }
  };

  return (
    <div className="bg-surface-container-low flex flex-col justify-between overflow-hidden h-full">
      {/* Top Section: New Session + History (Takes flex-1 and scrolls) */}
      <div className="p-space-md flex flex-col gap-space-md flex-1 min-h-0 overflow-hidden">
        {/* New Session Action Button & Collapse Toggle */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => createSession()}
            className="flex-1 flex items-center justify-center gap-space-xs py-2.5 px-3 rounded-xl text-white font-headline-sm text-headline-sm hover:opacity-95 active:scale-[0.98] transition-all shadow-md shadow-blue-500/20"
            style={{ background: 'linear-gradient(135deg, #1565c0 0%, #0288d1 60%, #00acc1 100%)' }}
            type="button"
          >
            <span className="material-symbols-outlined text-[18px]">add_circle</span>
            <span className="truncate">Tạo phiên hỏi đáp mới</span>
          </button>
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="w-9 h-9 shrink-0 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-all shadow-xs border border-outline-variant/30"
              title="Thu gọn thanh bên"
              type="button"
            >
              <span className="material-symbols-outlined text-[18px]">chevron_left</span>
            </button>
          )}
        </div>

        {/* Session History (Lịch sử đa lượt - Takes available height) */}
        <div className="flex flex-col gap-space-xs flex-1 min-h-0">
          <div className="flex items-center justify-between px-1 shrink-0">
            <span className="font-label-statute text-label-statute uppercase text-on-surface-variant tracking-wider">
              Lịch sử tra cứu gần đây
            </span>
            <span className="font-metric-num text-metric-num text-on-surface-variant">
              {validSessions.length} phiên
            </span>
          </div>

          {!validSessions.length && (
            <p className="p-space-sm rounded-xl bg-surface-container text-on-surface-variant font-body-sm text-body-sm shrink-0">
              Chưa có phiên được lưu.
            </p>
          )}

          <div className="flex flex-col gap-1.5 flex-1 min-h-0 overflow-y-auto pr-1">
            {validSessions.map((s) => {
              const isActive = s.id === activeSessionId;
              const isPinned = pinnedSessionIds.includes(s.id);
              const isMenuOpen = menuOpenSessionId === s.id;
              const isEditing = editingSessionId === s.id;

              return (
                <div
                  key={s.id}
                  onClick={() => selectSession(s.id)}
                  className={`group relative p-space-sm rounded-xl cursor-pointer transition-all flex flex-col gap-1 ${
                    isActive
                      ? 'bg-surface-container-lowest shadow-sm border-l-4 border-secondary'
                      : 'bg-surface-container hover:bg-surface-container-high'
                  }`}
                >
                  {/* Top metadata line: Domain badge + Pin/Time + 3-dots trigger */}
                  <div className="flex items-center justify-between">
                    <span
                      className={`font-label-statute text-label-statute px-1.5 py-0.5 rounded font-semibold ${
                        isActive
                          ? 'bg-secondary-fixed text-on-secondary-fixed'
                          : 'bg-surface-variant text-on-surface-variant'
                      }`}
                    >
                      {s.domain === 'lao_dong' ? 'Lao động' : s.domain === 'bhxh' ? 'BHXH' : 'Tổng hợp'}
                    </span>

                    <div className="flex items-center gap-1.5">
                      {isPinned && (
                        <span
                          className="material-symbols-outlined text-[15px] text-blue-600 rotate-45"
                          title="Đã ghim"
                        >
                          push_pin
                        </span>
                      )}
                      <span className="font-label-code text-label-code text-on-surface-variant text-[11px]">
                        {formatVNTime(s.updated_at)}
                      </span>

                      {/* 3 dots action menu button */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setMenuOpenSessionId(isMenuOpen ? null : s.id);
                        }}
                        className={`w-6 h-6 rounded-lg flex items-center justify-center transition-all ${
                          isMenuOpen
                            ? 'bg-surface-container-highest text-on-surface'
                            : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-highest opacity-70 group-hover:opacity-100'
                        }`}
                        title="Tùy chọn phiên"
                      >
                        <span className="material-symbols-outlined text-[16px]">more_vert</span>
                      </button>
                    </div>
                  </div>

                  {/* Session Title (with inline rename input) */}
                  {isEditing ? (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleSaveRename(s.id);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-1 my-0.5"
                    >
                      <input
                        type="text"
                        autoFocus
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Escape') setEditingSessionId(null);
                        }}
                        className="flex-1 px-2 py-0.5 text-headline-sm rounded-lg border border-primary focus:outline-none focus:ring-1 focus:ring-primary bg-surface-container-lowest text-on-surface"
                      />
                      <button
                        type="submit"
                        className="p-1 rounded text-primary hover:bg-surface-variant"
                        title="Lưu"
                      >
                        <span className="material-symbols-outlined text-[16px]">check</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingSessionId(null)}
                        className="p-1 rounded text-on-surface-variant hover:bg-surface-variant"
                        title="Hủy"
                      >
                        <span className="material-symbols-outlined text-[16px]">close</span>
                      </button>
                    </form>
                  ) : (
                    <p className="font-headline-sm text-headline-sm text-on-surface line-clamp-1 leading-snug">
                      {s.title}
                    </p>
                  )}

                  {/* Footer message count */}
                  <div className="flex items-center gap-space-xs text-on-surface-variant font-body-sm text-body-sm">
                    <span className="material-symbols-outlined text-[14px] text-secondary">forum</span>
                    <span>{s.message_count ?? 0} tin nhắn</span>
                  </div>

                  {copiedSessionId === s.id && (
                    <div className="text-[11px] text-emerald-600 font-medium flex items-center gap-1">
                      <span className="material-symbols-outlined text-[13px]">check_circle</span>
                      <span>Đã sao chép liên kết phiên!</span>
                    </div>
                  )}

                  {/* Dropdown Action Menu (4 features: Chia sẻ, Ghim, Đổi tên, Xóa) */}
                  {isMenuOpen && (
                    <div
                      ref={menuRef}
                      onClick={(e) => e.stopPropagation()}
                      className="absolute right-2 top-8 z-50 w-56 rounded-2xl bg-white shadow-2xl border border-slate-200/90 p-1.5 flex flex-col gap-0.5 animate-fadeIn"
                      style={{ boxShadow: '0 12px 28px -4px rgba(0, 0, 0, 0.18), 0 8px 10px -4px rgba(0, 0, 0, 0.08)' }}
                    >
                      {/* 1. Chia sẻ */}
                      <button
                        type="button"
                        onClick={() => handleShare(s)}
                        className="w-full flex items-center gap-3 px-3 py-2 text-left text-[13px] font-medium text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
                      >
                        <span className="material-symbols-outlined text-[18px] text-slate-600">share</span>
                        <span>Chia sẻ cuộc trò chuyện</span>
                      </button>

                      {/* 2. Ghim / Bỏ ghim */}
                      <button
                        type="button"
                        onClick={() => {
                          togglePinSession(s.id);
                          setMenuOpenSessionId(null);
                        }}
                        className="w-full flex items-center gap-3 px-3 py-2 text-left text-[13px] font-medium text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
                      >
                        <span className="material-symbols-outlined text-[18px] text-slate-600">
                          {isPinned ? 'keep_off' : 'push_pin'}
                        </span>
                        <span>{isPinned ? 'Bỏ ghim' : 'Ghim'}</span>
                      </button>

                      {/* 3. Đổi tên */}
                      <button
                        type="button"
                        onClick={() => handleStartRename(s)}
                        className="w-full flex items-center gap-3 px-3 py-2 text-left text-[13px] font-medium text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
                      >
                        <span className="material-symbols-outlined text-[18px] text-slate-600">edit</span>
                        <span>Đổi tên</span>
                      </button>

                      {/* Divider */}
                      <div className="h-px bg-slate-100 my-0.5" />

                      {/* 4. Xóa */}
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteConfirmSessionId(s.id);
                          setMenuOpenSessionId(null);
                        }}
                        className="w-full flex items-center gap-3 px-3 py-2 text-left text-[13px] font-medium text-red-600 hover:bg-red-50 rounded-xl transition-colors"
                      >
                        <span className="material-symbols-outlined text-[18px] text-red-500">delete</span>
                        <span>Xoá</span>
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirmSessionId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4"
          onClick={() => setDeleteConfirmSessionId(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl p-5 max-w-sm w-full shadow-2xl border border-slate-200 flex flex-col gap-3 animate-fadeIn"
          >
            <div className="flex items-center gap-2.5 text-red-600">
              <span className="material-symbols-outlined text-[24px]">delete</span>
              <h3 className="font-headline-sm text-headline-sm font-bold text-slate-800">Xác nhận xóa phiên</h3>
            </div>
            <p className="font-body-sm text-body-sm text-slate-600">
              Bạn có chắc chắn muốn xóa phiên tra cứu này? Toàn bộ tin nhắn và dữ liệu truy vấn sẽ bị xóa vĩnh viễn.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmSessionId(null)}
                className="px-3.5 py-1.5 rounded-xl border border-slate-300 font-label-statute text-label-statute hover:bg-slate-100 transition-colors"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={async () => {
                  const id = deleteConfirmSessionId;
                  setDeleteConfirmSessionId(null);
                  await deleteSession(id);
                }}
                className="px-3.5 py-1.5 rounded-xl bg-red-600 text-white font-label-statute text-label-statute hover:bg-red-700 transition-colors shadow-sm"
              >
                Xác nhận xóa
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Section: Phạm vi lập luận (Nổi bật, đặt dưới cùng, có scroll khi dài) */}
      <div className="p-space-md pt-0 shrink-0">
        <div className="rounded-2xl bg-surface-container-lowest p-3 shadow-md border border-outline-variant/40 flex flex-col gap-2">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-secondary text-[16px]">filter_alt</span>
              <span className="font-label-statute text-label-statute uppercase text-on-surface font-bold tracking-wider">
                Phạm vi lập luận
              </span>
            </div>
            <span className="font-label-statute text-[11px] text-secondary bg-secondary-fixed/50 px-1.5 py-0.5 rounded font-medium">
              Bộ lọc
            </span>
          </div>

          <div className="flex flex-col gap-1.5 max-h-[150px] overflow-y-auto pr-1">
            <label
              className={`flex items-center justify-between p-2 rounded-xl cursor-pointer transition-all ${
                selectedDomain === 'all'
                  ? 'bg-surface-container shadow-xs border border-secondary/30'
                  : 'hover:bg-surface-container'
              }`}
            >
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="domain"
                  checked={selectedDomain === 'all'}
                  onChange={() => setSelectedDomain('all')}
                  className="accent-secondary h-3.5 w-3.5"
                />
                <span className="font-body-sm text-body-sm font-medium text-on-surface">Toàn bộ kho số hóa</span>
              </div>
              <span className="font-metric-num text-metric-num text-on-surface-variant bg-surface-variant px-1.5 rounded">
                {documentCount == null ? '—' : documentCount + ' VB'}
              </span>
            </label>

            <label
              className={`flex items-center justify-between p-2 rounded-xl cursor-pointer transition-all ${
                selectedDomain === 'lao_dong'
                  ? 'bg-surface-container shadow-xs border border-secondary/30'
                  : 'hover:bg-surface-container'
              }`}
            >
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="domain"
                  checked={selectedDomain === 'lao_dong'}
                  onChange={() => setSelectedDomain('lao_dong')}
                  className="accent-secondary h-3.5 w-3.5"
                />
                <span className="font-body-sm text-body-sm text-on-surface">Pháp luật Lao động</span>
              </div>
              <span className="font-metric-num text-metric-num text-on-surface-variant">
                {documentCount == null ? '—' : documentCount + ' VB'}
              </span>
            </label>

            <label className="flex items-center justify-between p-2 rounded-xl opacity-60 cursor-not-allowed">
              <div className="flex items-center gap-2">
                <input
                  type="radio"
                  name="domain"
                  checked={false}
                  disabled
                  className="accent-secondary h-3.5 w-3.5"
                />
                <span className="font-body-sm text-body-sm text-on-surface">Luật BHXH & Y tế</span>
              </div>
              <span className="font-metric-num text-metric-num text-on-surface-variant">Chưa nạp</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};
