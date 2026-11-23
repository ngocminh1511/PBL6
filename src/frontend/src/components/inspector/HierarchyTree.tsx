'use client';
import { useEffect, useMemo, useState } from 'react';
import { FolderTree } from 'lucide-react';
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
  return <div className="flex-1 overflow-y-auto legal-scroll p-3 flex flex-col gap-3">
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between"><span className="text-[11.5px] font-medium text-ink-2">Văn bản đang đối soát</span><span className="font-mono text-[11px] text-muted">{documents.length} VB</span></div>
      <select value={id || ''} disabled={!documents.length} onChange={e => setSelectedCitation(documents.find(item => item.document_id === e.target.value)?.citation || null)}
        className="w-full px-3 py-1.5 text-[12.5px] bg-paper border border-ink/8 rounded-xl text-ink focus:outline-none focus:border-navy/40 focus:bg-white transition-colors">
        {!documents.length && <option value="">Chưa có chứng cứ được chọn</option>}
        {documents.map(item => <option key={item.document_id} value={item.document_id}>{item.meta_de_muc || item.document_id}</option>)}
      </select>
    </div>
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-1 bg-stone p-1 rounded-xl">
        <button onClick={() => setJson(false)} className={'px-2.5 py-1 rounded-lg text-[12px] font-medium transition-colors ' + (!json ? 'bg-white text-ink shadow-[0_1px_2px_rgba(28,27,24,0.06)]' : 'text-ink-3 hover:text-ink')}>Cây phân cấp trực quan</button>
        <button onClick={() => setJson(true)} className={'px-2.5 py-1 rounded-lg text-[12px] font-medium transition-colors ' + (json ? 'bg-white text-ink shadow-[0_1px_2px_rgba(28,27,24,0.06)]' : 'text-ink-3 hover:text-ink')}>Mã AST / JSON</button>
      </div>
    </div>
    {error && <p role="alert" className="rounded-xl border border-[#9A6B2F]/25 bg-[#FAF7F0] px-3 py-2 text-[12.5px] text-[#473822]">{error}</p>}
    {tree && selected?.meta_dieu && !focus && <p className="rounded-xl border border-[#9A6B2F]/25 bg-[#FAF7F0] px-3 py-2 text-[12.5px] text-[#473822]">Chưa tìm thấy Điều {selected.meta_dieu} trong cây của văn bản này.</p>}
    <div className="p-2.5 rounded-2xl bg-white border border-ink/10">
      {tree ? (json ? <pre className="font-mono text-[11px] text-ink-2 overflow-auto">{JSON.stringify(tree, null, 2)}</pre> : <ASTTree node={tree} focus={focus ?? undefined} tick={focusTick} />) :
        <div className="flex flex-col items-center justify-center py-10 gap-2 text-center text-muted">
          <FolderTree className="w-7 h-7 text-navy/65" />
          <p className="text-[12.5px]">{id && !error ? 'Đang tải cấu trúc…' : 'Chọn chứng cứ trong câu trả lời để xem cây phân cấp.'}</p>
        </div>}
    </div>
    {selected && <div className="px-3 py-2 rounded-xl bg-paper border border-navy/25 text-[12px] text-ink-2 break-words"><strong className="font-medium text-navy">Đang đối chiếu:</strong> {selected.citation}</div>}
  </div>;
}
