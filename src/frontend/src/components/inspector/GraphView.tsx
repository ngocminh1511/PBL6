'use client';
import { useEffect, useState } from 'react';
import { Share2 } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import { api, errorMessage } from '../../lib/api';
import type { GraphResponse } from '../../lib/types';

export function GraphView() {
  const { selectedCitation, selectedEvidences } = useChatStore();
  const selected = selectedEvidences.find(e => e.citation === selectedCitation) || selectedEvidences[0];
  const id = selected?.document_id, article = selected?.meta_dieu;
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; setGraph(null); setError('');
    if (id) api.getGraph(id, article).then(result => { if (active) setGraph(result); })
      .catch(error => { if (active) setError(errorMessage(error)); });
    return () => { active = false; };
  }, [id, article]);
  const nodes = graph?.nodes || [];
  const positions = new Map(nodes.map((node, index) => [node.id, {
    x: 220 + 165 * Math.cos(index * Math.PI * 2 / Math.max(nodes.length, 1)),
    y: 180 + 130 * Math.sin(index * Math.PI * 2 / Math.max(nodes.length, 1)),
  }]));
  const titleById = new Map(nodes.map(node => [node.id, node.title || node.id]));
  return <div className="flex-1 overflow-y-auto legal-scroll p-3 flex flex-col gap-3">
    <div className="flex items-center justify-between">
      <span className="text-[11.5px] font-medium text-ink-2">Cấu trúc mạng lưới đồ thị (Neo4j)</span>
      <span className="font-mono text-[11px] px-2 py-0.5 rounded-md bg-navy/8 text-navy">Duyệt 1 bước (1-Hop)</span>
    </div>
    {error && <p role="alert" className="rounded-xl border border-[#9A6B2F]/25 bg-[#FAF7F0] px-3 py-2 text-[12.5px] text-[#473822]">{error}</p>}
    <div className="w-full h-72 rounded-2xl bg-paper border border-ink/10 p-4 relative overflow-hidden flex flex-col justify-between">
      <div className="absolute inset-0 opacity-20 pointer-events-none"><div className="w-full h-full bg-[radial-gradient(#C9C5BC_1px,transparent_1px)] [background-size:16px_16px]"></div></div>
      <div className="relative z-10 flex items-center justify-between gap-2 font-mono text-[10.5px] text-ink-3">
        <span className="truncate" title={selected?.citation}>{selected?.citation || 'Chưa chọn chứng cứ'}</span>
        <span className="shrink-0">{graph?.status === 'connected' ? 'Đã truy vấn Neo4j' : 'Chưa có kết quả'}</span>
      </div>
      {nodes.length > 0 ? <svg viewBox="0 0 440 360" className="w-full h-44 relative z-10" aria-label="Đồ thị chứng cứ Neo4j">
        <defs><marker id="graph-arrow" markerWidth="6" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#1E3A5F" /></marker></defs>
        {graph?.edges.map((edge, index) => { const first = positions.get(edge.source), second = positions.get(edge.target); return first && second ?
          <line key={index} x1={first.x} y1={first.y} x2={second.x} y2={second.y} stroke="#1E3A5F" strokeOpacity="0.45" strokeWidth="1.5" markerEnd="url(#graph-arrow)"><title>{edge.type}</title></line> : null; })}
        {nodes.map((node, index) => { const point = positions.get(node.id)!; return <g key={node.id}>
          <title>{(node.title || node.id) + ' · ' + node.id}</title>
          <circle cx={point.x} cy={point.y} r={nodes.length > 15 ? 7 : 18} fill={index === 0 ? '#1E3A5F' : node.document_id && node.document_id !== id ? '#9A6B2F' : '#FFFFFF'} stroke="#1E3A5F" strokeWidth="2" />
          <text x={point.x} y={point.y + (nodes.length > 15 ? 18 : 30)} textAnchor="middle" fill="#3F3D37" fontSize="9" fontFamily="Plus Jakarta Sans, system-ui, sans-serif">{(node.title || node.id).slice(0, 24)}</text>
        </g>; })}
      </svg> : <div className="h-44 relative z-10 flex flex-col items-center justify-center text-muted gap-2">
        <Share2 className="w-7 h-7 text-navy/65" />
        <p className="text-[12.5px] text-center">{id && !graph && !error ? 'Đang tải đồ thị…' : 'Chọn chứng cứ để xem các node và liên kết thực tế.'}</p>
      </div>}
      <div className="relative z-10 flex items-center gap-space-md font-mono text-[10.5px] text-ink-3">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-navy"></span>{graph ? nodes.length : '—'} node</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#9A6B2F]"></span>{graph ? graph.edges.length : '—'} quan hệ</span>
      </div>
    </div>
    <div className="p-3.5 rounded-2xl bg-white border border-ink/10 flex flex-col gap-2">
      <h3 className="text-[13px] font-semibold text-ink">Quan hệ và đường dẫn chứng cứ</h3>
      {graph?.edges.length ? graph.edges.map((edge, index) => <div key={index} className="px-3 py-2 rounded-xl bg-paper font-mono text-[11px] text-ink-2 break-words">
        <span title={edge.source}>{titleById.get(edge.source) || edge.source}</span>
        <span className="block text-navy my-1">── {edge.type} →</span>
        <span title={edge.target}>{titleById.get(edge.target) || edge.target}</span>
      </div>) : <p className="text-[12.5px] text-muted">Chưa có quan hệ được trả về.</p>}
    </div>
    {graph?.warnings.map((warning, index) => <p className="text-[12.5px] text-[#7A521E]" key={index}>{warning}</p>)}
  </div>;
}
