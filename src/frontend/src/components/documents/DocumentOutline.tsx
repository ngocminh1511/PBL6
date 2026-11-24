'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Bookmark, ChevronRight, Library } from 'lucide-react';
import type { ASTNode, DocumentRecord } from '../../lib/types';
import {
  articleLabel, articleTitle, articlesOf, countLevels, foldText, levelOf, outlineItems, pathTo, type OutlineItem,
} from '../../lib/articleOutline';

const ICONS = { part: Library, chapter: BookOpen, section: Bookmark } as const;

function ArticleRow({ node, selected, onSelect, showSource }: {
  node: ASTNode; selected: boolean; onSelect: (node: ASTNode) => void; showSource?: boolean;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (selected) ref.current?.scrollIntoView({ block: 'nearest' }); }, [selected]);
  return (
    <button ref={ref} type="button" onClick={() => onSelect(node)} aria-current={selected || undefined}
      className={`w-full text-left flex items-start gap-2 px-2 py-1.5 rounded-lg transition-colors ${
        selected ? 'bg-secondary/[0.08] ring-1 ring-secondary/40' : 'hover:bg-stone'}`}>
      <span className="shrink-0 min-w-[52px] px-1.5 py-0.5 rounded-md bg-navy/8 text-navy text-[12px] font-semibold text-center">
        {articleLabel(node)}
      </span>
      <span className="min-w-0 flex flex-col">
        <span className={`text-[13px] leading-snug break-words ${selected ? 'text-ink font-medium' : 'text-ink-2'}`}>
          {articleTitle(node) || '(không có tên)'}
        </span>
        {showSource && node.document_number && <span className="text-[11.5px] text-ink-3">{node.document_number}</span>}
      </span>
    </button>
  );
}

function Items({ items, open, toggle, selectedId, onSelect }: {
  items: OutlineItem[]; open: Set<string>; toggle: (id: string) => void;
  selectedId: string | null; onSelect: (node: ASTNode) => void;
}) {
  // A source label is useful only when a container mixes articles of several documents.
  const sources = new Set(items.filter((i) => i.kind === 'group').map((i) => (i as { source: string | null }).source));
  return <>
    {items.map((item, index) => {
      if (item.kind === 'group') {
        return (
          <div key={'g' + index} className="flex flex-col">
            {sources.size > 1 && item.source && (
              <span className="px-2 pt-2 pb-0.5 text-[11.5px] font-semibold text-ink-3">{item.source}</span>
            )}
            {item.articles.map((node) => (
              <ArticleRow key={node.id} node={node} selected={node.id === selectedId} onSelect={onSelect} />
            ))}
          </div>
        );
      }
      const { node } = item;
      const level = levelOf(node) as keyof typeof ICONS;
      const Icon = ICONS[level] ?? BookOpen;
      const isOpen = open.has(node.id);
      const total = articlesOf(node).length;
      return (
        <div key={node.id} className="flex flex-col">
          <button type="button" onClick={() => toggle(node.id)} aria-expanded={isOpen}
            className="w-full text-left flex items-start gap-1.5 px-1.5 py-1.5 rounded-lg hover:bg-stone">
            <ChevronRight className={`w-3.5 h-3.5 mt-1 shrink-0 text-muted transition-transform ${isOpen ? 'rotate-90' : ''}`} />
            <Icon className="w-4 h-4 mt-0.5 shrink-0 text-navy/70" />
            <span className={`flex-1 min-w-0 text-[13px] leading-snug break-words ${level === 'section' ? 'text-ink-2' : 'font-semibold text-ink'}`}>
              {node.title}
            </span>
            <span className="shrink-0 pl-1 text-[11.5px] text-muted tabular-nums">{total}</span>
          </button>
          {isOpen && (
            <div className="ml-[13px] pl-2 border-l border-ink/8 flex flex-col">
              <Items items={outlineItems(node)} open={open} toggle={toggle} selectedId={selectedId} onSelect={onSelect} />
            </div>
          )}
        </div>
      );
    })}
  </>;
}

