'use client';

import React, { useMemo, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { diffWords } from '../../lib/textDiff';
import type { AmendmentChange, ArticleChange, ArticleChangeStatus, TaskChanges } from '../../lib/types';

const STATUS: Record<ArticleChangeStatus, { label: string; tone: string; hint: string }> = {
  new: { label: 'Mới', tone: 'bg-emerald-100 text-emerald-900', hint: 'Chưa có trong kho, sẽ được thêm.' },
  replaced: { label: 'Thay thế', tone: 'bg-amber-100 text-amber-900', hint: 'Nội dung khác bản trong kho; bản PDF sẽ thay thế.' },
  metadata: { label: 'Cập nhật thông tin', tone: 'bg-sky-100 text-sky-900', hint: 'Cùng nội dung, chỉ đổi thông tin hiệu lực/phiên bản.' },
  unchanged: { label: 'Không đổi', tone: 'bg-slate-100 text-ink-2', hint: 'Giống hệt bản trong kho.' },
  kept: { label: 'Kho có bản mới hơn', tone: 'bg-red-100 text-red-900', hint: 'Bản trong kho mới hơn; hệ thống sẽ từ chối lập chỉ mục PDF này.' },
  missing: { label: 'Thiếu trong PDF', tone: 'bg-orange-100 text-orange-900', hint: 'Có trong kho nhưng không có trong bản này (OCR sót, hoặc đã sửa đi); bản cũ được giữ trừ khi chọn xóa.' },
};
const ORDER: ArticleChangeStatus[] = ['kept', 'replaced', 'new', 'missing', 'metadata', 'unchanged'];

type Filter = 'changed' | 'all' | ArticleChangeStatus;

function SideBySide({ before, after, beforeTitle, afterTitle }: { before: string | null; after: string | null; beforeTitle: string; afterTitle: string }) {
  const parts = useMemo(() => diffWords(before ?? '', after ?? ''), [before, after]);
  const column = (title: string, side: 'removed' | 'added', empty: string, present: boolean) => (
    <div className="flex flex-col min-w-0 rounded-md border border-outline-variant/25 bg-white">
      <div className="px-2.5 py-1 text-[11.5px] font-semibold text-ink-3 bg-surface-container-low border-b border-outline-variant/20">{title}</div>
      <div className="p-2.5 text-[12px] leading-relaxed whitespace-pre-wrap break-words max-h-[320px] overflow-y-auto">
        {!present ? <span className="text-ink-3 italic">{empty}</span> : parts.map((part, idx) =>
          part.kind === 'same' ? <span key={idx}>{part.text}</span>
            : part.kind === side ? (
              <mark key={idx} className={side === 'removed' ? 'bg-red-100 text-red-900 line-through decoration-red-400' : 'bg-emerald-100 text-emerald-900'}>{part.text}</mark>
            ) : null)}
      </div>
    </div>
  );
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
      {column(beforeTitle, 'removed', 'Không có', before !== null)}
      {column(afterTitle, 'added', 'Không có', after !== null)}
    </div>
  );
}

function ArticleRow({ item, prune }: { item: ArticleChange; prune?: { checked: boolean; toggle: () => void } }) {
  const [open, setOpen] = useState(item.status === 'replaced' || item.status === 'kept');
  const meta = item.status ? STATUS[item.status] : null;
  return (
    <li className="border border-outline-variant/25 rounded-lg bg-surface-container-lowest">
      {prune && (
        <label className="flex items-center gap-2 px-3 pt-2 text-[12px] text-ink cursor-pointer">
          <input type="checkbox" checked={prune.checked} onChange={prune.toggle} className="accent-red-600" />
          <span>{prune.checked ? 'Xóa khỏi kho khi nạp lại' : 'Giữ trong kho'}</span>
        </label>
      )}
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-surface-container-low rounded-lg">
        <span className="material-symbols-outlined text-[16px] text-ink-3">{open ? 'expand_more' : 'chevron_right'}</span>
        <span className="font-semibold text-[12px] text-ink shrink-0">{item.label}</span>
        <span className="text-[12px] text-ink-3 truncate flex-1">{item.title}</span>
        {meta ? <span title={meta.hint} className={`px-1.5 py-0.5 rounded text-[11.5px] font-semibold shrink-0 ${meta.tone}`}>{meta.label}</span>
          : <span className="px-1.5 py-0.5 rounded text-[11.5px] font-semibold shrink-0 bg-slate-100 text-ink-2">Chưa so sánh được</span>}
      </button>
      {open && (
        <div className="px-3 pb-3 flex flex-col gap-1.5">
          {meta && <p className="text-[11.5px] text-ink-3">{meta.hint}{item.old_source ? ` Bản trong kho: nguồn ${item.old_source === 'phap_dien' ? 'Pháp điển' : 'PDF'}${item.old_version_date ? `, phiên bản ${item.old_version_date}` : ''}.` : ''}</p>}
          <SideBySide before={item.old_text} after={item.new_text} beforeTitle="Bản trong kho" afterTitle="Bản từ PDF đã rà soát" />
        </div>
      )}
    </li>
  );
}

