'use client';
import React, { useEffect, useLayoutEffect, useRef } from 'react';
import { BookOpen, Bookmark, ChevronRight, FileText, Library } from 'lucide-react';
import type { ASTNode } from '../../lib/types';
import type { TreeFocus } from '../../lib/locate';

type Level = 'document' | 'part' | 'chapter' | 'section' | 'article' | 'clause' | 'point' | 'other';

const LEVELS: Record<string, Level> = {
  document: 'document', DeMuc: 'document', part: 'part',
  chapter: 'chapter', Chuong: 'chapter', section: 'section', Muc: 'section',
  article: 'article', Dieu: 'article', clause: 'clause', point: 'point',
};

function levelOf(node: ASTNode): Level {
  if (node.point_number) return 'point';
  if (node.clause_number) return 'clause';
  if (node.article_number) return 'article';
  return LEVELS[node.type] ?? 'other';
}

const strip = (value: string, word: string) => value.replace(new RegExp('^' + word + '\\s*', 'i'), '').trim();

/** Distinct marker per level: icons for containers, "Điều 20", ①, "a)" for provisions. */
function Marker({ node, level }: { node: ASTNode; level: Level }) {
  const box = 'w-6 h-6 rounded-md flex items-center justify-center shrink-0';
  switch (level) {
    case 'document': return <span className={box + ' bg-navy text-white'}><FileText className="w-3.5 h-3.5" /></span>;
    case 'part': return <span className={box + ' bg-navy/12 text-navy'}><Library className="w-3.5 h-3.5" /></span>;
    case 'chapter': return <span className={box + ' bg-navy/8 text-navy'}><BookOpen className="w-3.5 h-3.5" /></span>;
    case 'section': return <span className={box + ' bg-[#9A6B2F]/10 text-[#7A521E]'}><Bookmark className="w-3.5 h-3.5" /></span>;
    case 'article':
      return <span className="shrink-0 px-1.5 py-0.5 rounded-md bg-navy/8 text-navy text-[11.5px] font-semibold whitespace-nowrap">
        Điều {strip(String(node.article_number), 'Điều')}
      </span>;
    case 'clause':
      return <span className="shrink-0 w-5 h-5 mt-px rounded-full border border-navy/40 text-navy text-[10.5px] font-semibold flex items-center justify-center">
        {strip(String(node.clause_number), 'Khoản')}
      </span>;
    case 'point':
      return <span className="shrink-0 mt-px text-[12px] font-semibold text-ink-3">{strip(String(node.point_number), 'Điểm')})</span>;
    default: return <span className={box + ' bg-stone text-ink-3'}><FileText className="w-3.5 h-3.5" /></span>;
  }
}

const titleClass: Record<Level, string> = {
  document: 'text-[13px] font-semibold text-ink',
  part: 'text-[12.5px] font-semibold text-ink uppercase tracking-wide',
  chapter: 'text-[12.5px] font-semibold text-ink',
  section: 'text-[12.5px] font-medium text-ink-2',
  article: 'text-[13px] font-medium text-ink',
  clause: 'text-[12.5px] text-ink-2',
  point: 'text-[12.5px] text-ink-2',
  other: 'text-[12.5px] text-ink-2',
};

/** Same focus contract as ASTTree: open the path to the cited provision, highlight it and scroll to it on every tick. */
export function LegalTree({ node, level = 0, focus, tick = 0 }: { node: ASTNode; level?: number; focus?: TreeFocus; tick?: number }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const row = useRef<HTMLElement>(null);
  const inPath = !!focus?.path.has(node.id);
  const active = !!focus?.active.has(node.id);
  const first = focus?.first === node.id;
  const kind = levelOf(node);
  const children = node.children ?? [];
  const showCount = (kind === 'chapter' || kind === 'section' || kind === 'part') && children.length > 0;
  const text = node.text?.trim() ?? '';
  const extra = text && text !== node.title?.trim() ? text : '';

  useLayoutEffect(() => { if ((inPath || active) && ref.current) ref.current.open = true; }, [inPath, active, focus, tick]);
  useEffect(() => { if (first) row.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, [first, focus, tick]);

  const rowClass = 'flex items-start gap-2 px-2 py-1.5 rounded-lg transition-colors '
    + (active ? 'bg-navy/[0.06] ring-1 ring-navy/45' : 'hover:bg-stone');
  const label = <span className={'block min-w-0 break-words leading-snug ' + titleClass[kind]}>{node.title || ''}</span>;
  const count = showCount && <span className="ml-auto pl-2 shrink-0 text-[11px] text-muted tabular-nums">{children.length}</span>;

  const chevron = <ChevronRight className="w-3.5 h-3.5 mt-1 shrink-0 text-muted transition-transform [details[open]>summary>&]:rotate-90" />;

  // A provision without children and without its own text has nothing to expand.
  if (!children.length && !extra) {
    return <div className="py-0.5">
      <div ref={row as React.RefObject<HTMLDivElement>} className={rowClass}>
        <span className="w-3.5 shrink-0" aria-hidden="true" />
        <Marker node={node} level={kind} />
        {label}
      </div>
    </div>;
  }

  // A provision with text only: collapsed to its title, opened when cited.
  if (!children.length) {
    return <details ref={ref} open={inPath || active} className="py-0.5">
      <summary ref={row as React.RefObject<HTMLElement>} className={rowClass + ' cursor-pointer list-none [&::-webkit-details-marker]:hidden'}>
        {chevron}
        <Marker node={node} level={kind} />
        {label}
      </summary>
      <p className="ml-[34px] mr-2 mt-0.5 mb-1 text-[12px] leading-relaxed text-ink-3 whitespace-pre-wrap">{extra}</p>
    </details>;
  }

  return <details ref={ref} open={level < 1 || inPath} className="py-0.5">
    <summary ref={row as React.RefObject<HTMLElement>} className={rowClass + ' cursor-pointer list-none [&::-webkit-details-marker]:hidden'}>
      {chevron}
      <Marker node={node} level={kind} />
      {label}
      {count}
    </summary>
    {extra && level > 0 && <p className="ml-[34px] mr-2 mt-0.5 text-[12px] leading-relaxed text-ink-3 whitespace-pre-wrap line-clamp-3">{extra}</p>}
    <div className="ml-[15px] pl-2.5 border-l border-ink/8">
      {children.map((child, index) => <LegalTree key={child.id + index} node={child} level={level + 1} focus={focus} tick={tick} />)}
    </div>
  </details>;
}
