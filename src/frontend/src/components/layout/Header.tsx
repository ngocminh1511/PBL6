'use client';

import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import type { HealthResponse } from '../../lib/types';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export const Header: React.FC = () => {
  const pathname = usePathname();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, [pathname]);
  const connected = health?.qdrant.connection === 'connected' && health?.neo4j.connection === 'connected';

  const isChat = pathname.startsWith('/chat') || pathname === '/';
  const isDocs = pathname.startsWith('/documents');
  const isAdmin = pathname.startsWith('/admin');

  return (
    <header
      className="fixed top-0 left-0 right-0 h-14 z-50"
      style={{
        background: 'linear-gradient(135deg, #1a237e 0%, #1565c0 40%, #0288d1 70%, #26c6da 100%)',
        boxShadow: '0 2px 20px rgba(2,136,209,0.4), 0 0 60px rgba(38,198,218,0.15), inset 0 1px 0 rgba(255,255,255,0.15)',
      }}
    >
      {/* Spotlight overlay */}
      <div className="absolute inset-0 pointer-events-none" style={{background: 'radial-gradient(ellipse 60% 100% at 50% -20%, rgba(255,255,255,0.15) 0%, transparent 60%)'}} />

      <div className="relative h-14 w-full px-gutter flex items-center justify-between gap-space-md">
        {/* Brand Logo */}
        <div className="flex items-center gap-space-md shrink-0">
          <Link href="/chat" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center font-bold text-white shadow-sm">
              <span className="material-symbols-outlined text-[20px]">account_balance</span>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-space-xs">
                <span className="font-headline-sm text-headline-sm text-white tracking-tight">Pháp luật Việt Nam</span>
              </div>
            </div>
          </Link>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden lg:flex items-center h-full gap-space-xs min-w-0">
          <Link
            href="/chat"
            className={`h-full flex items-center px-space-md transition-colors font-body-sm text-body-sm tracking-tight ${
              isChat
                ? 'bg-white/15 text-white border-b-2 border-cyan-300 font-semibold'
                : 'text-blue-100 hover:text-white hover:bg-white/10'
            }`}
          >
            [1] Trợ lý Tra cứu &amp; Hỏi đáp
          </Link>
          <Link
            href="/documents"
            className={`h-full flex items-center px-space-md transition-colors font-body-sm text-body-sm tracking-tight ${
              isDocs
                ? 'bg-white/15 text-white border-b-2 border-cyan-300 font-semibold'
                : 'text-blue-100 hover:text-white hover:bg-white/10'
            }`}
          >
            [2] Kho Văn bản &amp; Quản lý Chỉ mục
          </Link>
          <Link
            href="/admin"
            className={`h-full flex items-center px-space-md transition-colors font-body-sm text-body-sm tracking-tight ${
              isAdmin
                ? 'bg-white/15 text-white border-b-2 border-cyan-300 font-semibold'
                : 'text-blue-100 hover:text-white hover:bg-white/10'
            }`}
          >
            [3] Cấu hình hệ thống
          </Link>
        </nav>

        {/* Dual Index Status */}
        <div className="flex items-center gap-space-md shrink-0">
          <div className="hidden min-[1800px]:flex items-center gap-space-xs px-space-md py-1 rounded bg-white/10 border border-white/20">
            <span className={"w-2 h-2 rounded-full " + (connected ? "bg-emerald-400" : "bg-slate-400")}></span>
            <span className="font-label-code text-label-code text-blue-100">{connected ? 'Chỉ mục kép: Đã kết nối' : 'Chỉ mục kép: Chưa kiểm tra'}</span>
            <span className="font-label-code text-label-code text-blue-200/70">{health ? "Vector: " + health.qdrant.connection + " | Đồ thị: " + health.neo4j.connection : "Đang đọc trạng thái"}</span>
          </div>
        </div>
      </div>
    </header>
  );
};
