import type { ASTNode } from '../../lib/types';

const names: Record<string, string> = { document: 'Văn bản', part: 'Phần', chapter: 'Chương', section: 'Mục', article: 'Điều', clause: 'Khoản', point: 'Điểm' };

export function ASTTree({ node, level = 0 }: { node: ASTNode; level?: number }) {
  const type = names[node.type] || node.type;
  return <details open={level < 1} className="group/tree py-space-xs">
    <summary className="flex items-start gap-space-xs cursor-pointer p-space-sm rounded-lg bg-surface-container text-on-surface border border-outline-variant/20 shadow-xs list-none">
      <span className="material-symbols-outlined text-[16px] text-secondary shrink-0 mt-0.5">{level === 0 ? 'folder_open' : 'subdirectory_arrow_right'}</span>
      <span className="font-label-statute text-label-statute font-bold text-secondary shrink-0">[{type}]</span>
      <span className="font-headline-sm text-body-sm font-semibold break-words min-w-0">{node.title || node.id}</span>
      {!!node.children?.length && <span className="font-label-code text-[10px] text-on-surface-variant ml-auto shrink-0">{node.children.length}</span>}
    </summary>
    {node.text && <p className="p-space-sm mt-space-xs bg-surface-container-lowest rounded-lg font-body-sm text-body-sm text-on-surface-variant whitespace-pre-wrap leading-relaxed">{node.text}</p>}
    {!!node.children?.length && <div className="ml-space-sm mt-space-xs pl-space-md border-l-2 border-indigo-200">{node.children.map((child, index) => <ASTTree key={child.id + index} node={child} level={level + 1} />)}</div>}
  </details>;
}
