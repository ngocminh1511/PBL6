'use client';

import React from 'react';
import Link from 'next/link';
import { openSettings } from '../settings/settingsHash';
import type { NavItem } from './navItems';

interface NavEntryProps {
  item: NavItem;
  className: string;
  title?: string;
  ariaCurrent?: boolean;
  onNavigate?: () => void;
  children: React.ReactNode;
}

/** A navigation link, or a button that opens the settings dialog in place. */
export const NavEntry: React.FC<NavEntryProps> = ({ item, className, title, ariaCurrent, onNavigate, children }) => {
  if (item.opensSettings) {
    return (
      <button
        type="button"
        title={title}
        className={className}
        onClick={() => {
          onNavigate?.();
          openSettings();
        }}
      >
        {children}
      </button>
    );
  }
  return (
    <Link href={item.href} title={title} className={className} aria-current={ariaCurrent ? 'page' : undefined} onClick={onNavigate}>
      {children}
    </Link>
  );
};
