'use client';

import React, { useEffect, useState } from 'react';
import { errorMessage } from '../../lib/api';
import type { DocumentRemoval } from '../../lib/types';

type Target = { id: string; title: string };

/** Confirm, run and report the removal of a loaded PDF in one dialog. */
export function RemoveDocumentModal({ target, onRemove, onClose }: {
  target: Target;
  onRemove: (id: string) => Promise<DocumentRemoval>;
  onClose: () => void;
}) {
  const [state, setState] = useState<'confirm' | 'removing' | 'done' | 'failed'>('confirm');
  const [result, setResult] = useState<DocumentRemoval | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && state !== 'removing') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [state, onClose]);

  async function run() {
    setState('removing');
    try {
      setResult(await onRemove(target.id));
      setState('done');
    } catch (e) {
      setError(errorMessage(e));
      setState('failed');
    }
  }

  const icon = state === 'done' ? 'check_circle' : state === 'failed' ? 'error' : 'delete';
  const tone = state === 'done' ? 'bg-emerald-50 text-emerald-700' : 'bg-error-container text-error';
  const heading = state === 'done' ? 'Đã gỡ văn bản' : state === 'failed' ? 'Chưa gỡ được văn bản' : 'Gỡ văn bản PDF';

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="remove-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-[2px] p-4"
      onClick={() => { if (state !== 'removing') onClose(); }}>
      <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl shadow-2xl border border-ink/10 overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 p-4 border-b border-outline-variant/20 bg-surface-container-low">
          <span className={`w-8 h-8 rounded-lg flex items-center justify-center ${tone}`}>
            <span className="material-symbols-outlined text-[20px]">{icon}</span>
          </span>
          <h2 id="remove-title" className="text-[14px] font-semibold text-ink">{heading}</h2>
        </div>

        <div className="p-4 flex flex-col gap-2 text-[13px] text-ink-2">
          <p className="font-medium text-ink">{target.title}</p>
          {(state === 'confirm' || state === 'removing') && (
            <p>
              Văn bản sẽ bị gỡ khỏi kho tra cứu và đồ thị. Các Điều mà PDF này đã ghi đè sẽ được khôi phục từ Pháp điển
              (nếu có). Không hoàn tác được; muốn dùng lại phải nạp lại PDF.
            </p>
          )}
          {state === 'removing' && <p className="text-ink-3">Đang gỡ… có thể mất một lúc nếu cần khôi phục bản Pháp điển.</p>}
          {state === 'done' && result && (
            <ul className="list-disc pl-5 space-y-0.5">
              <li>Xóa {result.deleted_chunks} đoạn tra cứu.</li>
              <li>Xóa {result.graph.deleted_nodes} nút và {result.graph.deleted_edges} cạnh đồ thị
                {result.graph.reset_nodes > 0 && <>; trả lại {result.graph.reset_nodes} nút về bản Pháp điển</>}.</li>
              {result.restored_chunks > 0 && <li>Khôi phục {result.restored_chunks} đoạn từ Pháp điển.</li>}
              {result.warnings.map((w) => <li key={w}>{w}</li>)}
            </ul>
          )}
          {state === 'failed' && <p role="alert" className="p-2.5 rounded-lg bg-error-container text-on-error-container">{error}</p>}
        </div>

        <div className="flex justify-end gap-2 p-4 pt-0">
          {state === 'confirm' || state === 'removing' ? (
            <>
              <button type="button" disabled={state === 'removing'} onClick={onClose}
                className="px-3 py-1.5 rounded-lg text-[13px] bg-surface-container text-ink hover:bg-surface-container-high disabled:opacity-50">Hủy</button>
              <button type="button" disabled={state === 'removing'} onClick={run}
                className="px-3 py-1.5 rounded-lg text-[13px] font-medium bg-error text-on-error hover:bg-opacity-90 disabled:opacity-60">
                {state === 'removing' ? 'Đang gỡ…' : 'Gỡ văn bản'}
              </button>
            </>
          ) : (
            <>
              {state === 'failed' && (
                <button type="button" onClick={run}
                  className="px-3 py-1.5 rounded-lg text-[13px] bg-surface-container text-ink hover:bg-surface-container-high">Thử lại</button>
              )}
              <button type="button" onClick={onClose}
                className="px-3 py-1.5 rounded-lg text-[13px] font-medium bg-secondary text-white hover:bg-opacity-95">Đóng</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
