import type { Metadata } from 'next';
import '../styles/globals.css';
import { Header } from '../components/layout/Header';

export const metadata: Metadata = {
  title: 'Pháp luật Việt Nam - Hệ thống Hỏi đáp & Tra cứu Pháp luật Đa lượt',
  description: 'Hybrid GraphRAG v2.4 (AI Giải thích) cho Hệ thống Pháp luật Việt Nam',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
          rel="stylesheet"
        />
      </head>
      <body className="bg-surface font-body-md text-on-surface antialiased">
        <Header />
        <div className="pt-14 min-h-[calc(100vh-3.5rem)]">{children}</div>
      </body>
    </html>
  );
}

