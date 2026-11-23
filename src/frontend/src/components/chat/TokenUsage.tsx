'use client';

import React from 'react';
import type { TokenUsage as TokenUsageData } from '../../lib/types';

const stages: Record<string, string> = {
  session_title: 'Đặt tên phiên', intent: 'Phân loại ý định', query_rewrite: 'Viết lại câu hỏi',
  retrieval: 'Truy hồi chứng cứ', rerank: 'Xếp hạng chứng cứ', appendices: 'Bổ sung phụ lục',
  generation: 'Sinh câu trả lời', verification: 'Đối chiếu trích dẫn', other: 'Khác',
};
const tokens = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString('vi-VN');

export function TokenUsage({ usage }: { usage?: TokenUsageData | null }) {
  if (!usage) return <p className="font-label-code text-label-code text-on-surface-variant">Token LLM: Chưa có số liệu.</p>;
  const failed = usage.calls.filter(call => call.status === 'failed').length;
  const visibleStages = Array.from(new Set([...Object.keys(stages).filter(stage => stage !== 'other'), ...usage.executed_stages,
    ...usage.calls.map(call => call.stage)]));
  return <details className="min-w-0 rounded-xl border border-outline-variant/30 bg-surface-container-low p-space-sm font-label-code text-label-code text-on-surface-variant">
    <summary className="cursor-pointer leading-relaxed">
      <span className="font-semibold">Token LLM{usage.status === 'complete' ? '' : ' đã ghi nhận'}</span>
      {usage.status === 'unavailable' ? ' · Chưa có số liệu' : <>
        {' · Đầu vào: '}{tokens(usage.input_tokens)}{' · Đầu ra: '}{tokens(usage.output_tokens)}{' · Tổng: '}{tokens(usage.total_tokens)}
      </>}
      {usage.status === 'partial' && <span> · Chưa đủ số liệu</span>}
      {failed > 0 && <span> · {failed} lượt gọi lỗi</span>}
      <span className="ml-2 text-secondary underline">Chi tiết từng bước</span>
    </summary>
    <p className="mt-space-sm">Đầu vào gồm hướng dẫn hệ thống, lịch sử, câu hỏi và chứng cứ được gửi ở mỗi lượt gọi. Số liệu lấy từ nhà cung cấp, không phải ước tính hay giới hạn đầu ra.</p>
    {usage.status !== 'complete' && <p className="mt-1">Tổng chỉ cộng các số đã được báo cáo; phần chưa có số liệu hiển thị “—”.</p>}
    <div className="mt-space-sm overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <caption className="sr-only">Token LLM theo từng bước xử lý</caption>
        <thead><tr className="border-b border-outline-variant/30">
          {['Bước xử lý', 'Trạng thái / Model', 'Đầu vào', 'Đầu ra', 'Tổng'].map(label => <th key={label} scope="col" className="py-2 pr-3 font-semibold whitespace-nowrap">{label}</th>)}
        </tr></thead>
        <tbody>{visibleStages.flatMap(stage => {
          const calls = usage.calls.filter(call => call.stage === stage);
          if (!calls.length) {
            const executed = usage.executed_stages.includes(stage);
            return [<tr key={stage} className="border-b border-outline-variant/20">
              <th scope="row" className="py-2 pr-3 font-normal">{stages[stage] || stage}</th>
              <td className="py-2 pr-3">{executed ? 'Không gọi LLM' : 'Không chạy'}</td>
              {[0, 1, 2].map(index => <td key={index} className="py-2 pr-3 tabular-nums">{executed ? '0' : '—'}</td>)}
            </tr>];
          }
          return calls.map((call, index) => <tr key={`${stage}-${index}`} className="border-b border-outline-variant/20 align-top">
            <th scope="row" className="py-2 pr-3 font-normal">{stages[stage] || stage}{calls.length > 1 ? ` (${index + 1})` : ''}</th>
            <td className="py-2 pr-3">
              <div>{call.status === 'failed' ? `Lỗi${call.http_status ? ` HTTP ${call.http_status}` : ''}` : call.total_tokens == null ? 'Chưa có số liệu' : 'Đã nhận số liệu'}</div>
              <div className="break-words">{call.provider} · {call.model}</div>
              {call.requested_tokens != null && <div className="mt-1">Yêu cầu bị từ chối: {tokens(call.requested_tokens)} token (không cộng vào tổng đã xử lý).</div>}
              {call.cached_input_tokens != null && <div>Trong đầu vào có {tokens(call.cached_input_tokens)} token cache.</div>}
              {call.reasoning_tokens != null && <div>Trong đầu ra có {tokens(call.reasoning_tokens)} token suy luận.</div>}
            </td>
            <td className="py-2 pr-3 tabular-nums">{tokens(call.input_tokens)}</td>
            <td className="py-2 pr-3 tabular-nums">{tokens(call.output_tokens)}</td>
            <td className="py-2 pr-3 tabular-nums">{tokens(call.total_tokens)}</td>
          </tr>);
        })}</tbody>
      </table>
    </div>
  </details>;
}
