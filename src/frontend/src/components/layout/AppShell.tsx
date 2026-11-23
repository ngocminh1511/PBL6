'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { NavRail } from './NavRail';

/** Chat owns a full-screen workspace; every other page gets the navigation rail. */
export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const pathname = usePathname();
  if (pathname === '/' || pathname.startsWith('/chat')) return <>{children}</>;
  return (
    <>
      <NavRail />
      <div className="pl-[72px] min-h-screen">{children}</div>
    </>
  );
};
