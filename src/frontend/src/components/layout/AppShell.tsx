'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { NavRail } from './NavRail';
import { SettingsModal } from '../settings/SettingsModal';

/** Chat owns a full-screen workspace; every other page gets the navigation rail. */
export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const pathname = usePathname();
  const isChat = pathname === '/' || pathname.startsWith('/chat');
  return (
    <>
      {isChat ? children : (
        <>
          <NavRail />
          <div className="pl-[72px] min-h-screen">{children}</div>
        </>
      )}
      <SettingsModal />
    </>
  );
};
