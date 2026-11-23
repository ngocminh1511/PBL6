'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Check,
  FileCheck2,
  FolderTree,
  History,
  PanelLeftOpen,
  PanelRightOpen,
  Plus,
  Scale,
  Share2,
} from 'lucide-react';
import { NAV_ITEMS, isNavActive } from '../layout/navItems';

export type InspectorTab = 'tab-hierarchy' | 'tab-graph' | 'tab-rerank';

interface CollapsedRailProps {
  side: 'left' | 'right';
  onExpand: () => void;
  onDragExpand: () => void;
  onNewSession?: () => void;
  onSelectTab?: (tab: InspectorTab) => void;
  activeTab?: InspectorTab;
  evidenceCount?: number;
}

const iconBtn = 'w-8 h-8 rounded-xl flex items-center justify-center transition-colors';

export const CollapsedRail: React.FC<CollapsedRailProps> = ({
  side,
  onExpand,
  onDragExpand,
  onNewSession,
  onSelectTab,
  activeTab,
  evidenceCount = 0,
}) => {
  const pathname = usePathname();
  const dragStartX = useRef<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handleOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    window.addEventListener('mousedown', handleOutside);
    return () => window.removeEventListener('mousedown', handleOutside);
  }, [menuOpen]);

  const handleEdgePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    dragStartX.current = e.clientX;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (moveEvent: PointerEvent) => {
      if (dragStartX.current === null) return;
      const delta = moveEvent.clientX - dragStartX.current;
      const pulledInward = side === 'left' ? delta > 44 : delta < -44;
      if (pulledInward) {
        cleanup();
        onDragExpand();
      }
    };
    const cleanup = () => {
      dragStartX.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', cleanup);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', cleanup);
  };

  const handle = (
    <div
      role="separator"
      aria-orientation="vertical"
      title={side === 'left' ? 'Kéo sang phải để mở thanh lịch sử' : 'Kéo sang trái để mở thanh tra cứu'}
      onPointerDown={handleEdgePointerDown}
      onDoubleClick={onExpand}
      className="w-3 shrink-0 flex items-center justify-center cursor-col-resize group select-none"
    >
      <div className="w-1 h-10 rounded-full bg-ink/15 group-hover:h-14 group-hover:bg-navy/65 transition-all duration-150" />
    </div>
  );

  if (side === 'left') {
    return (
      <div className="flex items-stretch shrink-0 h-full">
        <aside
          aria-label="Thanh lịch sử thu gọn"
          className="w-12 bg-white rounded-2xl border border-ink/8 flex flex-col items-center py-2.5 gap-2 shrink-0 relative"
        >
          <button type="button" onClick={onExpand} title="Mở rộng lịch sử tra cứu" className={`${iconBtn} text-ink-2 hover:text-navy hover:bg-stone`}>
            <PanelLeftOpen className="w-4 h-4" />
          </button>
          <div className="w-5 h-px bg-ink/8 my-0.5" />
          {onNewSession && (
            <button type="button" onClick={onNewSession} title="Tạo phiên hỏi đáp mới" className={`${iconBtn} text-navy bg-stone hover:bg-[#EAE7DF]`}>
              <Plus className="w-4 h-4" />
            </button>
          )}
          <button type="button" onClick={onExpand} title="Lịch sử tra cứu" className={`${iconBtn} text-[#6E6B64] hover:text-ink hover:bg-stone`}>
            <History className="w-4 h-4" />
          </button>

          <div ref={menuRef} className="mt-auto relative">
            {menuOpen && (
              <div className="absolute bottom-10 left-0 z-30 w-60 rounded-2xl bg-white border border-ink/12 shadow-lg p-1.5 space-y-0.5">
                <div className="px-2.5 py-1.5 text-[11.5px] font-medium text-muted">Quản trị & Cài đặt</div>
                {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
                  const active = isNavActive(pathname, href);
                  return (
                    <Link
                      key={href}
                      href={href}
                      onClick={() => setMenuOpen(false)}
                      className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-[13px] transition-colors ${
                        active ? 'bg-stone text-navy font-medium' : 'text-[#2E2C27] hover:bg-paper'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <Icon className="w-4 h-4" />
                        <span>{label}</span>
                      </span>
                      {active && <Check className="w-3.5 h-3.5" />}
                    </Link>
                  );
                })}
              </div>
            )}
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              title="Quản trị & Cài đặt"
              className="w-8 h-8 rounded-full bg-navy text-white flex items-center justify-center hover:bg-navy-dark transition-colors"
            >
              <Scale className="w-3.5 h-3.5" />
            </button>
          </div>
        </aside>
        {handle}
      </div>
    );
  }

  const tabs: Array<{ tab: InspectorTab; title: string; icon: React.ReactNode }> = [
    { tab: 'tab-hierarchy', title: 'Cây Phân cấp văn bản', icon: <FolderTree className="w-4 h-4" /> },
    { tab: 'tab-graph', title: 'Đồ thị Tri thức', icon: <Share2 className="w-4 h-4" /> },
    { tab: 'tab-rerank', title: `Bằng chứng (${evidenceCount})`, icon: <FileCheck2 className="w-4 h-4" /> },
  ];

  return (
    <div className="flex items-stretch shrink-0 h-full">
      {handle}
      <aside
        aria-label="Thanh tra cứu thu gọn"
        className="w-12 bg-white rounded-2xl border border-ink/8 flex flex-col items-center py-2.5 gap-2 shrink-0"
      >
        <button type="button" onClick={onExpand} title="Mở rộng bảng tra cứu" className={`${iconBtn} text-ink-2 hover:text-navy hover:bg-stone`}>
          <PanelRightOpen className="w-4 h-4" />
        </button>
        <div className="w-5 h-px bg-ink/8 my-0.5" />
        {tabs.map(({ tab, title, icon }) => (
          <button
            key={tab}
            type="button"
            onClick={() => {
              onSelectTab?.(tab);
              onExpand();
            }}
            title={title}
            className={`relative ${iconBtn} ${activeTab === tab ? 'text-navy bg-stone' : 'text-[#6E6B64] hover:text-navy hover:bg-stone'}`}
          >
            {icon}
            {tab === 'tab-rerank' && evidenceCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-1 rounded-full bg-navy text-white font-mono text-[9.5px] leading-[15px] text-center tabular-nums">
                {evidenceCount}
              </span>
            )}
          </button>
        ))}
      </aside>
    </div>
  );
};
