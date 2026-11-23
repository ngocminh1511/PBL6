'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Check,
  ChevronsUpDown,
  MoreHorizontal,
  PanelLeftClose,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Scale,
  Search,
  Share2,
  Trash2,
  X,
} from 'lucide-react';
import { api } from '../../lib/api';
import { useChatStore } from '../../stores/chatStore';
import type { ChatSession } from '../../lib/types';
import { NAV_ITEMS, isNavActive } from '../layout/navItems';
import { NavEntry } from '../layout/NavEntry';

interface SessionListProps {
  onToggleCollapse?: () => void;
  onShareSession?: (session: ChatSession) => void;
}

const VN_TZ = 'Asia/Ho_Chi_Minh';

const parseDate = (dateStr: string) => {
  const isoStr = !dateStr.endsWith('Z') && !dateStr.includes('+') ? dateStr + 'Z' : dateStr;
  return new Date(isoStr);
};

const vnDayKey = (d: Date) => d.toLocaleDateString('en-CA', { timeZone: VN_TZ });

export const SessionList: React.FC<SessionListProps> = ({
  onToggleCollapse,
  onShareSession,
}) => {
  const pathname = usePathname();
  const {
    sessions,
    activeSessionId,
    selectSession,
    createSession,
    renameSession,
    deleteSession,
    pinnedSessionIds,
    togglePinSession,
  } = useChatStore();

  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const [menuOpenSessionId, setMenuOpenSessionId] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteConfirmSessionId, setDeleteConfirmSessionId] = useState<string | null>(null);
  const [copiedSessionId, setCopiedSessionId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [navMenuOpen, setNavMenuOpen] = useState(false);

  const menuRef = useRef<HTMLDivElement | null>(null);
  const navMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.listDocuments('all', undefined, undefined, 1)
      .then(page => setDocumentCount(page.total_count ?? 0))
      .catch(() => setDocumentCount(null));
  }, []);

  // Close popup menus when clicking outside
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

  useEffect(() => {
    if (!navMenuOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (navMenuRef.current && !navMenuRef.current.contains(e.target as Node)) {
        setNavMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [navMenuOpen]);

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

  const groups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const visible = q ? validSessions.filter((s) => s.title.toLowerCase().includes(q)) : validSessions;
    const todayKey = vnDayKey(new Date());
    const pinned: ChatSession[] = [];
    const today: ChatSession[] = [];
    const earlier: ChatSession[] = [];
    for (const s of visible) {
      if (pinnedSessionIds.includes(s.id)) pinned.push(s);
      else if (vnDayKey(parseDate(s.updated_at)) === todayKey) today.push(s);
      else earlier.push(s);
    }
    return { pinned, today, earlier, total: visible.length };
  }, [validSessions, searchQuery, pinnedSessionIds]);

  const formatTimeLabel = (dateStr: string) => {
    try {
      const d = parseDate(dateStr);
      if (vnDayKey(d) === vnDayKey(new Date())) {
        return d.toLocaleTimeString('vi-VN', { timeZone: VN_TZ, hour: '2-digit', minute: '2-digit', hour12: false });
      }
      return d.toLocaleDateString('vi-VN', { timeZone: VN_TZ, day: '2-digit', month: '2-digit' });
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

  const menuItemClass = 'w-full flex items-center gap-2.5 px-2.5 py-2 text-left text-[13px] text-[#2E2C27] hover:bg-paper rounded-xl transition-colors';

  const renderSession = (s: ChatSession) => {
    const isActive = s.id === activeSessionId;
    const isPinned = pinnedSessionIds.includes(s.id);
    const isMenuOpen = menuOpenSessionId === s.id;
    const isEditing = editingSessionId === s.id;

    return (
      <div
        key={s.id}
        onClick={() => selectSession(s.id)}
        className={`group relative rounded-xl px-2.5 py-2 transition-colors cursor-pointer ${
          isActive ? 'bg-stone-2 text-ink font-medium' : 'text-ink-2 hover:bg-[#F6F5F0]'
        }`}
      >
        {isEditing ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSaveRename(s.id);
            }}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1"
          >
            <input
              type="text"
              autoFocus
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setEditingSessionId(null);
              }}
              className="flex-1 min-w-0 px-2 py-0.5 text-[13px] rounded-lg border border-navy/40 focus:outline-none bg-white text-ink"
            />
            <button type="submit" className="p-1 rounded-lg text-navy hover:bg-white/80" title="Lưu">
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setEditingSessionId(null)}
              className="p-1 rounded-lg text-ink-3 hover:bg-white/80"
              title="Hủy"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </form>
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-[13.5px] leading-snug" title={s.title}>
              {s.title}
            </span>
            <div className="flex items-center shrink-0">
              <span className={`text-[11.5px] text-[#8A867E] tabular-nums ${isMenuOpen ? 'hidden' : 'group-hover:hidden'}`}>
                {formatTimeLabel(s.updated_at)}
              </span>
              <div className={`${isMenuOpen ? 'flex' : 'hidden group-hover:flex'} items-center gap-0.5`}>
                <button
                  type="button"
                  title={isPinned ? 'Bỏ ghim' : 'Ghim phiên'}
                  onClick={(e) => {
                    e.stopPropagation();
                    togglePinSession(s.id);
                  }}
                  className={`p-1 rounded-lg hover:bg-white/80 transition-colors ${isPinned ? 'text-navy' : 'text-[#6E6B64]'}`}
                >
                  <Pin className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  title="Xóa phiên"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteConfirmSessionId(s.id);
                  }}
                  className="p-1 rounded-lg text-[#6E6B64] hover:text-[#B91C1C] hover:bg-white/80 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  title="Tùy chọn phiên"
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpenSessionId(isMenuOpen ? null : s.id);
                  }}
                  className={`p-1 rounded-lg transition-colors ${isMenuOpen ? 'bg-white text-ink' : 'text-[#6E6B64] hover:bg-white/80'}`}
                >
                  <MoreHorizontal className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {copiedSessionId === s.id && (
          <div className="mt-1 text-[11px] text-emerald-700 font-medium flex items-center gap-1">
            <Check className="w-3 h-3" />
            <span>Đã sao chép liên kết phiên!</span>
          </div>
        )}

        {isMenuOpen && (
          <div
            ref={menuRef}
            onClick={(e) => e.stopPropagation()}
            className="absolute right-1 top-9 z-50 w-52 rounded-2xl bg-white border border-ink/12 shadow-lg p-1.5 space-y-0.5"
          >
            <button type="button" onClick={() => handleShare(s)} className={menuItemClass}>
              <Share2 className="w-4 h-4 text-ink-3" />
              <span>Chia sẻ cuộc trò chuyện</span>
            </button>
            <button
              type="button"
              onClick={() => {
                togglePinSession(s.id);
                setMenuOpenSessionId(null);
              }}
              className={menuItemClass}
            >
              {isPinned ? <PinOff className="w-4 h-4 text-ink-3" /> : <Pin className="w-4 h-4 text-ink-3" />}
              <span>{isPinned ? 'Bỏ ghim' : 'Ghim'}</span>
            </button>
            <button type="button" onClick={() => handleStartRename(s)} className={menuItemClass}>
              <Pencil className="w-4 h-4 text-ink-3" />
              <span>Đổi tên</span>
            </button>
            <div className="h-px bg-ink/6 my-0.5" />
            <button
              type="button"
              onClick={() => {
                setDeleteConfirmSessionId(s.id);
                setMenuOpenSessionId(null);
              }}
              className="w-full flex items-center gap-2.5 px-2.5 py-2 text-left text-[13px] text-[#B91C1C] hover:bg-red-50 rounded-xl transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span>Xoá</span>
            </button>
          </div>
        )}
      </div>
    );
  };

  const renderGroup = (label: string, items: ChatSession[]) => {
    if (items.length === 0) return null;
    return (
      <div className="mb-4">
        <div className="px-2.5 pb-1.5 text-[11.5px] font-medium text-muted">{label}</div>
        <div className="space-y-0.5">{items.map(renderSession)}</div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Brand header */}
      <div className="h-12 px-3.5 flex items-center justify-between border-b border-ink/6 shrink-0">
        <Link href="/chat" className="flex items-center gap-2 min-w-0 group">
          <span className="w-7 h-7 rounded-lg bg-navy text-white flex items-center justify-center shrink-0">
            <Scale className="w-3.5 h-3.5" />
          </span>
          <span className="font-serif text-[15.5px] font-semibold tracking-tight text-ink group-hover:text-navy truncate transition-colors">
            Pháp luật Việt Nam
          </span>
        </Link>
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            title="Thu gọn thanh bên"
            className="p-1.5 rounded-lg text-[#6E6B64] hover:text-ink hover:bg-stone transition-colors shrink-0"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* New session & search */}
      <div className="p-3 space-y-2.5 shrink-0">
        <button
          type="button"
          onClick={() => createSession()}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl border border-ink/12 bg-paper hover:bg-stone text-[13px] font-medium text-ink transition-colors"
        >
          <Plus className="w-4 h-4 text-navy" />
          <span>Tạo phiên hỏi đáp mới</span>
        </button>

        <div className="relative">
          <Search className="w-3.5 h-3.5 text-[#8A867E] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm nhanh phiên tra cứu..."
            className="w-full pl-8 pr-7 py-1.5 text-[12.5px] bg-paper border border-ink/8 rounded-xl text-ink placeholder:text-[#8A867E] focus:outline-none focus:border-navy/40 focus:bg-white transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[#8A867E] hover:text-ink"
              title="Xóa tìm kiếm"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Session groups */}
      <div className="flex-1 overflow-y-auto legal-scroll px-2.5 pt-1 pb-3">
        {!validSessions.length ? (
          <div className="px-3 py-8 text-center text-[12.5px] text-muted">Chưa có phiên được lưu.</div>
        ) : groups.total === 0 ? (
          <div className="px-3 py-8 text-center text-[12.5px] text-muted">Không tìm thấy phiên tra cứu phù hợp.</div>
        ) : (
          <>
            {renderGroup('Đã ghim', groups.pinned)}
            {renderGroup('Hôm nay', groups.today)}
            {renderGroup('Trước đó', groups.earlier)}
          </>
        )}
      </div>

      {/* Navigation & settings menu */}
      <div ref={navMenuRef} className="relative p-2.5 border-t border-ink/8 bg-white shrink-0">
        {navMenuOpen && (
          <div className="absolute bottom-14 left-2.5 right-2.5 z-30 rounded-2xl bg-white border border-ink/12 shadow-lg p-1.5 space-y-0.5">
            <div className="px-2.5 py-1.5 text-[11.5px] font-medium text-muted">Quản trị & Cài đặt</div>
            {NAV_ITEMS.map((item) => {
              const { href, label, icon: Icon } = item;
              const active = isNavActive(pathname, href);
              return (
                <NavEntry
                  key={href}
                  item={item}
                  ariaCurrent={active}
                  onNavigate={() => setNavMenuOpen(false)}
                  className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-[13px] transition-colors ${
                    active ? 'bg-stone text-navy font-medium' : 'text-[#2E2C27] hover:bg-paper'
                  }`}
                >
                  <span className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4" />
                    <span>{label}</span>
                  </span>
                  {href === '/documents' && documentCount != null ? (
                    <span className="font-mono text-[11px] text-muted tabular-nums">{documentCount} VB</span>
                  ) : active ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : null}
                </NavEntry>
              );
            })}
          </div>
        )}

        <button
          type="button"
          onClick={() => setNavMenuOpen((prev) => !prev)}
          className={`w-full flex items-center justify-between gap-2.5 px-2.5 py-2 rounded-xl transition-colors ${
            navMenuOpen ? 'bg-stone' : 'hover:bg-paper'
          }`}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="w-8 h-8 rounded-full bg-navy text-white flex items-center justify-center shrink-0">
              <Scale className="w-3.5 h-3.5" />
            </span>
            <div className="text-left min-w-0">
              <div className="text-[13px] font-medium text-ink truncate leading-tight">Quản trị & Cài đặt</div>
              <div className="text-[11.5px] text-muted truncate leading-tight mt-0.5">Kho văn bản · Cấu hình</div>
            </div>
          </div>
          <ChevronsUpDown className="w-4 h-4 text-muted shrink-0" />
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirmSessionId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-[2px] p-4"
          onClick={() => setDeleteConfirmSessionId(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl p-5 max-w-sm w-full shadow-2xl border border-ink/10 flex flex-col gap-3"
          >
            <div className="flex items-center gap-2.5 text-[#B91C1C]">
              <Trash2 className="w-5 h-5" />
              <h3 className="text-[15px] font-semibold text-ink">Xác nhận xóa phiên</h3>
            </div>
            <p className="text-[13px] leading-relaxed text-ink-3">
              Bạn có chắc chắn muốn xóa phiên tra cứu này? Toàn bộ tin nhắn và dữ liệu truy vấn sẽ bị xóa vĩnh viễn.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmSessionId(null)}
                className="px-3.5 py-1.5 rounded-xl border border-ink/12 text-[13px] font-medium text-ink-2 hover:bg-stone transition-colors"
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
                className="px-3.5 py-1.5 rounded-xl bg-[#B91C1C] text-white text-[13px] font-medium hover:bg-[#991B1B] transition-colors"
              >
                Xác nhận xóa
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
