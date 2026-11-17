'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, errorMessage } from '../../lib/api';
import type { AppendixItem, AppendixList, HealthResponse } from '../../lib/types';
import { RetrievalPanel } from '../../components/appendices/RetrievalPanel';

const labels: Record<string, string> = {
  reference: 'Tra cứu', form: 'Biểu mẫu', mixed: 'Hỗn hợp', unknown: 'Chưa phân loại',
  needs_review: 'Cần rà soát', auto_accepted: 'Đã nhận diện', reviewed: 'Đã rà soát',
  connected: 'Đã kết nối', unavailable: 'Chưa kết nối', not_checked: 'Chưa kiểm tra',
};

function Workspace() {
  const router = useRouter();
  const params = useSearchParams();
  const selectedId = params.get('appendix_id') || '';
  const chunkId = params.get('chunk_id') || '';
  const [query, setQuery] = useState('');
  const [document, setDocument] = useState('');
  const [kind, setKind] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [list, setList] = useState<AppendixList | null>(null);
  const [selected, setSelected] = useState<AppendixItem | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [probing, setProbing] = useState(false);

  function open(id: string, chunk?: string) {
    const search = new URLSearchParams({ appendix_id: id });
    if (chunk) search.set('chunk_id', chunk);
    router.replace('/appendices?' + search.toString(), { scroll: false });
  }
  useEffect(() => {
    let current = true;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const result = await api.listAppendices({ q: query, document, kind, status, offset, limit: 50 });
        if (current) { setList(result); setError(''); }
      } catch (error) { if (current) setError(errorMessage(error)); }
      finally { if (current) setLoading(false); }
    }, 250);
    return () => { current = false; clearTimeout(timer); };
  }, [query, document, kind, status, offset]);
  useEffect(() => {
    let current = true;
    setSelected(null);
    if (selectedId) api.getAppendix(selectedId).then(item => { if (current) setSelected(item); })
      .catch(error => { if (current) setError(errorMessage(error)); });
    return () => { current = false; };
  }, [selectedId]);
  useEffect(() => { api.health().then(setHealth).catch(error => setError(errorMessage(error))); }, []);
  async function probe() {
    setProbing(true);
    try { setHealth(await api.health(true)); }
    catch (error) { setError(errorMessage(error)); }
    finally { setProbing(false); }
  }
  return <main className="max-w-[1500px] mx-auto p-4 md:p-6 space-y-5">
    <div className="flex flex-wrap justify-between items-center gap-3">
      <div><p className="text-xs font-semibold text-secondary uppercase tracking-wider">Kho dữ liệu Lao động</p>
        <h1 className="text-2xl font-bold mt-1">Phụ lục & kiểm tra truy hồi</h1>
        <p className="text-sm text-slate-500 mt-1">Tra cứu danh mục, quy trình và biểu mẫu; mở đúng nội dung và file nguồn.</p></div>
      <button disabled={probing} onClick={probe} className="border rounded-xl px-4 py-2 bg-white disabled:opacity-50">
        {probing ? 'Đang kiểm tra…' : 'Kiểm tra kết nối'}</button>
    </div>
    {health && <div className="flex flex-wrap gap-2 text-xs" aria-live="polite">
      <span className="rounded-full bg-white border px-3 py-2">{health.data.appendices} phụ lục · {health.data.chunks} chunk</span>
      <span className="rounded-full bg-amber-50 border px-3 py-2">{health.data.needs_review} cần rà soát</span>
      <span className="rounded-full bg-white border px-3 py-2">Qdrant: {labels[health.qdrant.connection] || health.qdrant.connection}</span>
      <span className="rounded-full bg-white border px-3 py-2">Neo4j: {labels[health.neo4j.connection] || health.neo4j.connection}</span>
      <span className="rounded-full bg-white border px-3 py-2">R2: {health.storage.r2_verified_files} file đã xác minh · {labels[health.storage.r2.connection] || health.storage.r2.connection}</span>
    </div>}
    {error && <p role="alert" className="bg-red-50 text-red-800 border border-red-200 rounded-xl p-3">{error}</p>}
    <div className="grid lg:grid-cols-[minmax(300px,0.85fr)_minmax(0,1.4fr)] gap-5">
      <section className="rounded-2xl bg-white border p-4 space-y-3">
        <h2 className="font-bold">Danh sách phụ lục {list && <span className="text-slate-500 font-normal">({list.total})</span>}</h2>
        <label className="block text-sm">Tìm kiếm<input value={query} onChange={e => { setQuery(e.target.value); setOffset(0); }}
          type="search" placeholder="Tên phụ lục, số mẫu, số hiệu…" className="border rounded-lg p-2 block w-full mt-1" /></label>
        <label className="block text-sm">Văn bản<select value={document} onChange={e => { setDocument(e.target.value); setOffset(0); }}
          className="border rounded-lg p-2 block w-full mt-1"><option value="">Tất cả văn bản</option>
          {list?.documents.map(item => <option key={item.document_id} value={item.document_id}>{item.document}</option>)}</select></label>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">Loại<select value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }} className="border rounded-lg p-2 block w-full mt-1">
            <option value="">Tất cả loại</option>{['reference', 'form', 'mixed', 'unknown'].map(key => <option key={key} value={key}>{labels[key]}</option>)}</select></label>
          <label className="text-sm">Rà soát<select value={status} onChange={e => { setStatus(e.target.value); setOffset(0); }} className="border rounded-lg p-2 block w-full mt-1">
            <option value="">Tất cả trạng thái</option>{['needs_review', 'auto_accepted', 'reviewed'].map(key => <option key={key} value={key}>{labels[key]}</option>)}</select></label>
        </div>
        {loading && <p className="text-sm text-slate-500" role="status">Đang tải danh sách…</p>}
        <div className="max-h-[520px] overflow-y-auto divide-y">
          {list?.items.map(item => <button key={item.appendix_id} onClick={() => open(item.appendix_id)}
            className={'block text-left w-full p-3 rounded-lg transition-colors ' + (selectedId === item.appendix_id ? 'bg-indigo-50' : 'hover:bg-slate-50')}>
            <span className="text-sm font-semibold">Phụ lục {item.number} · {item.title}</span>
            <span className="block text-xs text-slate-500 mt-1">{item.document_number} · {labels[item.kind] || item.kind}</span>
            {item.review_status === 'needs_review' && <span className="text-xs text-amber-700">Cần rà soát</span>}
          </button>)}
          {list?.total === 0 && <p className="py-6 text-sm text-slate-500">Không có phụ lục phù hợp.</p>}
        </div>
        <div className="flex justify-between items-center text-sm">
          <button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))} className="disabled:opacity-40">← Trước</button>
          <span>{list && list.total > 0 ? (offset + 1) + '–' + Math.min(offset + 50, list.total) + ' / ' + list.total : '0 kết quả'}</span>
          <button disabled={!list || offset + 50 >= list.total} onClick={() => setOffset(offset + 50)} className="disabled:opacity-40">Tiếp →</button>
        </div>
        {list && <details className="text-xs text-slate-500 pt-3 border-t"><summary className="cursor-pointer">Độ phủ thu thập: {list.documents.length} nguồn văn bản</summary>
          <ul className="mt-2 space-y-2">{list.documents.map(item => <li key={item.document_id}>{item.document}: {item.appendices} phần · {item.download_status} · {item.extraction_status}</li>)}</ul>
        </details>}
      </section>
      <section id="appendix-viewer" className="rounded-2xl bg-white border p-4 min-w-0">
        <h2 className="font-bold mb-3">Nội dung & nguồn</h2>
        {!selected ? <p className="text-slate-500 text-sm p-8">{selectedId ? 'Đang tải phụ lục…' : 'Chọn một phụ lục để xem nội dung và tải file nguồn.'}</p>
          : <div className="space-y-3">
            <p className="text-xs text-secondary">{selected.document_number} · Phụ lục {selected.number}</p>
            <h3 className="font-semibold">{selected.title}</h3>
            <p className="text-xs text-slate-500">{labels[selected.review_status] || selected.review_status} · {selected.effect_status}</p>
            <div className="flex gap-3 flex-wrap text-sm text-secondary">
              <a href={selected.view_url + '?download=true'}>Tải phụ lục HTML</a>
              {selected.source_url && <a target="_blank" rel="noopener noreferrer" href={selected.source_url}>Mở nguồn ↗</a>}
              {selected.files?.map(file => <a key={file.artifact_id} href={file.download_url} target="_blank" rel="noopener noreferrer">
                Tải {file.format.toUpperCase()} nguồn{file.available === false ? ' · thiếu file' : ''}</a>)}
            </div>
            <p className="text-xs text-slate-500">File nguồn có thể chứa toàn văn và nhiều phụ lục; HTML là phần nội dung đã tách.</p>
            <iframe title="Nội dung phụ lục" sandbox="allow-scripts"
              src={selected.view_url + (chunkId ? '?chunk_id=' + encodeURIComponent(chunkId) : '')}
              className="w-full min-h-[550px] border rounded-xl" />
          </div>}
      </section>
    </div>
    <RetrievalPanel onView={(id, chunk) => { open(id, chunk); window.document.getElementById('appendix-viewer')?.scrollIntoView({ behavior: 'smooth' }); }} />
  </main>;
}

export default function AppendicesPage() {
  return <Suspense fallback={<p className="p-6">Đang mở kho phụ lục…</p>}><Workspace /></Suspense>;
}
