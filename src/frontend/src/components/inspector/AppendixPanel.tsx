'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Download, FileText, FileType, Maximize2, X } from 'lucide-react';
import { api, appendixDocxUrl, appendixViewUrl, errorMessage } from '../../lib/api';
import type { AppendixItem, ChatMessage } from '../../lib/types';
import { useChatStore } from '../../stores/chatStore';

interface AppendixRef {
  id: string;
  label: string;
  chunkId?: string;
}

/**
 * The chunk to highlight in the preview, only when it is a piece of that appendix
 * ("<appendix_id>" or "<appendix_id>:p3"). An article that merely links to an appendix
 * keeps its own chunk id, which the preview endpoint rejects with 404.
 */
export function appendixChunk(appendixId: string, chunkId?: string): string | undefined {
  return chunkId && (chunkId === appendixId || chunkId.startsWith(appendixId + ':')) ? chunkId : undefined;
}

/** Appendices attached to or cited by the latest answer, without duplicates. */
export function answerAppendices(messages: ChatMessage[]): AppendixRef[] {
  const last = [...messages].reverse().find((message) => message.role === 'assistant');
  if (!last) return [];
  const refs = new Map<string, AppendixRef>();
  for (const item of last.attachments ?? []) {
    refs.set(item.appendix_id, { id: item.appendix_id, label: `Phụ lục ${item.number} · ${item.document_number}` });
  }
  for (const evidence of last.legal_evidence ?? []) {
    if (!evidence.appendix_id) continue;
    const known = refs.get(evidence.appendix_id);
    refs.set(evidence.appendix_id, {
      id: evidence.appendix_id,
      label: known?.label ?? evidence.citation,
      chunkId: known?.chunkId ?? appendixChunk(evidence.appendix_id, evidence.chunk_id),
    });
  }
  return Array.from(refs.values());
}

const kindLabel: Record<string, string> = { form: 'Biểu mẫu', reference: 'Tra cứu', mixed: 'Hỗn hợp' };

