'use client';

import React, { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { useDocumentStore } from '../../stores/documentStore';

type Domain = 'lao_dong' | 'khac';
type DocType = 'pdf' | 'phap_dien_html';

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function Choice({ checked, disabled, title, label, hint, onSelect, name }: {
  checked: boolean; disabled?: boolean; title?: string; label: string; hint: string; name: string; onSelect: () => void;
}) {
  return (
    <label title={title}
      className={`p-3 rounded-xl border flex items-center gap-2 transition-all ${
        disabled ? 'border-outline-variant/20 bg-surface-container/50 opacity-50 cursor-not-allowed'
          : checked ? 'border-secondary bg-secondary-fixed/30 text-secondary cursor-pointer'
          : 'border-outline-variant/40 hover:bg-surface-container-low cursor-pointer'
      }`}>
      <input type="radio" name={name} checked={checked} disabled={disabled} onChange={onSelect} className="accent-secondary" />
      <div className="flex flex-col text-left">
        <span className="text-xs font-semibold text-ink">{label}</span>
        <span className="text-[11.5px] text-ink-3 font-normal">{hint}</span>
      </div>
    </label>
  );
}

/** Upload form for a new legal document, shown as a dialog over the "Nạp PDF" tab. */
export const UploadModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { uploadDocument, selectedDomain } = useDocumentStore();
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<Domain>(selectedDomain === 'khac' ? 'khac' : 'lao_dong');
  const [docType, setDocType] = useState<DocType>('pdf');
  const [deMucId, setDeMucId] = useState('');
  const [pauseForReview, setPauseForReview] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !isSubmitting) onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isSubmitting, onClose]);

  const chooseDomain = (next: Domain) => {
    setDomain(next);
    if (next === 'khac') setDocType('pdf');
  };

  const chooseType = (next: DocType) => {
    setDocType(next);
    // The accepted extension changes with the type; drop a file of the other kind.
    if (file && !file.name.toLowerCase().match(next === 'pdf' ? /\.pdf$/ : /\.html?$/)) setFile(null);
  };

  const pick = (picked?: File | null) => {
    if (!picked) return;
    setFile(picked);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Vui lòng chọn tài liệu cần nạp.');
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      if (docType === 'phap_dien_html') {
        const response = await api.uploadDocument(file, docType, domain, deMucId || undefined, false);
        useDocumentStore.getState().pollTaskProgress(response.task_id);
      } else {
        await uploadDocument(file, docType, domain, pauseForReview);
      }
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setIsSubmitting(false);
    }
  };

  const submitLabel = docType === 'pdf' && pauseForReview ? 'Tải lên & đọc OCR' : 'Tải lên & lập chỉ mục';

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="upload-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-[2px] p-4"
      onClick={() => { if (!isSubmitting) onClose(); }}>
      <div className="w-full max-w-2xl max-h-[calc(100vh-2rem)] bg-surface-container-lowest rounded-2xl shadow-2xl border border-ink/10 overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3.5 bg-[#0F172A] text-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-secondary">post_add</span>
            <h2 id="upload-title" className="text-[14px] font-semibold text-white">Nạp Văn bản Quy phạm Pháp luật</h2>
          </div>
          <button type="button" onClick={onClose} disabled={isSubmitting} aria-label="Đóng"
            className="w-7 h-7 rounded-lg flex items-center justify-center text-white/70 hover:text-white hover:bg-white/10 disabled:opacity-40">
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col min-h-0">
          <div className="p-5 flex flex-col gap-4 overflow-y-auto">
            <fieldset className="flex flex-col gap-1.5" disabled={isSubmitting}>
              <legend className="text-[12px] text-ink-3 font-semibold mb-1.5">Lĩnh vực Quản lý</legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Choice name="uploadDomain" checked={domain === 'lao_dong'} onSelect={() => chooseDomain('lao_dong')}
                  label="Pháp luật Lao động" hint="HĐLĐ, lương, BHXH..." />
                <Choice name="uploadDomain" checked={domain === 'khac'} onSelect={() => chooseDomain('khac')}
                  label="Lĩnh vực khác" hint="Giáo dục, Dân sự, Luật khác" />
              </div>
            </fieldset>

            <fieldset className="flex flex-col gap-1.5" disabled={isSubmitting}>
              <legend className="text-[12px] text-ink-3 font-semibold mb-1.5">Định dạng Tài liệu</legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Choice name="docType" checked={docType === 'pdf'} onSelect={() => chooseType('pdf')}
                  label="Văn bản PDF / OCR" hint="Luật, Nghị định, Thông tư" />
                <Choice name="docType" checked={docType === 'phap_dien_html'} disabled={domain === 'khac'}
                  title={domain === 'khac' ? 'Bộ Pháp điển chỉ hỗ trợ lĩnh vực Lao động' : undefined}
                  onSelect={() => chooseType('phap_dien_html')}
                  label="Pháp điển (HTML)" hint={domain === 'khac' ? 'Chỉ hỗ trợ Lao động' : 'Đề mục Bộ Pháp điển'} />
              </div>
              {docType === 'phap_dien_html' && (
                <label className="flex flex-col gap-1 text-[12px] text-ink-3 font-semibold mt-1">
                  Mã đề mục <span className="font-normal">(chỉ cần khi file chưa có tiêu đề nhận diện)</span>
                  <input value={deMucId} onChange={(e) => setDeMucId(e.target.value)} placeholder="Ví dụ: 20.2"
                    className="px-3 py-2 rounded-lg border border-outline-variant/40 bg-white text-[13px] text-ink font-normal focus:outline-none focus:border-secondary" />
                </label>
              )}
            </fieldset>

            {file ? (
              <div className="flex items-center gap-3 p-3 rounded-xl border border-secondary/40 bg-secondary-fixed/20">
                <div className="w-10 h-10 rounded-lg bg-secondary-fixed flex items-center justify-center text-secondary shrink-0">
                  <span className="material-symbols-outlined text-[22px]">{docType === 'pdf' ? 'picture_as_pdf' : 'html'}</span>
                </div>
                <div className="flex flex-col min-w-0 flex-1">
                  <span className="text-[13px] font-semibold text-ink truncate" title={file.name}>{file.name}</span>
                  <span className="text-[11.5px] text-ink-3">{formatSize(file.size)}</span>
                </div>
                <button type="button" onClick={() => inputRef.current?.click()} disabled={isSubmitting}
                  className="px-2.5 py-1 rounded-lg text-[12px] text-secondary hover:bg-secondary/10 disabled:opacity-40">Đổi file</button>
                <button type="button" onClick={() => setFile(null)} disabled={isSubmitting} aria-label="Bỏ chọn file"
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-ink-3 hover:bg-surface-container disabled:opacity-40">
                  <span className="material-symbols-outlined text-[18px]">close</span>
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]); }}
                className={`border-2 border-dashed rounded-2xl p-6 flex flex-col items-center justify-center gap-2 transition-all ${
                  dragging ? 'border-secondary bg-secondary-fixed/30' : 'border-outline-variant hover:border-secondary bg-surface-container-low/50 hover:bg-surface-container-low'
                }`}>
                <div className="w-12 h-12 rounded-full bg-secondary-fixed flex items-center justify-center text-secondary">
                  <span className="material-symbols-outlined text-[28px]">upload_file</span>
                </div>
                <span className="text-[14px] font-semibold text-ink">Kéo thả tài liệu vào đây hoặc nhấp để duyệt</span>
                <span className="text-xs text-ink-3">
                  {docType === 'pdf' ? 'File PDF văn bản hoặc bản scan' : 'File HTML đề mục Bộ Pháp điển'} (tối đa 50MB)
                </span>
              </button>
            )}
            <input ref={inputRef} type="file" hidden accept={docType === 'pdf' ? '.pdf' : '.html,.htm'}
              onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ''; }} />

            {docType === 'pdf' && (
              <label className="flex items-start gap-2.5 p-3 rounded-xl border border-outline-variant/30 bg-surface-container-low/60 cursor-pointer">
                <input type="checkbox" checked={pauseForReview} disabled={isSubmitting}
                  onChange={(e) => setPauseForReview(e.target.checked)} className="mt-0.5 accent-secondary" />
                <div className="flex flex-col text-left">
                  <span className="text-xs font-semibold text-ink">Tạm dừng để đối chiếu PDF & chỉnh sửa nội dung OCR</span>
                  <span className="text-[11.5px] text-ink-3 font-normal">
                    Kiểm tra từng trang PDF song song với chữ OCR và sửa chính tả trước khi lập chỉ mục
                  </span>
                </div>
              </label>
            )}

            {error && <p role="alert" className="p-2.5 rounded-lg bg-error-container text-on-error-container text-xs">{error}</p>}
          </div>

          <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-outline-variant/30 bg-surface-container-low">
            <button type="button" onClick={onClose} disabled={isSubmitting}
              className="px-4 py-2 rounded-xl text-[13px] bg-surface-container text-ink hover:bg-surface-container-high disabled:opacity-50">Hủy</button>
            <button type="submit" disabled={isSubmitting || !file}
              className="px-5 py-2 rounded-xl bg-secondary text-white text-[13px] font-medium shadow-sm hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-2">
              {isSubmitting ? (
                <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /><span>Đang tải lên...</span></>
              ) : (
                <><span className="material-symbols-outlined text-[18px]">play_arrow</span><span>{submitLabel}</span></>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