/** Header, counts and table of contents (containers and articles) of the selected document. */
export function DocumentOutline({ doc, tree, loading, selectedId, onSelect, onRemove, onOpenReview, picker }: {
  doc: DocumentRecord | undefined;
  tree: ASTNode | null;
  loading: boolean;
  selectedId: string | null;
  onSelect: (node: ASTNode) => void;
  onRemove: () => void;
  /** Open the upload that produced this PDF document, to reread or correct its review. */
  onOpenReview?: () => void;
  picker?: React.ReactNode;
}) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState('');
  const counts = useMemo(() => countLevels(tree), [tree]);
  const articles = useMemo(() => articlesOf(tree), [tree]);
  const items = useMemo(() => (tree ? outlineItems(tree) : []), [tree]);

  useEffect(() => { setQuery(''); }, [tree]);
  // Open the containers on the way to the selected article.
  useEffect(() => {
    if (!tree || !selectedId) return;
    const path = pathTo(tree, selectedId);
    setOpen((current) => (path.every((id) => current.has(id)) ? current : new Set(Array.from(current).concat(path))));
  }, [tree, selectedId]);

  const toggle = (id: string) => setOpen((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const needle = foldText(query.trim());
  const matches = needle
    ? articles.filter((node) => foldText(`${articleLabel(node)} ${node.title} ${node.document_number ?? ''}`).includes(needle))
    : [];
  const summary = ([['chương', counts.chuong], ['mục', counts.muc], ['Điều', counts.dieu], ['khoản', counts.khoan], ['điểm', counts.diem]] as const)
    .filter(([, value]) => value > 0).map(([label, value]) => `${value.toLocaleString('vi-VN')} ${label}`);

  return (
    <div className="h-full min-h-0 bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/30 flex flex-col overflow-hidden">
      <div className="p-space-sm flex flex-col gap-2 border-b border-outline-variant/20">
        {picker}
        <div className="flex items-start gap-2">
          <div className="flex-1 min-w-0 flex flex-col gap-0.5">
            <span className="text-[12px] text-ink-3">
              {doc ? [doc.document_type === 'phap_dien_html' ? 'Bộ Pháp điển' : 'PDF (OCR)', doc.document_number,
                doc.document_type === 'pdf' && doc.effective_from_date ? `hiệu lực ${doc.effective_from_date}` : null]
                .filter(Boolean).join(' · ') : ''}
            </span>
            <h2 className="text-[16px] font-semibold text-ink leading-snug">{doc?.title || 'Chưa chọn văn bản'}</h2>
            {summary.length > 0 && <span className="text-[12px] text-ink-3 tabular-nums">{summary.join(' · ')}</span>}
          </div>
          {doc?.document_type === 'pdf' && (
            <div className="shrink-0 flex flex-col items-end gap-1">
              {onOpenReview && (
                <button type="button" onClick={onOpenReview} title="Mở lượt nạp của văn bản này để xem hoặc sửa bản rà soát"
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-[12px] text-secondary border border-secondary/30 hover:bg-secondary/10 transition-colors">
                  <span className="material-symbols-outlined text-[16px]">edit_document</span>
                  Bản rà soát
                </button>
              )}
              <button type="button" onClick={onRemove} title="Gỡ văn bản PDF này khỏi kho tra cứu"
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[12px] text-error border border-error/30 hover:bg-error-container/40 transition-colors">
                <span className="material-symbols-outlined text-[16px]">delete</span>
                Gỡ
              </button>
            </div>
          )}
        </div>
        {articles.length > 0 && (
          <div className="relative">
            <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3 text-[16px]">search</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Tìm Điều theo số hoặc tên…"
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-surface-container-low text-ink text-[12.5px] placeholder:text-muted border border-outline-variant/30 focus:outline-none focus:bg-surface-container" />
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto legal-scroll p-1.5 flex flex-col">
        {!tree && <p className="py-10 text-center text-[12.5px] text-muted">{loading ? 'Đang tải mục lục…' : doc ? 'Không tải được cấu trúc văn bản.' : 'Chọn một văn bản trong danh sách.'}</p>}
        {tree && needle && (matches.length
          ? matches.map((node) => <ArticleRow key={node.id} node={node} selected={node.id === selectedId} onSelect={onSelect} showSource />)
          : <p className="py-6 text-center text-[12.5px] text-muted">Không có Điều phù hợp.</p>)}
        {tree && !needle && (articles.length
          ? <Items items={items} open={open} toggle={toggle} selectedId={selectedId} onSelect={onSelect} />
          : <p className="py-6 text-center text-[12.5px] text-muted">Văn bản chưa tách được Điều nào.</p>)}
      </div>
    </div>
  );
}