function AmendmentRow({ item }: { item: AmendmentChange }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="border border-outline-variant/25 rounded-lg bg-surface-container-lowest">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="w-full flex flex-wrap items-center gap-2 px-3 py-2 text-left hover:bg-surface-container-low rounded-lg">
        <span className="material-symbols-outlined text-[16px] text-ink-3">{open ? 'expand_more' : 'chevron_right'}</span>
        {item.actions.map((action) => (
          <span key={action} className="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-900 text-[11.5px] font-semibold">{action}</span>
        ))}
        <span className="font-semibold text-[12px] text-ink">{item.scope ? `${item.scope} ` : ''}{item.target_article}</span>
        <span className="text-[12px] text-ink-3">— {item.target_document}</span>
        <span className="text-[11.5px] text-ink-3 ml-auto">theo {item.source_article}{item.source_clause ? `, ${item.source_clause}` : ''}</span>
        <span className={`px-1.5 py-0.5 rounded text-[11.5px] font-semibold ${item.target_indexed ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-100 text-ink-2'}`}>
          {item.target_indexed === null ? 'Chưa kiểm tra kho' : item.target_indexed ? 'Đang có trong kho' : 'Chưa có trong kho'}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="rounded-md border border-outline-variant/25 bg-white">
            <div className="px-2.5 py-1 text-[11.5px] font-semibold text-ink-3 bg-surface-container-low border-b border-outline-variant/20">Nội dung hiện hành trong kho</div>
            <p className="p-2.5 text-[12px] leading-relaxed whitespace-pre-wrap max-h-[280px] overflow-y-auto">
              {item.current_text ?? <span className="italic text-ink-3">Kho chưa có Điều này.</span>}
            </p>
          </div>
          <div className="rounded-md border border-indigo-200 bg-white">
            <div className="px-2.5 py-1 text-[11.5px] font-semibold text-indigo-900 bg-indigo-50 border-b border-indigo-200">Quy định sửa đổi trong PDF</div>
            <p className="p-2.5 text-[12px] leading-relaxed whitespace-pre-wrap max-h-[280px] overflow-y-auto">{item.instruction}</p>
          </div>
        </div>
      )}
    </li>
  );
}

/** Step 3 of a PDF upload: what confirming would add, replace or amend. */
/** reindex: the task already has a review in the corpus; missing PDF Dieu then default to deletion,
 *  reported through onPruneChange (null until an analysis ran). */
