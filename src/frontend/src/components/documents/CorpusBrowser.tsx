'use client';

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useDocumentStore } from '../../stores/documentStore';
import type { ASTNode } from '../../lib/types';
import { articlesOf } from '../../lib/articleOutline';
import { DocumentTable } from './DocumentTable';
import { DocumentOutline } from './DocumentOutline';
import { ArticleView } from './ArticleView';

/** Widths in percent of the row: [list, outline]; the article takes the rest. */
type Widths = [number, number];
const DEFAULT: Widths = [30, 31];
const MIN = { list: 18, outline: 22, article: 26 };
const STORAGE_KEY = 'documents.columns';
const BOTTOM_GAP = 16; // px kept under the columns, as the page padding

function loadWidths(): Widths {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (Array.isArray(value) && value.length === 2 && value.every((v) => typeof v === 'number')) return value as Widths;
  } catch { /* storage unavailable: defaults */ }
  return DEFAULT;
}

function useMedia(query: string) {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, [query]);
  return matches;
}

/** Vertical bar between two columns; dragging it moves the boundary, a double click resets. */
function Handle({ onDrag, onReset }: { onDrag: (dx: number) => void; onReset: () => void }) {
  const last = useRef<number | null>(null);
  return (
    <div role="separator" aria-orientation="vertical" title="Kéo để đổi độ rộng · nhấp đúp để đặt lại"
      onDoubleClick={onReset}
      onPointerDown={(e) => { last.current = e.clientX; e.currentTarget.setPointerCapture(e.pointerId); }}
      onPointerMove={(e) => {
        if (last.current === null) return;
        onDrag(e.clientX - last.current);
        last.current = e.clientX;
      }}
      onPointerUp={() => { last.current = null; }}
      className="group shrink-0 w-3 -mx-0.5 flex items-stretch justify-center cursor-col-resize touch-none select-none">
      <span className="w-0.5 my-2 rounded-full bg-transparent group-hover:bg-secondary/40 group-active:bg-secondary/70 transition-colors" />
    </div>
  );
}

/**
 * Three resizable columns filling the window down to its bottom edge, each
 * scrolling on its own: the corpus list, the table of contents of the
 * selected document and the selected article. Below xl the list becomes a
 * picker above the table of contents; below lg the columns stack.
 */
export function CorpusBrowser({ refreshKey, onRemove }: {
  refreshKey?: unknown;
  onRemove: (doc: { id: string; title: string }) => void;
}) {
  const { documents, selectedDocId, selectedDocAST, selectDocument, error } = useDocumentStore();
  const doc = documents.find((d) => d.id === selectedDocId);
  const tree = (selectedDocAST as ASTNode | null) ?? null;
  const articles = useMemo(() => articlesOf(tree), [tree]);
  const [articleId, setArticleId] = useState<string | null>(null);
  useEffect(() => { setArticleId(articles[0]?.id ?? null); }, [articles]);
  const article = articles.find((a) => a.id === articleId) ?? null;

  const wide = useMedia('(min-width: 1280px)');
  const desktop = useMedia('(min-width: 1024px)');
  const row = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number | null>(null);
  const [widths, setWidths] = useState<Widths>(DEFAULT);
  useEffect(() => { setWidths(loadWidths()); }, []);
  useEffect(() => { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(widths)); } catch { /* not kept */ } }, [widths]);

  // Fill from where the row starts down to the bottom of the window.
  useLayoutEffect(() => {
    if (!desktop) { setHeight(null); return; }
    const measure = () => {
      const top = row.current?.getBoundingClientRect().top ?? 0;
      setHeight(Math.max(480, Math.floor(window.innerHeight - top - BOTTOM_GAP)));
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [desktop, error]); // an error banner above moves the row down

  const percent = useCallback((dx: number) => (row.current ? (dx / row.current.clientWidth) * 100 : 0), []);
  const dragList = (dx: number) => setWidths(([list, outline]) => {
    const next = Math.min(Math.max(list + percent(dx), MIN.list), 100 - outline - MIN.article);
    return [next, outline];
  });
  const dragOutline = (dx: number) => setWidths(([list, outline]) => {
    const used = wide ? list : 0;
    return [list, Math.min(Math.max(outline + percent(dx), MIN.outline), 100 - used - MIN.article)];
  });

  const picker = !wide && (
    <select aria-label="Chọn văn bản" value={selectedDocId} onChange={(e) => selectDocument(e.target.value)}
      className="w-full px-2.5 py-1.5 rounded-lg bg-surface-container-low text-ink text-[13px] border border-outline-variant/30">
      {documents.map((d) => <option key={d.id} value={d.id}>{d.title}{d.document_number ? ` · ${d.document_number}` : ''}</option>)}
    </select>
  );

  const outline = (
    <DocumentOutline doc={doc} tree={tree} loading={!!doc && !tree && !error} selectedId={articleId}
      onSelect={(node) => setArticleId(node.id)} onRemove={() => doc && onRemove({ id: doc.id, title: doc.title })}
      picker={picker || undefined} />
  );
  const view = <ArticleView doc={doc} article={article} tree={tree} />;

  if (!desktop) {
    return (
      <div ref={row} className="flex flex-col gap-space-md">
        <div className="h-[60vh]">{outline}</div>
        <div className="h-[70vh]">{view}</div>
      </div>
    );
  }
  return (
    <div ref={row} className="flex items-stretch" style={{ height: height ?? undefined }}>
      {wide && <>
        <div className="min-w-0 h-full" style={{ width: `${widths[0]}%` }}><DocumentTable refreshKey={refreshKey} /></div>
        <Handle onDrag={dragList} onReset={() => setWidths(DEFAULT)} />
      </>}
      <div className="min-w-0 h-full" style={{ width: `${widths[1]}%` }}>{outline}</div>
      <Handle onDrag={dragOutline} onReset={() => setWidths(DEFAULT)} />
      <div className="min-w-0 flex-1 h-full">{view}</div>
    </div>
  );
}
