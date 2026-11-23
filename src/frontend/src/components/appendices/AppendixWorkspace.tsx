'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Download, ExternalLink, FileText, Search } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import type { AppendixItem, AppendixList } from '../../lib/types';
import { Pagination } from '../common/Pagination';
import { RetrievalPanel } from './RetrievalPanel';

const PAGE_SIZE = 20;

const labels: Record<string, string> = {
  reference: 'Tra cứu', form: 'Biểu mẫu', mixed: 'Hỗn hợp', unknown: 'Chưa phân loại',
  needs_review: 'Cần rà soát', auto_accepted: 'Đã nhận diện', reviewed: 'Đã rà soát',
};
const KIND_TONE: Record<string, string> = {
  reference: 'bg-sky-50 text-sky-800', form: 'bg-indigo-50 text-indigo-800',
  mixed: 'bg-violet-50 text-violet-800', unknown: 'bg-slate-100 text-ink-2',
};

// Both panes share one viewport-bound height; the list and the viewer scroll inside it.
const PANE = 'h-[75vh] lg:h-[calc(100vh-190px)] min-h-[520px]';
const field ='w-full h-9 px-3 rounded-lg border border-outline-variant/40 bg-surface-container-lowest text-[13px] text-ink focus:outline-none focus:border-secondary';