export const ChangeReview: React.FC<{
  taskId: string;
  hasUnsavedEdits: boolean;
  reindex?: boolean;
  prune?: string[] | null;
  onPruneChange?: (prune: string[] | null) => void;
}> = ({ taskId, hasUnsavedEdits, reindex = false, prune = null, onPruneChange }) => {
  const [changes, setChanges] = useState<TaskChanges | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Filter>('changed');

  const analyze = async () => {
    setLoading(true); setError('');
    try {
      const result = await api.getTaskChanges(taskId);
      setChanges(result);
      // Re-indexing a corrected review: what the review no longer has goes, unless unticked.
      onPruneChange?.(reindex ? result.articles.filter((a) => a.status === 'missing' && a.deletable).map((a) => a.article_id) : []);
    }
    catch (e) { setError(errorMessage(e)); setChanges(null); onPruneChange?.(null); }
    finally { setLoading(false); }
  };

  const counts = useMemo(() => {
    const result = Object.fromEntries(ORDER.map((s) => [s, 0])) as Record<ArticleChangeStatus, number>;
    for (const item of changes?.articles ?? []) if (item.status) result[item.status] += 1;
    return result;
  }, [changes]);

  const visible = (changes?.articles ?? []).filter((item) =>
    filter === 'all' || item.status === null ? true
      : filter === 'changed' ? item.status !== 'unchanged'
        : item.status === filter);

  const chip = (key: Filter, label: string, count?: number) => (
    <button key={key} type="button" onClick={() => setFilter(key)}
      className={`px-2 py-0.5 rounded text-[11.5px] font-semibold transition-colors ${filter === key ? 'bg-secondary text-white' : 'bg-surface-container text-ink hover:bg-surface-container-high'}`}>
      {label}{count !== undefined ? ` (${count})` : ''}
    </button>
  );

  return (
    <section className="rounded-lg border border-outline-variant/25 bg-surface-container-low/70 overflow-hidden" aria-label="So sánh thay đổi">
      <div className="px-3 py-2 flex items-center justify-between gap-2 flex-wrap bg-surface-container-low border-b border-outline-variant/20">
        <div className="flex items-center gap-2 text-[12px] font-semibold text-ink">
          <span className="material-symbols-outlined text-[16px] text-secondary">difference</span>
          <span>So sánh thay đổi với kho dữ liệu</span>
          {changes && <span className="font-normal text-ink-3">· {changes.document_number || changes.document_id}</span>}
        </div>
        <button type="button" onClick={() => void analyze()} disabled={loading || hasUnsavedEdits}
          title={hasUnsavedEdits ? 'Lưu trang đang sửa trước khi phân tích' : undefined}
          className="px-3 py-1 rounded bg-secondary/10 hover:bg-secondary/20 text-secondary border border-secondary/30 text-[11.5px] font-semibold flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed">
          <span className={`material-symbols-outlined text-[15px] ${loading ? 'animate-spin' : ''}`}>{loading ? 'autorenew' : 'compare_arrows'}</span>
          <span>{loading ? 'Đang phân tích…' : changes ? 'Phân tích lại' : 'Phân tích thay đổi'}</span>
        </button>
      </div>

      <div className="p-3 flex flex-col gap-3">
        {!changes && !error && !loading && (
          <p className="text-[12px] text-ink-3">
            Sau khi rà soát xong các trang, bấm <strong>Phân tích thay đổi</strong> để xem Điều nào mới, Điều nào thay thế bản đang có,
            và các Điều của văn bản khác mà PDF này sửa đổi. Chưa có gì được ghi vào kho ở bước này.
          </p>
        )}
        {error && <p role="alert" className="text-[12px] text-red-700">{error}</p>}

        {changes && (
          <>
            {changes.store === 'unavailable' && (
              <p className="text-[12px] p-2 rounded bg-amber-50 border border-amber-200 text-amber-900">
                Không đọc được kho dữ liệu nên chưa so sánh được; danh sách dưới đây chỉ là các Điều tách từ PDF.
                {changes.store_error ? ` (${changes.store_error})` : ''}
              </p>
            )}
            {counts.kept > 0 && (
              <p className="text-[12px] p-2 rounded bg-red-50 border border-red-200 text-red-800">
                {counts.kept} Điều trong kho có phiên bản mới hơn PDF này; hệ thống sẽ từ chối lập chỉ mục nếu xác nhận.
              </p>
            )}

            {reindex && prune && prune.length > 0 && (
              <p className="text-[12px] p-2 rounded bg-orange-50 border border-orange-200 text-orange-900">
                Nạp lại sẽ xóa {prune.length} Điều không còn trong bản này khỏi kho (xem nhóm "Thiếu trong PDF"; bỏ chọn để giữ).
              </p>
            )}

            {changes.store === 'connected' && (
              <div className="flex flex-wrap items-center gap-1.5">
                {chip('changed', 'Có thay đổi', changes.articles.filter((a) => a.status !== 'unchanged').length)}
                {ORDER.filter((s) => counts[s] > 0).map((s) => chip(s, STATUS[s].label, counts[s]))}
                {chip('all', 'Tất cả', changes.articles.length)}
              </div>
            )}

            {visible.length ? (
              <ul className="flex flex-col gap-1.5">{visible.map((item) => (
                <ArticleRow key={item.article_id} item={item}
                  prune={reindex && item.status === 'missing' && item.deletable && prune && onPruneChange ? {
                    checked: prune.includes(item.article_id),
                    toggle: () => onPruneChange(prune.includes(item.article_id)
                      ? prune.filter((id) => id !== item.article_id) : [...prune, item.article_id]),
                  } : undefined} />
              ))}</ul>
            ) : (
              <p className="text-[12px] text-ink-3">Không có Điều nào trong nhóm này.</p>
            )}

            {changes.amendments.length > 0 && (
              <div className="flex flex-col gap-1.5 pt-2 border-t border-outline-variant/20">
                <span className="text-[13px] font-semibold text-ink">
                  Văn bản này sửa đổi {changes.amendments.length} quy định của văn bản khác
                </span>
                <ul className="flex flex-col gap-1.5">
                  {changes.amendments.map((item, idx) => <AmendmentRow key={`${item.target_article_id}-${idx}`} item={item} />)}
                </ul>
              </div>
            )}

            {changes.replaced_documents.length > 0 && (
              <div className="flex flex-col gap-1 pt-2 border-t border-outline-variant/20 text-[12px]">
                <span className="text-[13px] font-semibold text-ink">Văn bản bị thay thế / hết hiệu lực</span>
                {changes.replaced_documents.map((doc) => (
                  <span key={doc.document_id}>
                    • {doc.document}{' '}
                    <span className="text-ink-3">
                      ({doc.indexed === null ? 'chưa kiểm tra kho' : doc.indexed ? 'đang có trong kho' : 'chưa có trong kho'})
                    </span>
                  </span>
                ))}
              </div>
            )}

            {changes.warnings.length > 0 && (
              <details className="text-[11.5px] text-amber-800">
                <summary className="cursor-pointer">{changes.warnings.length} cảnh báo khi so sánh</summary>
                <ul className="mt-1 space-y-0.5">{changes.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
              </details>
            )}
          </>
        )}
      </div>
    </section>
  );
};
