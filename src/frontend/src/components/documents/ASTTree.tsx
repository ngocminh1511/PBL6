'use client';
import { useEffect, useLayoutEffect, useRef } from 'react';
import type { ASTNode } from '../../lib/types';
import type { TreeFocus } from '../../lib/locate';

const names: Record<string, string> = { document: 'Văn bản', part: 'Phần', chapter: 'Chương', section: 'Mục', article: 'Điều', clause: 'Khoản', point: 'Điểm', Dieu: 'Điều' };

function typeLabel(node: ASTNode) {
  if (node.point_number) return 'Điểm ' + node.point_number;
  if (node.clause_number) return 'Khoản ' + node.clause_number;
  if (node.article_number) return 'Điều ' + node.article_number;
  return names[node.type] || node.type;
}

/** `focus` opens the path to the cited Điều/khoản, highlights it and scrolls it into view; `tick` repeats that on every click. */
export function ASTTree({ node, level = 0, focus, tick = 0 }: { node: ASTNode; level?: number; focus?: TreeFocus; tick?: number }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const summary = useRef<HTMLElement>(null);
  const inPath = !!focus?.path.has(node.id);
  const active = !!focus?.active.has(node.id);
  const first = focus?.first === node.id;
  const type = typeLabel(node);
  // Open before the scroll below runs, also for nodes the user collapsed by hand since the last click.
  useLayoutEffect(() => { if (inPath && ref.current) ref.current.open = true; }, [inPath, focus, tick]);
  useEffect(() => { if (first) summary.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, [first, focus, tick]);
  return <details ref={ref} open={level < 1 || inPath} className="group/tree py-space-xs">
    <summary ref={summary} className={'flex items-start gap-space-xs cursor-pointer p-space-sm rounded-lg text-on-surface border shadow-xs list-none ' + (active ? 'bg-secondary-fixed border-secondary ring-2 ring-secondary' : 'bg-surface-container border-outline-variant/20')}>
      <span className="material-symbols-outlined text-[16px] text-secondary shrink-0 mt-0.5">{level === 0 ? 'folder_open' : 'subdirectory_arrow_right'}</span>
      <span className="font-label-statute text-label-statute font-bold text-secondary shrink-0">[{type}]</span>
      <span className="font-headline-sm text-body-sm font-semibold break-words min-w-0">{node.title || (node.article_number ? '' : node.id)}</span>
      {!!node.children?.length && <span className="font-label-code text-[10px] text-on-surface-variant ml-auto shrink-0">{node.children.length}</span>}
    </summary>
    {node.text && <p className="p-space-sm mt-space-xs bg-surface-container-lowest rounded-lg font-body-sm text-body-sm text-on-surface-variant whitespace-pre-wrap leading-relaxed">{node.text}</p>}
    {!!node.children?.length && <div className="ml-space-sm mt-space-xs pl-space-md border-l-2 border-indigo-200">{node.children.map((child, index) => <ASTTree key={child.id + index} node={child} level={level + 1} focus={focus} tick={tick} />)}</div>}
  </details>;
}
