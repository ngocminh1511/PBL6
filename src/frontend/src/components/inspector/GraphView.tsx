'use client';

import React from 'react';

export const GraphView: React.FC = () => {
  return (
    <div className="flex-1 overflow-y-auto p-space-md flex flex-col gap-space-md">
      <div className="flex items-center justify-between">
        <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
          Cấu trúc Mạng lưới Đồ thị (Neo4j)
        </span>
        <span className="font-label-statute text-label-statute px-2 py-0.5 rounded bg-secondary-fixed text-on-secondary-fixed font-semibold">
          Duyệt 1 bước (1-Hop)
        </span>
      </div>

      {/* Interactive SVG Network Map */}
      <div className="w-full h-72 rounded-2xl bg-slate-900 p-4 relative overflow-hidden flex flex-col justify-between shadow-inner">
        <div className="absolute inset-0 opacity-20 pointer-events-none">
          {/* Subtle grid pattern */}
          <div className="w-full h-full border border-slate-700/50 bg-[radial-gradient(#334155_1px,transparent_1px)] [background-size:16px_16px]"></div>
        </div>

        <div className="relative z-10 flex items-center justify-between text-white font-label-statute text-[11px]">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            Tọa độ Đỉnh: Điều 35 (BLLĐ 2019)
          </span>
          <span className="text-slate-400">Cypher: MATCH (d)-[r:REFERS_TO]...</span>
        </div>

        {/* Graph SVG representation */}
        <svg className="w-full h-44 relative z-10" viewBox="0 0 400 180">
          {/* Lines */}
          <line x1="80" y1="90" x2="200" y2="40" stroke="#818cf8" strokeWidth="2" strokeDasharray="4" />
          <line x1="200" y1="40" x2="320" y2="90" stroke="#f59e0b" strokeWidth="2.5" />
          <line x1="200" y1="40" x2="200" y2="140" stroke="#818cf8" strokeWidth="2" />

          {/* Node 1: Chương III */}
          <circle cx="80" cy="90" r="22" fill="#1e293b" stroke="#818cf8" strokeWidth="2" />
          <text x="80" y="93" fill="#ffffff" fontSize="9" textAnchor="middle" fontFamily="JetBrains Mono">
            Chương III
          </text>

          {/* Node 2: Điều 35 (Central) */}
          <circle cx="200" cy="40" r="26" fill="#4f46e5" stroke="#a5b4fc" strokeWidth="3" />
          <text x="200" y="44" fill="#ffffff" fontSize="10" fontWeight="bold" textAnchor="middle" fontFamily="JetBrains Mono">
            Điều 35
          </text>

          {/* Node 3: NĐ 145 Điều 7 (Refers To Target) */}
          <circle cx="320" cy="90" r="24" fill="#d97706" stroke="#fde68a" strokeWidth="2.5" />
          <text x="320" y="94" fill="#ffffff" fontSize="9" fontWeight="bold" textAnchor="middle" fontFamily="JetBrains Mono">
            NĐ145 Đ.7
          </text>

          {/* Node 4: Khoản 1 */}
          <circle cx="200" cy="140" r="18" fill="#1e293b" stroke="#818cf8" strokeWidth="1.5" />
          <text x="200" y="144" fill="#ffffff" fontSize="9" textAnchor="middle" fontFamily="JetBrains Mono">
            Khoản 1
          </text>

          {/* Relationship Edge Labels */}
          <rect x="235" y="55" width="56" height="15" rx="3" fill="#78350f" />
          <text x="263" y="66" fill="#fef3c7" fontSize="8" fontWeight="bold" textAnchor="middle" fontFamily="JetBrains Mono">
            REFERS_TO
          </text>

          <rect x="110" y="55" width="50" height="15" rx="3" fill="#312e81" />
          <text x="135" y="66" fill="#e0e7ff" fontSize="8" textAnchor="middle" fontFamily="JetBrains Mono">
            PART_OF
          </text>
        </svg>

        <div className="relative z-10 flex items-center justify-between text-[11px] font-label-code text-slate-300 bg-slate-800/80 p-2 rounded-lg backdrop-blur">
          <span>Liên kết: Điều 35(1)(d) ──▶ NĐ 145/2020 Điều 7(2)</span>
          <span className="text-amber-400 font-bold">120 Ngày</span>
        </div>
      </div>

      {/* Relationship Edge Cards */}
      <div className="flex flex-col gap-2">
        <span className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
          Các cạnh quan hệ trong phiên:
        </span>

        {/* Edge 1: PART_OF */}
        <div className="p-3 rounded-xl bg-surface-container-lowest border-l-4 border-indigo-600 shadow-xs flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="font-label-code text-indigo-700 font-bold text-[11px]">QUAN HỆ: THUỘC VỀ (PART_OF)</span>
            <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-800">
              Phân cấp cấu trúc
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface">
            <strong>Điều 35</strong> trực thuộc <strong>Chương III: Hợp đồng lao động</strong> (Bộ luật Lao động 2019).
          </p>
        </div>

        {/* Edge 2: REFERS_TO */}
        <div className="p-3 rounded-xl bg-surface-container-lowest border-l-4 border-amber-500 shadow-xs flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="font-label-code text-amber-700 font-bold text-[11px]">QUAN HỆ: THAM CHIẾU (REFERS_TO)</span>
            <span className="font-label-statute text-label-statute px-1.5 py-0.5 rounded bg-amber-50 text-amber-800">
              Dẫn chiếu pháp điển
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface">
            <strong>Điểm d Khoản 1 Điều 35</strong> dẫn chiếu đến <strong>Nghị định 145/2020/NĐ-CP Điều 7</strong> (Ngành nghề đặc thù).
          </p>
        </div>
      </div>
    </div>
  );
};