/** Preview of one appendix with its forms and download links; also used inside the expanded dialog. */
export function AppendixPreview({ id, chunkId, onExpand, onClose }: {
  id: string;
  chunkId?: string;
  onExpand?: () => void;
  onClose?: () => void;
}) {
  const [item, setItem] = useState<AppendixItem | null>(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState<string | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    setItem(null); setError(''); setForm(undefined);
    api.getAppendix(id).then((value) => { if (alive) setItem(value); })
      .catch((e) => { if (alive) setError(errorMessage(e)); });
    return () => { alive = false; };
  }, [id]);

  const forms = item?.form_sections ?? [];
  const selectedForm = forms.find((f) => f.code === form);
  const sourceFiles = (item?.files ?? []).filter((file) => file.available !== false && file.format !== 'html');
  const htmlDownload = appendixViewUrl(id, { form }) + (form ? '&' : '?') + 'download=true';

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="px-3.5 pt-3 pb-2.5 border-b border-ink/6 space-y-2 shrink-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11.5px] text-muted">
              <span>{item ? `Phụ lục ${item.number} · ${item.document_number}` : 'Phụ lục'}</span>
              {item?.kind && kindLabel[item.kind] && (
                <span className="px-1.5 py-0.5 rounded-md bg-navy/8 text-navy font-medium">{kindLabel[item.kind]}</span>
              )}
            </div>
            <h3 className="mt-0.5 text-[13.5px] font-semibold text-ink leading-snug line-clamp-2">
              {selectedForm ? `Mẫu số ${selectedForm.code}${selectedForm.title ? ' – ' + selectedForm.title : ''}` : item?.title ?? 'Đang tải…'}
            </h3>
          </div>
          <div className="flex items-center gap-0.5 shrink-0">
            {onExpand && (
              <button type="button" onClick={onExpand} title="Mở rộng bản xem trước" className="p-1.5 rounded-lg text-ink-3 hover:text-ink hover:bg-stone">
                <Maximize2 className="w-4 h-4" />
              </button>
            )}
            {onClose && (
              <button type="button" onClick={onClose} aria-label="Đóng bản xem trước" className="p-1.5 rounded-lg text-ink-3 hover:text-ink hover:bg-stone">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {forms.length > 1 && (
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Chọn biểu mẫu">
            <button
              type="button"
              aria-pressed={!form}
              onClick={() => setForm(undefined)}
              className={`px-2 py-1 rounded-lg text-[11.5px] border transition-colors ${!form ? 'bg-navy text-white border-navy' : 'bg-white border-ink/10 text-ink-2 hover:border-navy/35'}`}
            >
              Cả phụ lục
            </button>
            {forms.map((f) => (
              <button
                key={f.code}
                type="button"
                aria-pressed={form === f.code}
                title={f.title || undefined}
                onClick={() => setForm(f.code)}
                className={`px-2 py-1 rounded-lg text-[11.5px] border transition-colors ${form === f.code ? 'bg-navy text-white border-navy' : 'bg-white border-ink/10 text-ink-2 hover:border-navy/35'}`}
              >
                Mẫu {f.code}
              </button>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <a
            href={appendixDocxUrl(id, form)}
            download
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-navy text-white text-[12.5px] font-medium hover:bg-navy-dark transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            {form ? 'Tải biểu mẫu (.docx)' : 'Tải phụ lục (.docx)'}
          </a>
          <a href={htmlDownload} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-ink/10 text-[12px] text-ink-2 hover:bg-stone transition-colors">
            <FileText className="w-3.5 h-3.5" />
            Bản HTML
          </a>
        </div>
      </div>

      <div className="flex-1 min-h-0 bg-paper">
        {error ? (
          <p role="alert" className="m-3 rounded-xl border border-[#9A6B2F]/25 bg-[#FAF7F0] px-3 py-2 text-[12.5px] text-[#473822]">{error}</p>
        ) : (
          <iframe
            key={id + (form ?? '')}
            title="Xem trước phụ lục"
            src={appendixViewUrl(id, { form, chunkId: appendixChunk(id, chunkId) })}
            sandbox="allow-scripts"
            className="w-full h-full border-0 bg-white"
          />
        )}
      </div>

      {sourceFiles.length > 0 && (
        <div className="px-3.5 py-2.5 border-t border-ink/6 text-[11.5px] text-ink-3 shrink-0">
          <span>Văn bản gốc của cả {item?.document_number} (gồm nhiều phụ lục): </span>
          {sourceFiles.map((file) => (
            <a key={file.artifact_id} href={file.download_url} className="inline-flex items-center gap-1 ml-2 font-medium text-navy hover:underline">
              <FileType className="w-3 h-3" />{file.format.toUpperCase()}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export function AppendixPanel() {
  const { messages, selectedAppendix, openAppendix } = useChatStore();
  const refs = useMemo(() => answerAppendices(messages), [messages]);
  const [expanded, setExpanded] = useState(false);
  const current = selectedAppendix ?? (refs[0] ? { id: refs[0].id, chunkId: refs[0].chunkId } : null);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setExpanded(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [expanded]);

  if (!current) {
    return <div className="flex-1 py-12 px-6 text-center text-[13px] text-muted">Câu trả lời này không kèm phụ lục.</div>;
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {refs.length > 1 && (
        <div className="px-3 pt-2.5 flex gap-1.5 overflow-x-auto legal-scroll shrink-0">
          {refs.map((ref) => (
            <button
              key={ref.id}
              type="button"
              onClick={() => openAppendix(ref.id, ref.chunkId)}
              className={`px-2.5 py-1 rounded-lg text-[11.5px] whitespace-nowrap border transition-colors ${
                current.id === ref.id ? 'bg-stone-2 border-ink/10 text-ink font-medium' : 'border-transparent text-ink-3 hover:bg-stone'
              }`}
            >
              {ref.label}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 min-h-0">
        <AppendixPreview id={current.id} chunkId={current.chunkId} onExpand={() => setExpanded(true)} />
      </div>
      {expanded && (
        <div
          className="fixed inset-0 z-[55] flex items-center justify-center bg-ink/35 backdrop-blur-[2px] p-3 sm:p-6"
          onMouseDown={(e) => { if (e.target === e.currentTarget) setExpanded(false); }}
        >
          <div role="dialog" aria-modal="true" aria-label="Xem trước phụ lục" className="w-full max-w-[1000px] h-[min(860px,100%)] bg-white rounded-2xl border border-ink/10 shadow-2xl overflow-hidden">
            <AppendixPreview id={current.id} chunkId={current.chunkId} onClose={() => setExpanded(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
