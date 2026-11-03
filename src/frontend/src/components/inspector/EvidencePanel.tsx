'use client';

import React from 'react';
import { useChatStore } from '../../stores/chatStore';

export const EvidencePanel: React.FC = () => {
  const { selectedEvidences } = useChatStore();

  return (
    <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
          Hồ sơ Căn cứ Pháp lý
        </span>
        <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-tertiary-fixed text-on-tertiary-fixed font-semibold">
          {selectedEvidences.length > 0 ? `${selectedEvidences.length} Điều khoản` : '4 Đoạn giữ lại'}
        </span>
      </div>

      {/* Retained Evidence List */}
      <div className="flex flex-col gap-2.5">
        {selectedEvidences.length > 0 ? (
          selectedEvidences.map((ev, idx) => (
            <div
              key={ev.chunk_id || idx}
              className="p-3 rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-xs flex flex-col gap-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-surface-container text-secondary font-bold">
                  {ev.citation}
                </span>
                <span className="font-label-code text-label-code text-on-tertiary-container font-bold text-[11px]">
                  Điểm: {ev.score ? ev.score.toFixed(3) : '0.940'}
                </span>
              </div>
              <h4 className="font-headline-sm text-headline-sm text-on-surface line-clamp-1">{ev.ten}</h4>
              <p className="font-body-sm text-body-sm text-on-surface-variant line-clamp-3">
                {ev.text}
              </p>
              {ev.amendments && ev.amendments.length > 0 && (
                <div className="mt-1 p-2 rounded bg-amber-50 border border-amber-200 text-[11px] text-amber-800">
                  <strong>Được sửa đổi bởi:</strong> {ev.amendments.map((a) => a.citation).join(', ')}
                </div>
              )}
            </div>
          ))
        ) : (
          <>
            {/* Fallback sample matching mockup */}
            <div className="p-3 rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-xs flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-surface-container text-secondary font-bold">
                  Điều 35, Khoản 1, Điểm a • BLLĐ 2019
                </span>
                <span className="font-label-code text-label-code text-on-tertiary-container font-bold text-[11px]">
                  Điểm: 0.942
                </span>
              </div>
              <h4 className="font-headline-sm text-headline-sm text-on-surface">
                Quyền đơn phương chấm dứt HĐLĐ của NLĐ
              </h4>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                Ít nhất 45 ngày nếu làm việc theo hợp đồng lao động không xác định thời hạn...
              </p>
            </div>

            <div className="p-3 rounded-xl bg-surface-container-lowest border border-outline-variant/40 shadow-xs flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-surface-container text-secondary font-bold">
                  Điều 7, Khoản 2 • Nghị định 145/2020/NĐ-CP
                </span>
                <span className="font-label-code text-label-code text-on-tertiary-container font-bold text-[11px]">
                  Điểm: 0.915 [Đồ thị]
                </span>
              </div>
              <h4 className="font-headline-sm text-headline-sm text-on-surface">
                Ngành, nghề, công việc đặc thù
              </h4>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                Thành viên tổ lái tàu bay; nhân viên kỹ thuật bảo dưỡng tàu bay... Ít nhất 120 ngày.
              </p>
            </div>
          </>
        )}
      </div>

      {/* Pruned Evidence Ledger (Rose State) */}
      <div className="flex flex-col gap-2 pt-2 border-t border-outline-variant/30">
        <span className="font-label-statute text-label-statute uppercase text-rose-700 font-bold flex items-center gap-1">
          <span className="material-symbols-outlined text-[15px]">filter_alt_off</span>
          Nhật ký Loại trừ bằng chứng:
        </span>

        <div className="p-3 rounded-xl bg-[#FFF1F2] border border-[#FECDD3] flex flex-col gap-1 text-[12px]">
          <div className="flex items-center justify-between text-rose-800 font-semibold">
            <span className="line-through">Điều 37 • BLLĐ 2012 (Hết hiệu lực)</span>
            <span className="font-mono text-[10px] bg-rose-200 px-1 rounded">Đã loại: 0.42</span>
          </div>
          <span className="text-rose-600 italic">Lý do: Văn bản đã bị thay thế bởi BLLĐ 2019.</span>
        </div>

        <div className="p-3 rounded-xl bg-[#FFF1F2] border border-[#FECDD3] flex flex-col gap-1 text-[12px]">
          <div className="flex items-center justify-between text-rose-800 font-semibold">
            <span className="line-through">Điều 112 • Nghỉ lễ, tết hưởng nguyên lương</span>
            <span className="font-mono text-[10px] bg-rose-200 px-1 rounded">Đã loại: 0.58</span>
          </div>
          <span className="text-rose-600 italic">Lý do: Điểm tương đồng ngữ nghĩa thấp dưới ngưỡng lọc.</span>
        </div>
      </div>
    </div>
  );
};

