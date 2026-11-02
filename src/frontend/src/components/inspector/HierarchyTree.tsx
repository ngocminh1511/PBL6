'use client';

import React, { useState, useMemo } from 'react';
import { useChatStore } from '../../stores/chatStore';
import { EvidenceItem } from '../../lib/types';

export const HierarchyTree: React.FC = () => {
  const [viewMode, setViewMode] = useState<'tree' | 'json'>('tree');
  const { selectedCitation, selectedEvidences, setSelectedCitation } = useChatStore();

  const defaultSampleEvidence: EvidenceItem = useMemo(
    () => ({
      chunk_id: 'sample_bll_d35',
      mapc: '20.2.LĐ.3.35',
      ten: 'Quyền đơn phương chấm dứt hợp đồng lao động của người lao động',
      text: '1. Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải báo trước cho người sử dụng lao động:\na) Ít nhất 45 ngày nếu làm việc theo hợp đồng lao động không xác định thời hạn;\nd) Đối với một số ngành, nghề, công việc đặc thù thì thời hạn báo trước thực hiện theo quy định của Chính phủ (Nghị định 145/2020/NĐ-CP Điều 7).',
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

  const currentEvidence = useMemo(() => {
    if (selectedCitation) {
      const normalized = selectedCitation.toLowerCase();
      const match = availableEvidences.find((e) => {
        const cit = (e.citation || '').toLowerCase();
        const ten = (e.ten || '').toLowerCase();
        return cit.includes(normalized) || normalized.includes(cit) || ten.includes(normalized);
      });
      if (match) return match;
    }
    return availableEvidences[0];
  }, [availableEvidences, selectedCitation]);

  const docTitle = currentEvidence.meta_de_muc || (currentEvidence.document_id ? `Văn bản ${currentEvidence.document_id}` : 'Bộ luật Lao động 45/2019/QH14');
  const articleTitle = currentEvidence.citation || `Điều ${currentEvidence.meta_dieu || 'Pháp điển'}`;
  const clauseNumber = currentEvidence.meta_khoan || '1';

  return (
    <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-space-md">
      {/* Statute Document Select Dropdown */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
            Văn bản Đang Đối Soát
          </span>
          <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-semibold">
            Tồn tại thực tế
          </span>
        </div>
        <div className="relative">
          <select
            value={currentEvidence.chunk_id}
            onChange={(e) => {
              const found = availableEvidences.find((ev) => ev.chunk_id === e.target.value);
              if (found) setSelectedCitation(found.citation);
            }}
            className="w-full bg-surface-container-lowest text-on-surface font-body-sm text-body-sm p-2.5 rounded-xl appearance-none focus:outline-none shadow-xs font-medium cursor-pointer border border-outline-variant/40"
          >
            {availableEvidences.map((ev, i) => (
              <option key={ev.chunk_id || i} value={ev.chunk_id}>
                {ev.citation} - {ev.meta_de_muc || ev.ten}
              </option>
            ))}
          </select>
          <span className="material-symbols-outlined absolute right-2.5 top-3 text-[18px] text-on-surface-variant pointer-events-none">
            expand_more
          </span>
        </div>
      </div>

      {/* Switch Mode: Tree vs JSON */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-surface-container p-1 rounded-lg">
          <button
            onClick={() => setViewMode('tree')}
            className={`px-space-sm py-1 rounded text-body-sm font-headline-sm transition-all ${
              viewMode === 'tree' ? 'bg-surface-container-lowest text-on-surface shadow-sm' : 'text-on-surface-variant'
            }`}
          >
            Cây Phân cấp Trực quan
          </button>
          <button
            onClick={() => setViewMode('json')}
            className={`px-space-sm py-1 rounded text-body-sm font-headline-sm transition-all ${
              viewMode === 'json' ? 'bg-surface-container-lowest text-on-surface shadow-sm' : 'text-on-surface-variant'
            }`}
          >
            Mã AST / Graph JSON
          </button>
        </div>
        <span className="font-label-statute text-label-statute text-outline">Độ sâu: 5 cấp bậc</span>
      </div>

      {viewMode === 'tree' ? (
        /* Hierarchical Tree Visualization */
        <div className="p-space-md rounded-2xl bg-surface-container-lowest flex flex-col gap-space-sm shadow-xs border border-outline-variant/30">
          {/* Level 1: Văn bản / Chương */}
          <div className="flex items-center gap-2 text-on-surface-variant font-label-statute text-label-statute">
            <span className="material-symbols-outlined text-[16px] text-secondary">folder_open</span>
            <span className="font-bold text-on-surface uppercase">{docTitle}</span>
          </div>

          {/* Level 2: Mục */}
          <div className="pl-4 flex flex-col gap-space-xs border-l-2 border-indigo-200 ml-2">
            <div className="flex items-center gap-1.5 text-on-surface-variant font-label-statute text-label-statute">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>
              <span>Bộ Pháp Điển Điện Tử • Chủ đề 20 Lao động</span>
            </div>

            {/* Level 3: Điều luật */}
            <div className="pl-3 flex flex-col gap-space-xs">
              <div className="p-2.5 rounded-lg bg-surface-container font-headline-sm text-headline-sm text-on-surface flex items-center justify-between border border-secondary/30">
                <span className="font-bold text-indigo-950">
                  {articleTitle}: {currentEvidence.ten}
                </span>
                <span className="font-label-statute text-label-statute bg-secondary text-white px-1.5 py-0.5 rounded shrink-0">
                  Có hiệu lực
                </span>
              </div>

              {/* Level 4: Khoản */}
              <div className="pl-3 flex flex-col gap-space-xs text-on-surface font-body-sm text-body-sm">
                <p className="font-medium text-on-surface pt-1">
                  Khoản {clauseNumber}. Nội dung trích xuất quy chuẩn:
                </p>

                {/* Level 5: Text nội dung & Dẫn chiếu */}
                <div className="p-3 rounded-xl bg-secondary-fixed/30 border-2 border-secondary shadow-sm flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-label-statute text-label-statute font-bold text-on-surface">
                      Đoạn quy phạm (Chunk ID: {currentEvidence.chunk_id})
                    </span>
                    <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-bold">
                      ĐANG ĐỐI SOÁT
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface leading-relaxed whitespace-pre-line">
                    "{currentEvidence.text}"
                  </p>
                  <div className="flex items-center gap-2 font-label-code text-label-statute text-outline pt-1 text-[11px]">
                    <span>Nguồn truy xuất:</span>
                    <span className="text-secondary bg-surface-container-low px-1.5 py-0.5 rounded font-bold font-mono">
                      {currentEvidence.source}
                    </span>
                    <span>• Điểm tương đồng: {(currentEvidence.score || 0.95).toFixed(3)}</span>
                  </div>

                  {/* Refers to badge if present */}
                  {(currentEvidence.source.includes('REFERS_TO') || currentEvidence.source.includes('graph')) && (
                    <div className="mt-2 p-2 rounded-lg bg-surface-container-lowest border border-amber-300 flex flex-col gap-1 shadow-xs">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="material-symbols-outlined text-[16px] text-amber-600">trending_flat</span>
                          <span className="font-label-code text-label-statute text-amber-700 font-bold">
                            CẠNH ĐỒ THỊ: THAM CHIẾU (REFERS_TO)
                          </span>
                        </div>
                        <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px]">
                          1-Hop Traversal
                        </span>
                      </div>
                      <div className="font-label-code text-label-statute text-on-surface flex items-center gap-1 text-[11px]">
                        <span>──▶</span>
                        <strong className="text-secondary">{currentEvidence.citation}</strong>
                        <span>(Liên kết đồ thị tri thức Neo4j)</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* AST / Graph JSON View */
        <div className="bg-surface-container-lowest p-space-md rounded-xl font-label-code text-label-statute text-on-surface overflow-x-auto max-h-[460px] overflow-y-auto border border-outline-variant/30 text-[11px]">
          <pre className="leading-relaxed">
            {JSON.stringify(
              {
                node_id: currentEvidence.chunk_id,
                statute_type: 'ArticleComponent',
                identifier: currentEvidence.citation,
                title: currentEvidence.ten,
                document: {
                  id: currentEvidence.document_id || 'BLLD2019',
                  title: docTitle,
                  status: 'active',
                },
                hierarchy_ancestry: [
                  { level: 'VanBan', title: docTitle },
                  { level: 'ChuDe', id: '20', title: 'Lao động' },
                  { level: 'Dieu', id: currentEvidence.meta_dieu, title: currentEvidence.ten },
                  { level: 'Khoan', id: clauseNumber },
                ],
                graph_edges: [
                  { type: 'PART_OF', target: docTitle, direction: 'OUTGOING' },
                  {
                    type: 'REFERS_TO',
                    target: currentEvidence.citation,
                    source: currentEvidence.source,
                  },
                ],
                vector_embedding: {
                  engine: 'qdrant',
                  score: currentEvidence.score,
                  source: currentEvidence.source,
                },
              },
              null,
              2
            )}
          </pre>
        </div>
      )}
    </div>
  );
};
