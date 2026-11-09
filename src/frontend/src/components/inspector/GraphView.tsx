'use client';
import { useEffect, useState } from 'react';
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
  return <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-space-md">
    <div className="flex items-center justify-between">
      <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">Cấu trúc Mạng lưới Đồ thị (Neo4j)</span>
      <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed font-semibold">Duyệt 1 bước (1-Hop)</span>
    </div>
    {error && <p role="alert" className="p-space-sm rounded-lg bg-amber-50 text-amber-800 font-body-sm text-body-sm">{error}</p>}
    <div className="w-full h-72 rounded-2xl bg-slate-900 p-4 relative overflow-hidden flex flex-col justify-between shadow-inner">
      <div className="absolute inset-0 opacity-20 pointer-events-none"><div className="w-full h-full bg-[radial-gradient(#334155_1px,transparent_1px)] [background-size:16px_16px]"></div></div>
      <div className="relative z-10 flex items-center justify-between gap-2 font-label-code text-[10px] text-slate-300">
        <span className="truncate" title={selected?.citation}>{selected?.citation || 'Chưa chọn chứng cứ'}</span>
        <span className="shrink-0">{graph?.status === 'connected' ? 'Đã truy vấn Neo4j' : 'Chưa có kết quả'}</span>
      </div>
      {nodes.length > 0 ? <svg viewBox="0 0 440 360" className="w-full h-44 relative z-10" aria-label="Đồ thị chứng cứ Neo4j">
        <defs><marker id="graph-arrow" markerWidth="6" markerHeight="6" refX="8" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#818cf8" /></marker></defs>
        {graph?.edges.map((edge, index) => { const first = positions.get(edge.source), second = positions.get(edge.target); return first && second ?
          <line key={index} x1={first.x} y1={first.y} x2={second.x} y2={second.y} stroke="#818cf8" strokeWidth="1.5" markerEnd="url(#graph-arrow)"><title>{edge.type}</title></line> : null; })}
        {nodes.map((node, index) => { const point = positions.get(node.id)!; return <g key={node.id}>
          <title>{(node.title || node.id) + ' · ' + node.id}</title>
          <circle cx={point.x} cy={point.y} r={nodes.length > 15 ? 7 : 18} fill={index === 0 ? '#4f46e5' : node.document_id && node.document_id !== id ? '#d97706' : '#1e293b'} stroke="#a5b4fc" strokeWidth="2" />
          <text x={point.x} y={point.y + (nodes.length > 15 ? 18 : 30)} textAnchor="middle" fill="#e2e8f0" fontSize="9" fontFamily="JetBrains Mono">{(node.title || node.id).slice(0, 24)}</text>
        </g>; })}
      </svg> : <div className="h-44 relative z-10 flex flex-col items-center justify-center text-slate-400 gap-space-sm">
        <span className="material-symbols-outlined text-[36px] text-indigo-300">hub</span>
        <p className="font-body-sm text-body-sm text-center">{id && !graph && !error ? 'Đang tải đồ thị…' : 'Chọn chứng cứ để xem các node và liên kết thực tế.'}</p>
      </div>}
      <div className="relative z-10 flex items-center gap-space-md font-label-code text-[10px] text-slate-300">
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-indigo-400"></span>{graph ? nodes.length : '—'} node</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400"></span>{graph ? graph.edges.length : '—'} quan hệ</span>
      </div>
    </div>
    <div className="p-space-md rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-xs flex flex-col gap-space-sm">
      <h3 className="font-label-statute text-label-statute uppercase text-secondary font-bold">Quan hệ và đường dẫn chứng cứ</h3>
      {graph?.edges.length ? graph.edges.map((edge, index) => <div key={index} className="p-space-sm rounded-lg bg-surface-container-low font-label-code text-[11px] break-words">
        <span title={edge.source}>{titleById.get(edge.source) || edge.source}</span>
        <span className="block text-secondary my-1">── {edge.type} →</span>
        <span title={edge.target}>{titleById.get(edge.target) || edge.target}</span>
      </div>) : <p className="font-body-sm text-body-sm text-on-surface-variant">Chưa có quan hệ được trả về.</p>}
    </div>
    {graph?.warnings.map((warning, index) => <p className="font-body-sm text-body-sm text-amber-800" key={index}>{warning}</p>)}
  </div>;
}
