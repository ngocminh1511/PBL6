'use client';
import { useEffect, useMemo, useState } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { api, errorMessage } from '../../lib/api';
import { locateEvidence } from '../../lib/locate';
import { ASTTree } from '../documents/ASTTree';
import type { ASTNode } from '../../lib/types';

export function HierarchyTree() {
  const { selectedCitation, selectedEvidences, setSelectedCitation, focusTick } = useChatStore();
  const selected = selectedEvidences.find(e => e.citation === selectedCitation) || selectedEvidences[0];
  const id = selected?.document_id;
  const [tree, setTree] = useState<ASTNode | null>(null);
  const [error, setError] = useState('');
  const [json, setJson] = useState(false);
  useEffect(() => {
    let active = true; setTree(null); setError('');
    if (id) api.getDocumentAST(id).then(result => { if (active) setTree(result.ast_tree); })
      .catch(error => { if (active) setError(errorMessage(error)); });
    return () => { active = false; };
  }, [id]);
  const focus = useMemo(() => (tree && selected ? locateEvidence(tree, selected) : null), [tree, selected]);
  const documents = Array.from(new Map(selectedEvidences.filter(e => e.document_id).map(e => [e.document_id!, e])).values());
  return <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-space-md">
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between"><span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">Văn bản đang đối soát</span><span className="material-symbols-outlined text-secondary text-[18px]">account_tree</span></div>
      <select value={id || ''} disabled={!documents.length} onChange={e => setSelectedCitation(documents.find(item => item.document_id === e.target.value)?.citation || null)}
        className="bg-surface-container border border-outline-variant/30 rounded-lg p-space-sm font-body-sm text-body-sm text-on-surface">
        {!documents.length && <option value="">Chưa có chứng cứ được chọn</option>}
        {documents.map(item => <option key={item.document_id} value={item.document_id}>{item.meta_de_muc || item.document_id}</option>)}
      </select>
    </div>
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg">
        <button onClick={() => setJson(false)} className={'px-space-sm py-1 rounded text-body-sm font-headline-sm transition-all ' + (!json ? 'bg-surface-container-lowest text-on-surface shadow-sm' : 'text-on-surface-variant')}>Cây phân cấp trực quan</button>
        <button onClick={() => setJson(true)} className={'px-space-sm py-1 rounded text-body-sm font-headline-sm transition-all ' + (json ? 'bg-surface-container-lowest text-on-surface shadow-sm' : 'text-on-surface-variant')}>Mã AST / JSON</button>
      </div>
    </div>
    {error && <p role="alert" className="p-space-sm rounded-lg bg-amber-50 text-amber-800 font-body-sm text-body-sm">{error}</p>}
    {tree && selected?.meta_dieu && !focus && <p className="p-space-sm rounded-lg bg-amber-50 text-amber-800 font-body-sm text-body-sm">Chưa tìm thấy Điều {selected.meta_dieu} trong cây của văn bản này.</p>}
    <div className="p-space-md rounded-2xl bg-surface-container-lowest shadow-xs border border-outline-variant/30">
      {tree ? (json ? <pre className="font-label-code text-[11px] overflow-auto">{JSON.stringify(tree, null, 2)}</pre> : <ASTTree node={tree} focus={focus ?? undefined} tick={focusTick} />) :
        <div className="flex flex-col items-center justify-center py-space-xl gap-space-sm text-center text-on-surface-variant">
          <span className="material-symbols-outlined text-[32px] text-secondary">account_tree</span>
          <p className="font-body-sm text-body-sm">{id && !error ? 'Đang tải cấu trúc…' : 'Chọn chứng cứ trong câu trả lời để xem cây phân cấp.'}</p>
        </div>}
    </div>
    {selected && <div className="p-space-sm rounded-xl bg-surface-container border border-outline-variant/30 font-label-code text-[11px] text-on-surface-variant break-words"><strong className="text-secondary">Đang đối chiếu:</strong> {selected.citation}</div>}
  </div>;
}
