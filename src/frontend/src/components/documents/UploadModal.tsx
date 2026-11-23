'use client';

import React, { useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { useDocumentStore } from '../../stores/documentStore';

export const UploadModal: React.FC = () => {
  const { isUploadModalOpen, setUploadModalOpen, uploadDocument, selectedDomain } = useDocumentStore();
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState('pdf');
  const [deMucId, setDeMucId] = useState('');
  const [domain, setDomain] = useState('lao_dong');
  const [pauseForReview, setPauseForReview] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isUploadModalOpen) {
      const nextDomain = selectedDomain === 'khac' ? 'khac' : 'lao_dong';
      setDomain(nextDomain);
      if (nextDomain === 'khac') setDocType('pdf');
      setError(null);
    }
  }, [isUploadModalOpen, selectedDomain]);

  if (!isUploadModalOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
    }
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
      setFile(null);
      setDeMucId('');
      setUploadModalOpen(false);
    } catch (err: any) {
      setError(errorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="w-full max-w-lg bg-surface-container-lowest rounded-2xl shadow-2xl border border-outline-variant/30 overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-[#0F172A] text-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[20px] text-secondary">post_add</span>
            <h3 className="font-headline-md text-headline-sm text-white">Nạp Văn bản Quy phạm Pháp luật</h3>
          </div>
          <button
            onClick={() => setUploadModalOpen(false)}
            className="text-slate-400 hover:text-white transition-colors"
            type="button"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          {/* Domain Selector */}
          <div className="flex flex-col gap-1.5">
            <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
              Lĩnh vực Quản lý
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label
                onClick={() => setDomain('lao_dong')}
                className={`p-3 rounded-xl border flex items-center gap-2 cursor-pointer transition-all ${
                  domain === 'lao_dong'
                    ? 'border-secondary bg-secondary-fixed/30 text-secondary'
                    : 'border-outline-variant/40 hover:bg-surface-container-low'
                }`}
              >
                <input
                  type="radio"
                  name="uploadDomain"
                  checked={domain === 'lao_dong'}
                  onChange={() => setDomain('lao_dong')}
                  className="accent-secondary"
                />
                <div className="flex flex-col text-left">
                  <span className="font-headline-sm text-xs font-semibold text-on-surface">Pháp luật Lao động</span>
                  <span className="text-[11px] text-on-surface-variant font-normal">HĐLĐ, lương, BHXH...</span>
                </div>
              </label>

              <label
                onClick={() => {
                  setDomain('khac');
                  setDocType('pdf');
                }}
                className={`p-3 rounded-xl border flex items-center gap-2 cursor-pointer transition-all ${
                  domain === 'khac'
                    ? 'border-secondary bg-secondary-fixed/30 text-secondary'
                    : 'border-outline-variant/40 hover:bg-surface-container-low'
                }`}
              >
                <input
                  type="radio"
                  name="uploadDomain"
                  checked={domain === 'khac'}
                  onChange={() => {
                    setDomain('khac');
                    setDocType('pdf');
                  }}
                  className="accent-secondary"
                />
                <div className="flex flex-col text-left">
                  <span className="font-headline-sm text-xs font-semibold text-on-surface">Lĩnh vực khác</span>
                  <span className="text-[11px] text-on-surface-variant font-normal">Giáo dục, Dân sự, Luật khác</span>
                </div>
              </label>
            </div>
          </div>

          {docType === 'phap_dien_html' && <label className="text-sm">Mã đề mục (nếu file chưa có tiêu đề nhận diện)
            <input value={deMucId} onChange={e => setDeMucId(e.target.value)} placeholder="Ví dụ: 20.2"
              className="block w-full border rounded-lg p-2 mt-1" /></label>}
          {/* File Type Selector */}
          <div className="flex flex-col gap-1.5">
            <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
              Định dạng Tài liệu
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label
                onClick={() => setDocType('pdf')}
                className={`p-3 rounded-xl border flex items-center gap-2 cursor-pointer transition-all ${
                  docType === 'pdf'
                    ? 'border-secondary bg-secondary-fixed/30 text-secondary'
                    : 'border-outline-variant/40 hover:bg-surface-container-low'
                }`}
              >
                <input
                  type="radio"
                  name="docType"
                  checked={docType === 'pdf'}
                  onChange={() => setDocType('pdf')}
                  className="accent-secondary"
                />
                <div className="flex flex-col text-left">
                  <span className="font-headline-sm text-xs font-semibold text-on-surface">Văn bản PDF / OCR</span>
                  <span className="text-[11px] text-on-surface-variant font-normal">Luật, Nghị định, Thông tư</span>
                </div>
              </label>

              <label
                onClick={() => {
                  if (domain !== 'khac') setDocType('phap_dien_html');
                }}
                title={domain === 'khac' ? 'Bộ Pháp điển chỉ hỗ trợ lĩnh vực Lao động' : undefined}
                className={`p-3 rounded-xl border flex items-center gap-2 transition-all ${
                  domain === 'khac'
                    ? 'border-outline-variant/20 bg-surface-container/50 opacity-50 cursor-not-allowed'
                    : docType === 'phap_dien_html'
                    ? 'border-secondary bg-secondary-fixed/30 text-secondary cursor-pointer'
                    : 'border-outline-variant/40 hover:bg-surface-container-low cursor-pointer'
                }`}
              >
                <input
                  type="radio"
                  name="docType"
                  disabled={domain === 'khac'}
                  checked={docType === 'phap_dien_html'}
                  onChange={() => setDocType('phap_dien_html')}
                  className="accent-secondary"
                />
                <div className="flex flex-col text-left">
                  <span className="font-headline-sm text-xs font-semibold text-on-surface">Pháp điển (HTML)</span>
                  <span className="text-[11px] text-on-surface-variant font-normal">
                    {domain === 'khac' ? 'Chỉ hỗ trợ Lao động' : 'Đề mục Bộ Pháp điển'}
                  </span>
                </div>
              </label>
            </div>
          </div>

          {/* Drag & Drop File Zone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="border-2 border-dashed border-outline-variant hover:border-secondary rounded-2xl p-6 flex flex-col items-center justify-center gap-2 bg-surface-container-low/50 hover:bg-surface-container-low transition-all cursor-pointer relative"
          >
            <input
              type="file"
              accept={docType === 'pdf' ? '.pdf' : '.html,.htm'}
              onChange={handleFileChange}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
            <div className="w-12 h-12 rounded-full bg-secondary-fixed flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined text-[28px]">upload_file</span>
            </div>
            <div className="text-center">
              <p className="font-headline-sm text-headline-sm text-on-surface">
                {file ? file.name : 'Kéo thả tài liệu vào đây hoặc nhấp để duyệt'}
              </p>
              <p className="text-xs text-on-surface-variant font-body-sm mt-0.5">
                Hỗ trợ định dạng PDF, HTML Bộ Pháp điển, hoặc tài liệu số hóa (Tối đa 50MB)
              </p>
            </div>
          </div>

          {docType === 'pdf' && (
            <label className="flex items-start gap-2.5 p-3 rounded-xl border border-outline-variant/30 bg-surface-container-low/60 cursor-pointer">
              <input
                type="checkbox"
                checked={pauseForReview}
                onChange={(e) => setPauseForReview(e.target.checked)}
                className="mt-0.5 accent-secondary"
              />
              <div className="flex flex-col text-left">
                <span className="font-headline-sm text-xs font-semibold text-on-surface">
                  Tạm dừng để đối chiếu PDF & chỉnh sửa nội dung OCR
                </span>
                <span className="text-[11px] text-on-surface-variant font-normal">
                  Kiểm tra từng trang PDF song song với chữ OCR và sửa chính tả trước khi lập chỉ mục
                </span>
              </div>
            </label>
          )}

          {error && <div className="p-2.5 rounded-lg bg-red-50 text-red-700 text-xs font-mono">{error}</div>}

          {/* Modal Footer */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-outline-variant/30">
            <button
              type="button"
              onClick={() => setUploadModalOpen(false)}
              className="px-4 py-2 rounded-xl text-on-surface-variant hover:bg-surface-container transition-colors font-body-sm"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !file}
              className="px-5 py-2 rounded-xl bg-secondary text-white font-headline-sm text-body-sm shadow-sm hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                  <span>Đang tải lên...</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                  <span>Bắt đầu Lập chỉ mục kép</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

