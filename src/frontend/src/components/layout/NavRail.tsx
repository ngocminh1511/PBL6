'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Scale } from 'lucide-react';
import { api } from '../../lib/api';
import type { HealthResponse } from '../../lib/types';
import { NAV_ITEMS, isNavActive } from './navItems';

/** Vertical navigation rail for pages outside the chat workspace. */
export const NavRail: React.FC = () => {
  const pathname = usePathname();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, [pathname]);
  const connected = health?.qdrant.connection === 'connected' && health?.neo4j.connection === 'connected';
  const healthTitle = health
    ? `Chỉ mục kép: ${connected ? 'Đã kết nối' : 'Chưa kết nối đủ'} · Vector: ${health.qdrant.connection} | Đồ thị: ${health.neo4j.connection}`
    : 'Chỉ mục kép: Chưa kiểm tra';

  return (
    <aside
      aria-label="Điều hướng chính"
      className="fixed left-3 top-3 bottom-3 z-40 w-12 bg-white rounded-2xl border border-ink/8 flex flex-col items-center py-2.5 gap-2"
    >
      <Link
        href="/chat"
        title="Pháp luật Việt Nam"
        className="w-8 h-8 rounded-lg bg-navy text-white flex items-center justify-center hover:bg-navy-dark transition-colors"
      >
        <Scale className="w-4 h-4" />
      </Link>

      <div className="w-5 h-px bg-ink/8 my-0.5" />

      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = isNavActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            title={label}
            aria-current={active ? 'page' : undefined}
            className={`w-8 h-8 rounded-xl flex items-center justify-center transition-colors ${
              active ? 'bg-stone text-navy' : 'text-ink-3 hover:text-ink hover:bg-stone'
            }`}
          >
            <Icon className="w-4 h-4" />
          </Link>
        );
      })}

      <span
        title={healthTitle}
        className={`mt-auto mb-1 w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-stone-3'}`}
      />
    </aside>
  );
};