/** Appendix catalog browser. `basePath` keeps the host page's own query (e.g. its tab) when a row is opened. */
export function AppendixWorkspace({ basePath = '/appendices', embedded = false }: { basePath?: string; embedded?: boolean }) {
  const router = useRouter();
  const params = useSearchParams();
  const selectedId = params.get('appendix_id') || '';
  const chunkId = params.get('chunk_id') || '';
  const [query, setQuery] = useState('');
  const [document, setDocument] = useState('');
  const [kind, setKind] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [list, setList] = useState<AppendixList | null>(null);
  const [selected, setSelected] = useState<AppendixItem | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);

  // A new page starts at its first row.
  useEffect(() => { listRef.current?.scrollTo({ top: 0 }); }, [page]);

  function open(id: string, chunk?: string) {
    const [path, own = ''] = basePath.split('?');
    const search = new URLSearchParams(own);
    search.set('appendix_id', id);
    if (chunk) search.set('chunk_id', chunk); else search.delete('chunk_id');
    router.replace(path + '?' + search.toString(), { scroll: false });
  }
  /** Change a filter and go back to the first page. */
  const filter = (set: (value: string) => void) => (value: string) => { set(value); setPage(1); };

  useEffect(() => {
    let current = true;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const result = await api.listAppendices({ q: query, document, kind, status, offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE });
        if (current) { setList(result); setError(''); }
      } catch (error) { if (current) setError(errorMessage(error)); }
      finally { if (current) setLoading(false); }
    }, 250);
    return () => { current = false; clearTimeout(timer); };
  }, [query, document, kind, status, page]);
  useEffect(() => {
    let current = true;
    setSelected(null);
    if (selectedId) api.getAppendix(selectedId).then(item => { if (current) setSelected(item); })
      .catch(error => { if (current) setError(errorMessage(error)); });
    return () => { current = false; };
  }, [selectedId]);

  return <div className={embedded ? 'flex flex-col gap-space-md' : 'max-w-[1500px] mx-auto p-4 md:p-6 flex flex-col gap-space-md'}>
    <div className="flex flex-col">
      <h1 className="text-[18px] font-semibold text-ink">Danh mục, phụ lục & biểu mẫu</h1>
      <p className="text-[12.5px] text-ink-3">Tra cứu danh mục, quy trình và biểu mẫu; mở đúng nội dung và file nguồn.</p>
    </div>
    {error && <p role="alert" className="p-3 rounded-xl bg-error-container text-on-error-container text-[12.5px]">{error}</p>}

    <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
      {/* Catalog list */}
      <section className={`lg:col-span-5 ${PANE} rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-sm flex flex-col overflow-hidden`}>
        <div className="shrink-0 p-space-md flex flex-col gap-2.5 border-b border-outline-variant/20">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-semibold text-ink">Danh sách phụ lục</h2>
            {list && <span className="text-[12px] text-ink-3 tabular-nums">{list.total.toLocaleString('vi-VN')} mục</span>}
          </div>
          <label className="relative block">
            <span className="sr-only">Tìm kiếm</span>
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 pointer-events-none" />
            <input value={query} onChange={e => filter(setQuery)(e.target.value)} type="search"
              placeholder="Tên phụ lục, số mẫu, số hiệu…" className={`${field} pl-9`} />
          </label>
          <select aria-label="Văn bản" value={document} onChange={e => filter(setDocument)(e.target.value)} className={field}>
            <option value="">Tất cả văn bản</option>
            {list?.documents.map(item => <option key={item.document_id} value={item.document_id}>{item.document}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <select aria-label="Loại" value={kind} onChange={e => filter(setKind)(e.target.value)} className={field}>
              <option value="">Tất cả loại</option>
              {['reference', 'form', 'mixed', 'unknown'].map(key => <option key={key} value={key}>{labels[key]}</option>)}
            </select>
            <select aria-label="Trạng thái rà soát" value={status} onChange={e => filter(setStatus)(e.target.value)} className={field}>
              <option value="">Tất cả trạng thái</option>
              {['needs_review', 'auto_accepted', 'reviewed'].map(key => <option key={key} value={key}>{labels[key]}</option>)}
            </select>
          </div>
        </div>

        <ul ref={listRef} className={`flex-1 min-h-0 overflow-y-auto overscroll-contain legal-scroll flex flex-col p-1.5 gap-0.5 transition-opacity ${loading ? 'opacity-50' : ''}`} aria-busy={loading}>
          {list?.items.map(item => {
            const active = selectedId === item.appendix_id;
            return <li key={item.appendix_id}>
              <button type="button" onClick={() => open(item.appendix_id)} aria-current={active ? 'true' : undefined}
                className={`w-full text-left px-3 py-2.5 rounded-lg flex flex-col gap-1 border transition-colors ${
                  active ? 'bg-secondary/10 border-secondary/30' : 'border-transparent hover:bg-surface-container-low'
                }`}>
                <span className={`text-[13px] font-semibold leading-snug line-clamp-2 ${active ? 'text-secondary' : 'text-ink'}`}>
                  Phụ lục {item.number} · {item.title}
                </span>
                <span className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-ink-3">
                  <span className="truncate max-w-[60%]">{item.document_number}</span>
                  <span className={`px-1.5 py-0.5 rounded font-medium ${KIND_TONE[item.kind] || KIND_TONE.unknown}`}>{labels[item.kind] || item.kind}</span>
                  {item.review_status === 'needs_review' && <span className="px-1.5 py-0.5 rounded font-medium bg-amber-50 text-amber-800">Cần rà soát</span>}
                </span>
              </button>
            </li>;
          })}
          {!list && loading && <li className="py-10 text-center text-[12.5px] text-ink-3" role="status">Đang tải danh sách…</li>}
          {list?.total === 0 && <li className="py-10 text-center text-[12.5px] text-ink-3">Không có phụ lục phù hợp.</li>}
        </ul>

        <div className="shrink-0 px-space-md py-2.5 border-t border-outline-variant/20 bg-surface-container-low/60">
          <Pagination page={page} pageSize={PAGE_SIZE} total={list?.total ?? 0} disabled={loading} onChange={setPage} />
        </div>

        {list && <details className="shrink-0 px-space-md py-2.5 border-t border-outline-variant/20 text-[12px] text-ink-3">
          <summary className="cursor-pointer select-none">Độ phủ thu thập: {list.documents.length} nguồn văn bản</summary>
          <ul className="mt-2 space-y-1.5 max-h-32 overflow-y-auto legal-scroll">{list.documents.map(item => <li key={item.document_id}>{item.document}: {item.appendices} phần · {item.download_status} · {item.extraction_status}</li>)}</ul>
        </details>}
      </section>

      {/* Viewer */}
      <section id="appendix-viewer" className={`lg:col-span-7 ${PANE} rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-sm p-space-md min-w-0 flex flex-col gap-3 overflow-hidden`}>
        {!selected ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
            <div className="w-12 h-12 rounded-2xl bg-secondary-fixed flex items-center justify-center text-secondary"><FileText size={24} /></div>
            <p className="text-[13px] text-ink-3 max-w-sm">
              {selectedId ? 'Đang tải phụ lục…' : 'Chọn một phụ lục trong danh sách để xem nội dung và tải file nguồn.'}
            </p>
          </div>
        ) : <>
          <div className="flex flex-col gap-1">
            <span className="text-[12px] text-ink-3">{selected.document_number} · Phụ lục {selected.number}</span>
            <h2 className="text-[16px] font-semibold text-ink leading-snug">{selected.title}</h2>
            <span className="flex flex-wrap gap-1.5 text-[11.5px]">
              <span className={`px-1.5 py-0.5 rounded font-medium ${selected.review_status === 'needs_review' ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-800'}`}>
                {labels[selected.review_status] || selected.review_status}
              </span>
              {selected.effect_status && <span className="px-1.5 py-0.5 rounded font-medium bg-surface-container text-ink-2">{selected.effect_status}</span>}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <a href={selected.view_url + '?download=true'}
              className="h-8 px-3 rounded-lg bg-secondary text-white text-[12.5px] font-medium flex items-center gap-1.5 hover:opacity-90">
              <Download size={15} />Tải phụ lục HTML
            </a>
            {selected.files?.map(file => <a key={file.artifact_id} href={file.download_url} target="_blank" rel="noopener noreferrer"
              className="h-8 px-3 rounded-lg border border-outline-variant/40 text-ink text-[12.5px] font-medium flex items-center gap-1.5 hover:bg-surface-container">
              <Download size={15} />{file.format.toUpperCase()} nguồn{file.available === false ? ' · thiếu file' : ''}
            </a>)}
            {selected.source_url && <a target="_blank" rel="noopener noreferrer" href={selected.source_url}
              className="h-8 px-3 rounded-lg border border-outline-variant/40 text-ink text-[12.5px] font-medium flex items-center gap-1.5 hover:bg-surface-container">
              <ExternalLink size={15} />Mở nguồn
            </a>}
          </div>
          <p className="text-[11.5px] text-ink-3">File nguồn có thể chứa toàn văn và nhiều phụ lục; HTML là phần nội dung đã tách.</p>
          <iframe title="Nội dung phụ lục" sandbox="allow-scripts"
            src={selected.view_url + (chunkId ? '?chunk_id=' + encodeURIComponent(chunkId) : '')}
            className="w-full flex-1 min-h-0 rounded-lg border border-outline-variant/30 bg-white" />
        </>}
      </section>
    </div>

    <RetrievalPanel onView={(id, chunk) => { open(id, chunk); window.document.getElementById('appendix-viewer')?.scrollIntoView({ behavior: 'smooth' }); }} />
  </div>;
}
