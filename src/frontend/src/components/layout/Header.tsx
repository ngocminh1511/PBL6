'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '../../stores/authStore';

export const Header: React.FC = () => {
  const pathname = usePathname();
  const { user } = useAuthStore();

  const isChat = pathname.startsWith('/chat') || pathname === '/';
  const isDocs = pathname.startsWith('/documents');
  const isAdmin = pathname.startsWith('/admin');

  return (
    <header className="fixed top-0 left-0 right-0 h-14 bg-[#0F172A] text-white z-50 shadow-[0_1px_8px_rgba(0,0,0,0.12)]">
      <div className="h-14 w-full px-gutter flex items-center justify-between gap-space-md">
        {/* Brand Logo & Version */}
        <div className="flex items-center gap-space-md shrink-0">
          <Link href="/chat" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center font-bold text-white shadow-sm">
              <span className="material-symbols-outlined text-[20px]">account_balance</span>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-space-xs">
                <span className="font-headline-sm text-headline-sm text-white tracking-tight">Pháp luật Việt Nam</span>
                <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded-lg bg-[#1E293B] text-[#93C5FD] border border-[#334155]/60">
                  Hybrid GraphRAG v2.4 (AI Giải thích)
                </span>
              </div>
            </div>
          </Link>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden lg:flex items-center h-full gap-space-xs">
          <Link
            href="/chat"
            className={`h-full flex items-center px-space-md transition-colors font-body-sm text-body-sm tracking-tight ${
              isChat
                ? 'bg-[#1E293B] text-white border-b-2 border-secondary shadow-sm font-semibold'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            }`}
          >
            [1] Trợ lý Tra cứu & Hỏi đáp
          </Link>
          <Link
            href="/documents"
            className={`h-full flex items-center px-space-md transition-colors font-body-sm text-body-sm tracking-tight ${
              isDocs
                ? 'bg-[#1E293B] text-white border-b-2 border-secondary shadow-sm font-semibold'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            }`}
          >
            [2] Kho Văn bản & Quản lý Chỉ mục
          </Link>
          <Link
            href="/admin"
            className={`h-full flex items-center px-space-md transition-colors font-body-sm text-body-sm tracking-tight ${
              isAdmin
                ? 'bg-[#1E293B] text-white border-b-2 border-secondary shadow-sm font-semibold'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            }`}
          >
            [3] Cấu hình hệ thống
          </Link>
        </nav>

        {/* Dual Index Status & User Profile */}
        <div className="flex items-center gap-space-md shrink-0">
          <div className="hidden xl:flex items-center gap-space-xs px-space-md py-1 rounded bg-[#1E293B] border border-[#334155]/60">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="font-label-code text-label-code text-slate-300">Chỉ mục kép: Trực tuyến</span>
            <span className="font-label-code text-label-code text-slate-400">(Vector 100% | Đồ thị hoạt động)</span>
          </div>

          <div className="h-4 w-px bg-slate-700 hidden sm:block"></div>

          <div className="flex items-center gap-space-sm pl-space-xs">
            <div className="text-right hidden md:block">
              <div className="font-headline-sm text-headline-sm text-white leading-none">
                {user?.full_name || 'Ths. Luật sư'}
              </div>
              <div className="font-label-code text-label-code text-slate-400">Chuyên viên Nghiên cứu</div>
            </div>
            <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-white">
              <span className="material-symbols-outlined text-[18px]">person</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

