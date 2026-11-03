'use client';

import React, { useState } from 'react';
import { useChatStore } from '../../stores/chatStore';

export const HierarchyTree: React.FC = () => {
  const [viewMode, setViewMode] = useState<'tree' | 'json'>('tree');
  const { selectedCitation } = useChatStore();

  const isDiemASelected = selectedCitation?.includes('Điểm a') || selectedCitation?.includes('Khoản 1');
  const isDiemDSelected = selectedCitation?.includes('Điểm d') || selectedCitation?.includes('đặc thù');

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
          <select className="w-full bg-surface-container-lowest text-on-surface font-body-sm text-body-sm p-2.5 rounded-xl appearance-none focus:outline-none shadow-xs font-medium cursor-pointer border border-outline-variant/40">
            <option>Bộ luật Lao động 45/2019/QH14 (Hiệu lực: Còn)</option>
            <option>Nghị định 145/2020/NĐ-CP (Hướng dẫn BLLĐ)</option>
            <option>Luật Bảo hiểm xã hội 58/2014/QH13</option>
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
          {/* Level 1: Chương */}
          <div className="flex items-center gap-2 text-on-surface-variant font-label-statute text-label-statute">
            <span className="material-symbols-outlined text-[16px] text-secondary">folder_open</span>
            <span className="font-bold text-on-surface">CHƯƠNG III: HỢP ĐỒNG LAO ĐỘNG</span>
          </div>

          {/* Level 2: Mục */}
          <div className="pl-4 flex flex-col gap-space-xs border-l-2 border-indigo-200 ml-2">
            <div className="flex items-center gap-1.5 text-on-surface-variant font-label-statute text-label-statute">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary"></span>
              <span>Mục 3: Chấm dứt hợp đồng lao động</span>
            </div>

            {/* Level 3: Điều 35 */}
            <div className="pl-3 flex flex-col gap-space-xs">
              <div className="p-2 rounded-lg bg-surface-container font-headline-sm text-headline-sm text-on-surface flex items-center justify-between border border-secondary/30">
                <span>Điều 35. Quyền đơn phương chấm dứt HĐLĐ của NLĐ</span>
                <span className="font-label-statute text-label-statute bg-secondary text-white px-1.5 py-0.5 rounded">
                  Có hiệu lực
                </span>
              </div>

              {/* Level 4: Khoản 1 */}
              <div className="pl-3 flex flex-col gap-space-xs text-on-surface font-body-sm text-body-sm">
                <p className="font-medium text-on-surface pt-1">
                  1. Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải báo trước cho người sử dụng lao động như sau:
                </p>

                {/* Level 5: Điểm a */}
                <div
                  className={`p-2.5 rounded-xl flex flex-col gap-1 transition-all ${
                    isDiemASelected
                      ? 'bg-secondary-fixed/40 border-2 border-secondary shadow-sm'
                      : 'bg-surface-container-high'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-label-statute text-label-statute font-bold text-on-surface">
                      Điểm a (Bình thường)
                    </span>
                    <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-bold">
                      ĐANG TRÍCH DẪN
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface">
                    "a) Ít nhất 45 ngày nếu làm việc theo hợp đồng lao động không xác định thời hạn;"
                  </p>
                  <div className="flex items-center gap-2 font-label-code text-label-statute text-outline pt-1 text-[11px]">
                    <span>Mã đoạn Vector:</span>
                    <span className="text-secondary bg-surface-container-low px-1 rounded">BLLD_D35_K1_Da</span>
                    <span>• Kích thước: 1536</span>
                  </div>
                </div>

                {/* Level 5: Điểm d (WITH REFERS_TO) */}
                <div
                  className={`p-2.5 rounded-xl flex flex-col gap-1.5 transition-all ${
                    isDiemDSelected
                      ? 'bg-amber-50 border-2 border-amber-500 shadow-sm'
                      : 'bg-surface-container-high'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-label-statute text-label-statute font-bold text-on-surface">
                      Điểm d (Đặc thù)
                    </span>
                    <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-bold">
                      DẪN CHIẾU ĐỒ THỊ
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface">
                    "d) Đối với một số ngành, nghề, công việc đặc thù thì thời hạn báo trước thực hiện theo quy định của Chính phủ."
                  </p>

                  {/* Explainable Graph Edge: REFERS_TO */}
                  <div className="p-2 rounded-lg bg-surface-container-lowest border border-amber-300 flex flex-col gap-1 shadow-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-[16px] text-amber-600">trending_flat</span>
                        <span className="font-label-code text-label-statute text-amber-700 font-bold">
                          CẠNH ĐỒ THỊ: THAM CHIẾU (REFERS_TO)
                        </span>
                      </div>
                      <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px]">
                        Đã đối chiếu & Liên kết
                      </span>
                    </div>
                    <div className="font-label-code text-label-statute text-on-surface flex items-center gap-1 text-[11px]">
                      <span>──▶</span>
                      <strong className="text-secondary">NĐ 145/2020/NĐ-CP</strong>
                      <span>(Điều 7, Khoản 2: Thành viên tổ bay, điều hành bay...)</span>
                    </div>
                  </div>
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
                node_id: 'VN_BLLD_2019_D35_K1_Dd',
                statute_type: 'Diem',
                identifier: 'Điểm d, Khoản 1, Điều 35',
                document: {
                  code: '45/2019/QH14',
                  title: 'Bộ luật Lao động 2019',
                  effective_date: '2021-01-01',
                },
                hierarchy_ancestry: [
                  { level: 'VanBan', id: 'BLLD2019' },
                  { level: 'Chuong', id: 'Chuong_III', title: 'Hợp đồng lao động' },
                  { level: 'Muc', id: 'Muc_3', title: 'Chấm dứt HĐLĐ' },
                  { level: 'Dieu', id: 'Dieu_35', title: 'Quyền đơn phương chấm dứt...' },
                  { level: 'Khoan', id: 'Khoan_1' },
                ],
                graph_edges: [
                  { type: 'PART_OF', target: 'VN_BLLD_2019_D35_K1', direction: 'OUTGOING' },
                  {
                    type: 'REFERS_TO',
                    target: 'VN_ND_145_2020_D7_K2',
                    target_title: 'Nghị định 145/2020/NĐ-CP Điều 7 Khoản 2',
                    semantic_relationship: 'QUY_DINH_CHI_TIET_NGANH_NGHE_DAC_THU',
                  },
                ],
                vector_embedding: {
                  engine: 'qdrant',
                  collection: 'legal_ld_v5_bge',
                  model: 'BAAI/bge-m3',
                  dimensions: 1024,
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

