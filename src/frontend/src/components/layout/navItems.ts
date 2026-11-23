import { FolderOpen, MessageSquare, Settings, type LucideIcon } from 'lucide-react';

export interface NavItem {
  href: string;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  /** Opens the settings dialog over the current page instead of navigating. */
  opensSettings?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: '/chat', label: 'Trợ lý Tra cứu', shortLabel: 'Tra cứu', icon: MessageSquare },
  { href: '/documents', label: 'Kho Văn bản & Chỉ mục', shortLabel: 'Kho VB', icon: FolderOpen },
  { href: '/admin', label: 'Cấu hình hệ thống', shortLabel: 'Cấu hình', icon: Settings, opensSettings: true },
];

export const isNavActive = (pathname: string, href: string) =>
  href === '/chat' ? pathname === '/' || pathname.startsWith('/chat') : pathname.startsWith(href);
