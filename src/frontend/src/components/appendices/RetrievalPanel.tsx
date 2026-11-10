'use client';

import { FormEvent, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import type { GraphPath, RetrievedChunk, RetrievalResult } from '../../lib/types';

function Chunk({ hit, onView }: { hit: RetrievedChunk; onView: (id: string, chunk?: string) => void }) {
  return <details className="rounded-xl border border-outline-variant/40 p-3 bg-white">
    <summary className="cursor-pointer font-semibold text-sm">
      {hit.rank ? '#' + hit.rank + ' · ' : ''}{hit.citation || hit.ten || hit.chunk_id}
      {hit.score != null && <span className="ml-2 font-mono text-secondary">{hit.score.toFixed(4)}</span>}
    </summary>
    <code className="block mt-2 text-xs break-all text-slate-500">{hit.chunk_id}</code>
    <p className="whitespace-pre-wrap text-sm leading-6 mt-2">{hit.text}</p>
    {hit.appendix_id && hit.view_url && <button className="text-secondary underline mt-3 text-sm"
      onClick={() => onView(hit.appendix_id!, hit.chunk_id)}>Xem vị trí trong phụ lục</button>}
  </details>;
}

function PathView({ path }: { path: GraphPath }) {
  return <div className="flex flex-wrap gap-2 items-center text-xs py-2">
    {path.nodes.map((node, index) => <span className="contents" key={node.id + index}>
      {index > 0 && <span className="text-slate-500">
        {path.edges[index - 1]?.source === path.nodes[index - 1].id ? '— ' + path.edges[index - 1]?.type + ' →' : '← ' + path.edges[index - 1]?.type + ' —'}
      </span>}
      <span title={node.id} className="p-2 rounded-lg bg-indigo-50 border border-indigo-100">
        {node.appendix_id ? 'Phụ lục ' + (node.appendix_number || node.appendix_id)
          : node.article_number ? 'Điều ' + node.article_number : node.title || node.document_id || node.id}
        {node.document_id && <small className="block text-slate-500">{node.document_id}</small>}
      </span>
    </span>)}
  </div>;
}

export function RetrievalPanel({ onView }: { onView: (id: string, chunk?: string) => void }) {
  const [question, setQuestion] = useState('');
  const [topK, setTopK] = useState(8);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RetrievalResult | null>(null);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true); setError(''); setResult(null);
    try { setResult(await api.inspect(question.trim(), topK)); }
    catch (error) { setError(errorMessage(error)); }
    finally { setBusy(false); }
  }
  return <section className="bg-white border border-outline-variant/40 rounded-2xl p-5 space-y-4">
    <div><h2 className="font-bold text-lg">Kiểm tra truy hồi phụ lục</h2>
      <p className="text-sm text-slate-500 mt-1">Embedding → Qdrant → liên kết Neo4j → nội dung phụ lục. Không gọi LLM để viết lại, rerank hoặc tạo câu trả lời.</p></div>
    <form onSubmit={submit} className="space-y-3">
      <label className="block text-sm font-medium" htmlFor="retrieval-question">Câu hỏi cần truy hồi</label>
      <textarea id="retrieval-question" value={question} onChange={e => setQuestion(e.target.value)}
        required maxLength={4000} rows={3} className="w-full rounded-xl border p-3 text-sm"
        placeholder="Ví dụ: Công việc có thể gây tổn hại đến sự phát triển thể lực của người chưa thành niên" />
      <div className="flex items-center gap-3">
        <label className="text-sm">Top-k <input aria-label="Top-k" type="number" min={1} max={20} value={topK}
          onChange={e => setTopK(Number(e.target.value))} className="border rounded-lg p-2 w-20 ml-1" /></label>
        <button disabled={busy || !question.trim()} className="rounded-xl px-4 py-2 bg-secondary text-white disabled:opacity-50">
          {busy ? 'Đang truy hồi…' : 'Truy hồi dữ liệu'}</button>
      </div>
      {busy && <p className="text-sm text-slate-500" role="status">Lượt đầu có thể cần chờ model trên Modal khởi động.</p>}
    </form>
    {error && <p role="alert" className="p-3 rounded-lg bg-red-50 text-red-800">{error}</p>}
    {result && <div className="space-y-5" aria-live="polite">
      <p className="text-sm font-semibold">{result.vector_hits.length} chunk vector · {result.graph.paths.length} liên kết ontology · {result.appendices.length} phụ lục</p>
      <p className="text-xs text-slate-500 break-all">{result.embedding.model} · {result.embedding.backend} · {result.embedding.dimensions} chiều · {result.collection}</p>
      <div className="flex gap-2 flex-wrap">{Object.entries(result.timings_ms).map(([key, ms]) =>
        <span key={key} className="bg-slate-100 px-2 py-1 rounded text-xs">{key}: {(ms / 1000).toFixed(2)} s</span>)}</div>
      {result.warnings.map((warning, index) => <p key={index} className="text-sm p-3 rounded bg-amber-50 text-amber-900">{warning}</p>)}
      <section className="space-y-2"><h3 className="font-semibold">1. Kết quả vector từ Qdrant</h3>
        {result.vector_hits.length ? result.vector_hits.map(hit => <Chunk key={hit.chunk_id} hit={hit} onView={onView} />)
          : <p className="text-sm text-slate-500">Không có chunk phù hợp với bộ lọc hiệu lực.</p>}</section>
      <section><h3 className="font-semibold">2. Liên kết ontology từ Neo4j</h3>
        <p className="text-sm text-slate-500">Trạng thái: {result.graph.status}</p>
        {result.graph.paths.length ? result.graph.paths.map((path, index) => <PathView key={index} path={path} />)
          : <p className="text-sm mt-2">Không có đường liên kết được trả về.</p>}
        {result.graph.provenance.length > 0 && <details className="mt-3"><summary className="text-sm cursor-pointer">Văn bản ban hành và nguồn</summary>
          {result.graph.provenance.map((path, index) => <PathView key={index} path={path} />)}</details>}
        <details className="mt-3"><summary className="text-sm cursor-pointer">Cypher và tham số truy vấn</summary>
          <pre className="overflow-auto text-xs p-3 bg-slate-50 mt-2">{result.graph.cypher + '\n\n' + JSON.stringify(result.graph.parameters, null, 2)}</pre></details>
      </section>
      <section className="space-y-3"><h3 className="font-semibold">3. Nội dung phụ lục lấy từ Qdrant</h3>
        {!result.appendices.length && <p className="text-sm text-slate-500">Chưa tìm được phụ lục phù hợp.</p>}
        {result.appendices.map(item => <article key={item.appendix_id} className="rounded-xl border p-4 space-y-3">
          <h4 className="font-semibold">{item.title || item.appendix_id}</h4>
          <p className="text-xs text-slate-500">{item.document_number} · tìm qua: {item.retrieved_via.join(', ')}</p>
          {item.view_url && <button onClick={() => onView(item.appendix_id)} className="text-secondary underline text-sm">Xem phụ lục và tải nguồn</button>}
          {!item.eligible_for_retrieval && <p className="text-sm text-amber-800">Phụ lục chưa đủ điều kiện rà soát hoặc hiệu lực; chỉ hiển thị metadata.</p>}
          {item.kind === 'form' && <p className="text-sm text-slate-500">Biểu mẫu được tìm bằng metadata; nội dung mẫu không được embedding.</p>}
          {item.eligible_for_retrieval && item.kind !== 'form' && !item.chunks.length && <p className="text-sm text-slate-500">
            {result.appendix_fetch_status === 'unavailable' ? 'Chưa lấy được chunk từ Qdrant.' : 'Không có chunk còn hiệu lực được trả về.'}</p>}
          {item.chunks.map(hit => <Chunk key={hit.chunk_id} hit={hit} onView={onView} />)}
        </article>)}</section>
      <details><summary className="cursor-pointer text-sm">Toàn bộ kết quả JSON</summary>
        <pre className="max-h-96 overflow-auto text-xs bg-slate-50 p-3 mt-2">{JSON.stringify(result, null, 2)}</pre></details>
    </div>}
  </section>;
}
