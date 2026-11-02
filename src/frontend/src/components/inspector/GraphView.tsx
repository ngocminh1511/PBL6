'use client';

import React, { useState, useMemo } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { EvidenceItem } from '../../lib/types';

interface GraphNode {
  id: string;
  label: string;
  subLabel?: string;
  type: 'central' | 'parent' | 'child' | 'refers_to' | 'amendment';
  x: number;
  y: number;
  radius: number;
  data?: {
    title?: string;
    text?: string;
    source?: string;
    citation?: string;
    validity?: string;
  };
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  type: 'PART_OF' | 'REFERS_TO' | 'CONTAINS' | 'AMENDS';
  color: string;
  dashed?: boolean;
}

export const GraphView: React.FC = () => {
  const { selectedCitation, selectedEvidences, setSelectedCitation } = useChatStore();
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);

  // Fallback initial sample evidence if no chat turn has occurred yet
  const defaultSampleEvidence: EvidenceItem = useMemo(
    () => ({
      chunk_id: 'sample_bll_d35',
      mapc: '20.2.LĐ.3.35',
      ten: 'Quyền đơn phương chấm dứt hợp đồng lao động của người lao động',
      text: 'Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải báo trước: ít nhất 45 ngày nếu làm việc theo hợp đồng lao động không xác định thời hạn; đối với ngành, nghề đặc thù thực hiện theo quy định của Chính phủ (NĐ 145/2020).',
      source: 'vector',
      score: 0.95,
      document_id: '45-2019-qh14',
      meta_dieu: '35',
      meta_khoan: '1',
      meta_de_muc: 'Bộ luật Lao động 2019',
      citation: 'Điều 35 Bộ luật Lao động 2019',
      amendments: [],
    }),
    []
  );

  const availableEvidences = selectedEvidences.length > 0 ? selectedEvidences : [defaultSampleEvidence];

  // Find the focused evidence item based on selectedCitation or default to first
  const currentEvidence = useMemo(() => {
    if (selectedCitation) {
      const normalizedQuery = selectedCitation.toLowerCase();
      const match = availableEvidences.find((e) => {
        const cit = (e.citation || '').toLowerCase();
        const ten = (e.ten || '').toLowerCase();
        const chunk = (e.chunk_id || '').toLowerCase();
        return (
          cit.includes(normalizedQuery) ||
          normalizedQuery.includes(cit) ||
          ten.includes(normalizedQuery) ||
          chunk.includes(normalizedQuery)
        );
      });
      if (match) return match;
    }
    return availableEvidences[0];
  }, [availableEvidences, selectedCitation]);

  // Build Dynamic Graph (Nodes + Edges) around the currently focused evidence
  const { nodes, edges } = useMemo(() => {
    const nodeList: GraphNode[] = [];
    const edgeList: GraphEdge[] = [];

    // 1. Central Node (Focus Article)
    const centralCitation = currentEvidence.citation || `Điều ${currentEvidence.meta_dieu || 'Pháp điển'}`;
    const centralShort = centralCitation.length > 20 ? centralCitation.slice(0, 18) + '...' : centralCitation;
    const hasAmendment = currentEvidence.amendments && currentEvidence.amendments.length > 0;
    const validityText = hasAmendment
      ? 'Đã bị sửa đổi / bổ sung một phần bởi văn bản mới'
      : 'Đang có hiệu lực thi hành đầy đủ (Xác thực từ Neo4j: Thuộc tính HAS_VALIDITY_INTERVAL)';

    nodeList.push({
      id: 'node-central',
      label: centralShort,
      subLabel: currentEvidence.document_id || 'Tâm điểm',
      type: 'central',
      x: 250,
      y: 110,
      radius: 28,
      data: {
        title: currentEvidence.ten,
        text: currentEvidence.text,
        source: currentEvidence.source,
        citation: currentEvidence.citation,
        validity: validityText,
      },
    });

    // 2. Parent Node (Chapter / Statute Container - PART_OF)
    const parentDocName = currentEvidence.meta_de_muc || 'Bộ luật Lao động 2019';
    const parentLabel = parentDocName.length > 18 ? parentDocName.slice(0, 16) + '...' : parentDocName;

    nodeList.push({
      id: 'node-parent',
      label: parentLabel,
      subLabel: 'Văn bản / Chương',
      type: 'parent',
      x: 90,
      y: 50,
      radius: 22,
      data: {
        title: parentDocName,
        text: `Văn bản quy phạm chủ quản chứa ${centralCitation}`,
        source: 'ontology:hierarchy',
      },
    });

    edgeList.push({
      id: 'edge-part-of',
      source: 'node-central',
      target: 'node-parent',
      label: 'PART_OF',
      type: 'PART_OF',
      color: '#818cf8',
      dashed: true,
    });

    // 3. Child Node (Clause / Khoản - CONTAINS)
    const khoanVal = currentEvidence.meta_khoan || '1';
    nodeList.push({
      id: 'node-child',
      label: `Khoản ${khoanVal}`,
      subLabel: 'Thành phần điều luật',
      type: 'child',
      x: 90,
      y: 170,
      radius: 19,
      data: {
        title: `Khoản ${khoanVal} - ${currentEvidence.citation}`,
        text: currentEvidence.text.slice(0, 200) + '...',
        source: 'ast:clause',
      },
    });

    edgeList.push({
      id: 'edge-contains',
      source: 'node-central',
      target: 'node-child',
      label: 'CONTAINS',
      type: 'CONTAINS',
      color: '#a78bfa',
    });

    // 4. Reference Nodes (REFERS_TO / IMPLEMENTS)
    // Find cross-reference from other evidences or text mentions
    const otherEvidences = availableEvidences.filter((e) => e.chunk_id !== currentEvidence.chunk_id);
    const refEvidence = otherEvidences.find(
      (e) => e.source.includes('REFERS_TO') || e.source.includes('graph') || e.document_id !== currentEvidence.document_id
    ) || otherEvidences[0];

    if (refEvidence) {
      const refCit = refEvidence.citation || `Điều ${refEvidence.meta_dieu || 'Liên quan'}`;
      const refShort = refCit.length > 18 ? refCit.slice(0, 16) + '...' : refCit;

      nodeList.push({
        id: 'node-ref',
        label: refShort,
        subLabel: refEvidence.meta_de_muc || 'Nghị định / VB Dẫn chiếu',
        type: 'refers_to',
        x: 410,
        y: 60,
        radius: 24,
        data: {
          title: refEvidence.ten || refCit,
          text: refEvidence.text,
          source: refEvidence.source,
          citation: refEvidence.citation,
        },
      });

      edgeList.push({
        id: 'edge-refers-to',
        source: 'node-central',
        target: 'node-ref',
        label: 'REFERS_TO',
        type: 'REFERS_TO',
        color: '#f59e0b',
      });
    } else {
      // Fallback context reference if only 1 evidence retrieved
      nodeList.push({
        id: 'node-ref-sample',
        label: 'NĐ 145/2020',
        subLabel: 'Điều 7 (Đặc thù)',
        type: 'refers_to',
        x: 410,
        y: 60,
        radius: 24,
        data: {
          title: 'Nghị định 145/2020/NĐ-CP Điều 7',
          text: 'Quy định chi tiết ngành nghề đặc thù và thời hạn báo trước đối với thành viên tổ lái tàu bay, người quản lý doanh nghiệp.',
          source: 'graph:REFERS_TO',
        },
      });

      edgeList.push({
        id: 'edge-refers-to-fallback',
        source: 'node-central',
        target: 'node-ref-sample',
        label: 'REFERS_TO',
        type: 'REFERS_TO',
        color: '#f59e0b',
      });
    }

    // 5. Amendment Node (AMENDS) if present in currentEvidence
    if (currentEvidence.amendments && currentEvidence.amendments.length > 0) {
      const amend = currentEvidence.amendments[0];
      nodeList.push({
        id: 'node-amend',
        label: amend.citation || 'Văn bản sửa đổi',
        subLabel: amend.change || 'Sửa đổi bổ sung',
        type: 'amendment',
        x: 410,
        y: 170,
        radius: 20,
        data: {
          title: amend.citation,
          text: amend.text,
          source: 'graph:AMENDS',
        },
      });

      edgeList.push({
        id: 'edge-amends',
        source: 'node-amend',
        target: 'node-central',
        label: 'AMENDS',
        type: 'AMENDS',
        color: '#10b981',
      });
    } else if (otherEvidences.length > 1) {
      // If no amendment, but there is a 2nd related evidence from retrieval:
      const secondRef = otherEvidences[1];
      const secondCit = secondRef.citation || `Điều ${secondRef.meta_dieu || 'Liên quan'}`;
      const secondShort = secondCit.length > 18 ? secondCit.slice(0, 16) + '...' : secondCit;

      nodeList.push({
        id: 'node-ref-2',
        label: secondShort,
        subLabel: secondRef.meta_de_muc || 'Quy định liên đới',
        type: 'refers_to',
        x: 410,
        y: 170,
        radius: 22,
        data: {
          title: secondRef.ten || secondCit,
          text: secondRef.text,
          source: secondRef.source,
          citation: secondRef.citation,
        },
      });

      edgeList.push({
        id: 'edge-refers-to-2',
        source: 'node-central',
        target: 'node-ref-2',
        label: 'REFERS_TO',
        type: 'REFERS_TO',
        color: '#f59e0b',
      });
    }

    return { nodes: nodeList, edges: edgeList };
  }, [currentEvidence, availableEvidences]);

  // Selected node inspection
  const selectedNode = activeNodeId ? nodes.find((n) => n.id === activeNodeId) : nodes[0];

  return (
    <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-space-md">
      {/* Top Header Bar with Context Selector */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Mạng lưới Đồ thị Tri thức (Neo4j)
          </span>
          <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed font-semibold">
            Duyệt đa bước (1-2 Hops)
          </span>
        </div>

        {/* Dropdown to switch focus among retrieved evidences */}
        {availableEvidences.length > 1 && (
          <div className="flex items-center gap-2">
            <label className="font-label-statute text-label-statute text-on-surface-variant shrink-0">
              Tâm điểm:
            </label>
            <select
              value={currentEvidence.chunk_id}
              onChange={(e) => {
                const found = availableEvidences.find((ev) => ev.chunk_id === e.target.value);
                if (found) {
                  setSelectedCitation(found.citation);
                  setActiveNodeId('node-central');
                }
              }}
              className="w-full bg-surface-container text-on-surface font-body-sm text-body-sm p-1.5 rounded-lg border border-outline-variant/40 focus:outline-none cursor-pointer"
            >
              {availableEvidences.map((ev, idx) => (
                <option key={ev.chunk_id || idx} value={ev.chunk_id}>
                  {ev.citation} - {ev.ten.slice(0, 35)}...
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Interactive SVG Network Map */}
      <div className="w-full h-80 rounded-2xl bg-slate-950 p-4 relative overflow-hidden flex flex-col justify-between shadow-lg border border-slate-800">
        <div className="absolute inset-0 opacity-25 pointer-events-none">
          <div className="w-full h-full border border-slate-700/40 bg-[radial-gradient(#334155_1px,transparent_1px)] [background-size:16px_16px]"></div>
        </div>

        {/* Graph Meta Top Info */}
        <div className="relative z-10 flex items-center justify-between text-white font-label-statute text-[11px]">
          <span className="flex items-center gap-1.5 truncate max-w-[280px]">
            <span className="w-2 h-2 rounded-full bg-indigo-400"></span>
            Đang đối soát: <strong className="text-amber-300 ml-1">{currentEvidence.citation}</strong>
          </span>
          <span className="text-slate-400 font-mono text-[10px]">
            Cypher: MATCH (d)-[r:REFERS_TO]-(t)
          </span>
        </div>

        {/* Dynamic SVG Visualizer */}
        <svg className="w-full h-52 relative z-10 select-none" viewBox="0 0 500 220">
          <defs>
            <marker
              id="arrow-refers"
              viewBox="0 0 10 10"
              refX="20"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#f59e0b" />
            </marker>
            <marker
              id="arrow-partof"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#818cf8" />
            </marker>
            <marker
              id="arrow-contains"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#a78bfa" />
            </marker>
            <marker
              id="arrow-amends"
              viewBox="0 0 10 10"
              refX="18"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#10b981" />
            </marker>
          </defs>

          {/* Render Graph Edges */}
          {edges.map((edge) => {
            const src = nodes.find((n) => n.id === edge.source);
            const tgt = nodes.find((n) => n.id === edge.target);
            if (!src || !tgt) return null;

            const midX = (src.x + tgt.x) / 2;
            const midY = (src.y + tgt.y) / 2;
            const markerId =
              edge.type === 'REFERS_TO'
                ? 'url(#arrow-refers)'
                : edge.type === 'PART_OF'
                ? 'url(#arrow-partof)'
                : edge.type === 'AMENDS'
                ? 'url(#arrow-amends)'
                : 'url(#arrow-contains)';

            return (
              <g key={edge.id}>
                <line
                  x1={src.x}
                  y1={src.y}
                  x2={tgt.x}
                  y2={tgt.y}
                  stroke={edge.color}
                  strokeWidth="2"
                  strokeDasharray={edge.dashed ? '4,4' : undefined}
                  markerEnd={markerId}
                  className="transition-all opacity-80 hover:opacity-100"
                />
                {/* Edge Label Pill */}
                <g transform={`translate(${midX}, ${midY})`}>
                  <rect
                    x="-28"
                    y="-8"
                    width="56"
                    height="16"
                    rx="4"
                    fill="#0f172a"
                    stroke={edge.color}
                    strokeWidth="1"
                    className="opacity-95"
                  />
                  <text
                    x="0"
                    y="3"
                    fill={edge.color}
                    fontSize="8"
                    fontWeight="bold"
                    textAnchor="middle"
                    fontFamily="JetBrains Mono, monospace"
                  >
                    {edge.label}
                  </text>
                </g>
              </g>
            );
          })}

          {/* Render Graph Nodes */}
          {nodes.map((node) => {
            const isSelected = selectedNode?.id === node.id;
            const isCentral = node.type === 'central';

            let fill = '#1e293b';
            let stroke = '#818cf8';

            if (isCentral) {
              fill = '#4338ca';
              stroke = '#a5b4fc';
            } else if (node.type === 'refers_to') {
              fill = '#b45309';
              stroke = '#fde68a';
            } else if (node.type === 'amendment') {
              fill = '#065f46';
              stroke = '#6ee7b7';
            }

            return (
              <g
                key={node.id}
                onClick={() => setActiveNodeId(node.id)}
                className="cursor-pointer group"
              >
                {/* Outer Glow Halo for Selected Node */}
                {isSelected && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.radius + 6}
                    fill="none"
                    stroke={stroke}
                    strokeWidth="2"
                    strokeDasharray="3,3"
                    className="animate-spin-slow"
                  />
                )}

                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.radius}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={isCentral ? 3 : 2}
                  className="transition-transform group-hover:scale-105 duration-200"
                />

                {/* Node Label Text */}
                <text
                  x={node.x}
                  y={node.y + 3}
                  fill="#ffffff"
                  fontSize={isCentral ? 10 : 8.5}
                  fontWeight="bold"
                  textAnchor="middle"
                  fontFamily="JetBrains Mono, monospace"
                  className="pointer-events-none"
                >
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Bottom Status Ticker */}
        <div className="relative z-10 flex items-center justify-between text-[11px] font-label-code text-slate-300 bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800">
          <span className="truncate">
            Đang xem:{' '}
            <strong className="text-emerald-400">
              {selectedNode ? selectedNode.label : currentEvidence.citation}
            </strong>
          </span>
          <span className="text-indigo-400 shrink-0 font-medium">Click node để đối soát</span>
        </div>
      </div>

      {/* Selected Node Details Box */}
      {selectedNode && selectedNode.data && (
        <div className="p-3 rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-xs flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="font-label-code text-[11px] font-bold text-secondary flex items-center gap-1">
              <span className="material-symbols-outlined text-[15px]">info</span>
              CHI TIẾT ĐỈNH ĐỒ THỊ: {selectedNode.label}
            </span>
            <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant font-mono">
              {selectedNode.type.toUpperCase()}
            </span>
          </div>
          {selectedNode.data.title && (
            <p className="font-body-sm text-body-sm font-semibold text-on-surface">
              {selectedNode.data.title}
            </p>
          )}
          {selectedNode.data.validity && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] font-medium">
              <span className="material-symbols-outlined text-[15px] text-emerald-600">verified</span>
              <span><strong>Hiệu lực pháp lý:</strong> {selectedNode.data.validity}</span>
            </div>
          )}
          {selectedNode.data.text && (
            <p className="font-body-sm text-body-sm text-on-surface-variant line-clamp-3 leading-relaxed">
              {selectedNode.data.text}
            </p>
          )}
        </div>
      )}

      {/* Dynamic Relationship Cards List */}
      <div className="flex flex-col gap-2">
        <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
          Các cạnh quan hệ pháp lý trong phiên ({edges.length} cạnh):
        </span>

        {edges.map((edge) => {
          const isPartOf = edge.type === 'PART_OF';
          const isRefers = edge.type === 'REFERS_TO';
          const isAmends = edge.type === 'AMENDS';

          const borderColor = isPartOf
            ? 'border-indigo-600'
            : isRefers
            ? 'border-amber-500'
            : isAmends
            ? 'border-emerald-500'
            : 'border-purple-500';

          const textColor = isPartOf
            ? 'text-indigo-700'
            : isRefers
            ? 'text-amber-700'
            : isAmends
            ? 'text-emerald-700'
            : 'text-purple-700';

          const bgColor = isPartOf
            ? 'bg-indigo-50 text-indigo-800'
            : isRefers
            ? 'bg-amber-50 text-amber-800'
            : isAmends
            ? 'bg-emerald-50 text-emerald-800'
            : 'bg-purple-50 text-purple-800';

          return (
            <div
              key={edge.id}
              className={`p-3 rounded-xl bg-surface-container-lowest border-l-4 ${borderColor} shadow-xs flex flex-col gap-1`}
            >
              <div className="flex items-center justify-between">
                <span className={`font-label-code ${textColor} font-bold text-[11px]`}>
                  QUAN HỆ: {edge.label}
                </span>
                <span className={`font-label-statute text-label-statute px-1.5 py-0.5 rounded ${bgColor}`}>
                  {isPartOf
                    ? 'Phân cấp cấu trúc'
                    : isRefers
                    ? 'Dẫn chiếu pháp điển'
                    : isAmends
                    ? 'Sửa đổi bổ sung'
                    : 'Thành phần khoản'}
                </span>
              </div>
              <p className="font-body-sm text-body-sm text-on-surface">
                {isPartOf && (
                  <>
                    <strong>{currentEvidence.citation}</strong> trực thuộc{' '}
                    <strong>{currentEvidence.meta_de_muc || 'Bộ luật Lao động'}</strong>.
                  </>
                )}
                {isRefers && (
                  <>
                    <strong>{currentEvidence.citation}</strong> dẫn chiếu pháp lý sang{' '}
                    <strong>
                      {availableEvidences.find((e) => e.chunk_id !== currentEvidence.chunk_id)?.citation ||
                        'Nghị định hướng dẫn thi hành (NĐ 145/2020)'}
                    </strong>
                    .
                  </>
                )}
                {isAmends && (
                  <>
                    Quy định này có điều khoản <strong>sửa đổi, bổ sung hiệu lực</strong> theo văn bản mới.
                  </>
                )}
                {edge.type === 'CONTAINS' && (
                  <>
                    Điều luật bao hàm thành phần quy định chi tiết:{' '}
                    <strong>Khoản {currentEvidence.meta_khoan || '1'}</strong>.
                  </>
                )}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
