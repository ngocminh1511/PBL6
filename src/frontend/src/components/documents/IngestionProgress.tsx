'use client';

import React, { useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { IngestionTask } from '../../lib/types';
import { useDocumentStore } from '../../stores/documentStore';

interface IngestionProgressProps {
  task: IngestionTask;
  onOpenDocument?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Đang chờ xử lý',
  parsing: 'Đang đọc & OCR',
  awaiting_review: 'Chờ kiểm tra OCR',
  chunking: 'Tách cấu trúc',
  embedding: 'Đang lập chỉ mục',
  indexing: 'Đồng bộ dữ liệu',
  completed: 'Hoàn tất',
  failed: 'Thất bại',
  cancelled: 'Đã hủy',
};

const STAGES = [
  { key: 'ocr', label: '1. Đọc & OCR', statuses: ['pending', 'parsing'] },
  { key: 'structure', label: '2. Tách cấu trúc', statuses: ['chunking'] },
  { key: 'index', label: '3. Lập chỉ mục', statuses: ['embedding', 'indexing'] },
  { key: 'done', label: '4. Hoàn tất', statuses: ['completed'] },
];

function stageIndex(status: string): number {
  const idx = STAGES.findIndex((s) => s.statuses.includes(status));
  return idx === -1 ? 0 : idx;
}

export const IngestionProgress: React.FC<IngestionProgressProps> = ({ task, onOpenDocument }) => {
  const cancelTask = useDocumentStore((s) => s.cancelTask);
  const confirmTaskReview = useDocumentStore((s) => s.confirmTaskReview);
  const [cancelling, setCancelling] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [previewExpanded, setPreviewExpanded] = useState(true);
  const [targetPage, setTargetPage] = useState<number | null>(null);
  const [pageInput, setPageInput] = useState('1');
  const [fullPageTexts, setFullPageTexts] = useState<Record<number, string>>({});
  const [pageMethods, setPageMethods] = useState<Record<number, string>>({});
  const [editedPages, setEditedPages] = useState<Record<number, boolean>>({});
  const [loadingPage, setLoadingPage] = useState<number | null>(null);
  const [pageLoadError, setPageLoadError] = useState<string | null>(null);
  const [pdfImgError, setPdfImgError] = useState(false);

  const [isEditing, setIsEditing] = useState(false);
  const [draftText, setDraftText] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  const isCompleted = task.status === 'completed';
  const isFailed = task.status === 'failed';
  const isCancelled = task.status === 'cancelled';
  const isAwaitingReview = task.status === 'awaiting_review';
  const isRunning = !isCompleted && !isFailed && !isCancelled && !isAwaitingReview;
  const canCancel = isRunning || isAwaitingReview;
  const currentStage = isCompleted ? 3 : isAwaitingReview ? 1 : stageIndex(task.status);
  const statusText = STATUS_LABELS[task.status] || task.status;

  const ocrPreview = task.ocr_preview;
  const recentPages = ocrPreview?.recent_pages ?? [];
  const latestProcessedPage =
    ocrPreview?.processed_pages || recentPages[recentPages.length - 1]?.page_number || 1;
  const totalPages = ocrPreview?.total_pages || latestProcessedPage || 1;
  const viewPage = Math.max(1, Math.min(targetPage ?? latestProcessedPage, Math.max(totalPages, 1)));

  useEffect(() => {
    if (!canCancel) {
      setCancelling(false);
    }
    if (!isAwaitingReview) {
      setConfirming(false);
      setIsEditing(false);
    }
  }, [canCancel, isAwaitingReview]);

  useEffect(() => {
    setTargetPage(null);
    setPageInput('1');
    setFullPageTexts({});
    setPageMethods({});
    setEditedPages({});
    setLoadingPage(null);
    setPageLoadError(null);
    setPdfImgError(false);
    setIsEditing(false);
    setDraftText('');
    setSaveNotice(null);
    setPreviewExpanded(true);
  }, [task.id]);

  useEffect(() => {
    setPageInput(String(viewPage));
    setPdfImgError(false);
    setSaveNotice(null);
  }, [viewPage]);

  useEffect(() => {
    if (task.document_type !== 'pdf' || !ocrPreview) return;
    if (viewPage > ocrPreview.processed_pages) return;
    if (fullPageTexts[viewPage] !== undefined) return;

    let cancelled = false;
    setLoadingPage(viewPage);
    setPageLoadError(null);
    void api
      .getTaskOCRPage(task.id, viewPage)
      .then((detail) => {
        if (cancelled) return;
        setFullPageTexts((prev) => ({ ...prev, [viewPage]: detail.text }));
        setPageMethods((prev) => ({ ...prev, [viewPage]: detail.method }));
      })
      .catch((e) => {
        if (cancelled) return;
        setPageLoadError(errorMessage(e));
      })
      .finally(() => {
        if (!cancelled) setLoadingPage(null);
      });
    return () => {
      cancelled = true;
    };
  }, [task.id, task.document_type, viewPage, ocrPreview?.processed_pages, fullPageTexts]);

  const recentMatch = recentPages.find((p) => p.page_number === viewPage);
  const isPageExtracted = viewPage <= (ocrPreview?.processed_pages ?? 0);
  const currentPageText =
    fullPageTexts[viewPage] ?? recentMatch?.preview_text ?? '';
  const currentPageMethod = pageMethods[viewPage] ?? recentMatch?.method ?? '';
  const methodLabel =
    currentPageMethod === 'ocr'
      ? 'OCR'
      : currentPageMethod === 'text'
      ? 'Text layer'
      : currentPageMethod === 'empty'
      ? 'Trang trống'
      : currentPageMethod;

  const goToPage = (nextPage: number) => {
    if (isEditing) {
      setPageLoadError('Vui lòng lưu hoặc hủy chỉnh sửa trang hiện tại trước khi chuyển trang.');
      return;
    }
    const clamped = Math.max(1, Math.min(nextPage, Math.max(totalPages, 1)));
    setPageLoadError(null);
    setTargetPage(clamped);
    setPageInput(String(clamped));
  };

  const handleJumpToPage = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseInt(pageInput.trim(), 10);
    if (Number.isNaN(parsed)) {
      setPageInput(String(viewPage));
      return;
    }
    goToPage(parsed);
  };

  const handleStartEdit = () => {
    if (!isAwaitingReview || !isPageExtracted) return;
    setDraftText(currentPageText);
    setPageLoadError(null);
    setSaveNotice(null);
    setIsEditing(true);
  };

  const handleSaveEdit = async () => {
    if (savingEdit) return;
    setSavingEdit(true);
    setPageLoadError(null);
    setSaveNotice(null);
    try {
      const updated = await api.updateTaskOCRPage(task.id, viewPage, draftText);
      setFullPageTexts((prev) => ({ ...prev, [viewPage]: updated.text }));
      setEditedPages((prev) => ({ ...prev, [viewPage]: true }));
      setIsEditing(false);
      setSaveNotice(`Đã lưu chỉnh sửa trang ${viewPage}.`);
    } catch (e) {
      setPageLoadError(errorMessage(e));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleConfirm = async () => {
    if (!isAwaitingReview || confirming || isEditing) return;
    setConfirming(true);
    setPageLoadError(null);
    try {
      await confirmTaskReview(task.id);
    } catch (e) {
      setPageLoadError(errorMessage(e));
      setConfirming(false);
    }
  };

  const handleCancel = async () => {
    if (!canCancel || cancelling) return;
    setCancelling(true);
    try {
      await cancelTask(task.id);
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="w-full bg-surface-container-lowest rounded-xl p-space-md shadow-sm border border-secondary/30 flex flex-col gap-3 animate-fadeIn">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-secondary/10 flex items-center justify-center text-secondary">
            <span className={`material-symbols-outlined text-[20px] ${isRunning ? 'animate-spin' : ''}`}>
              {isCompleted
                ? 'check_circle'
                : isFailed
                ? 'error'
                : isCancelled
                ? 'cancel'
                : isAwaitingReview
                ? 'fact_check'
                : 'sync'}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="font-headline-sm text-headline-sm text-on-surface">
              Tiến trình Nạp tài liệu: {task.file_name}
            </span>
            <span className="font-label-code text-[11px] text-on-surface-variant">
              Định dạng: {task.document_type === 'pdf' ? 'Văn bản PDF (OCR)' : 'Pháp điển HTML'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`font-label-statute text-label-statute px-2.5 py-1 rounded font-bold ${
              isCompleted
                ? 'bg-tertiary-fixed text-on-tertiary-fixed'
                : isFailed
                ? 'bg-error-container text-on-error-container'
                : isCancelled
                ? 'bg-amber-100 text-amber-900'
                : isAwaitingReview
                ? 'bg-indigo-100 text-indigo-900'
                : 'bg-secondary-fixed text-on-secondary-fixed'
            }`}
          >
            {statusText} ({Math.round(task.progress)}%)
          </span>
          {isAwaitingReview && (
            <button
              type="button"
              onClick={handleConfirm}
              disabled={confirming || isEditing}
              title={isEditing ? 'Hãy lưu hoặc hủy chỉnh sửa trước khi xác nhận lập chỉ mục' : undefined}
              className="px-3 py-1 rounded bg-secondary hover:opacity-90 text-white text-[12px] font-label-statute font-semibold flex items-center gap-1 transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer shadow-sm"
            >
              <span className="material-symbols-outlined text-[15px]">check_circle</span>
              <span>{confirming ? 'Đang bắt đầu...' : 'Xác nhận & Lập chỉ mục'}</span>
            </button>
          )}
          {isCompleted && onOpenDocument && (
            <button
              type="button"
              onClick={onOpenDocument}
              className="px-3 py-1 rounded bg-secondary hover:opacity-90 text-white text-[12px] font-label-statute font-semibold flex items-center gap-1 shadow-sm"
            >
              <span className="material-symbols-outlined text-[15px]">folder_open</span>
              <span>Xem văn bản trong kho</span>
            </button>
          )}
          {canCancel && (
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling || confirming}
              className="px-2.5 py-1 rounded border border-red-300 bg-red-50 hover:bg-red-100 text-red-700 text-[12px] font-label-statute font-semibold flex items-center gap-1 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
            >
              <span className="material-symbols-outlined text-[15px]">stop_circle</span>
              <span>{cancelling ? 'Đang hủy...' : 'Hủy xử lý'}</span>
            </button>
          )}
        </div>
      </div>

      {/* 4-Stage Step Indicator */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {STAGES.map((stage, idx) => {
          const isDone = isCompleted || (!isFailed && !isCancelled && idx < currentStage);
          const isActive = isRunning && idx === currentStage;
          return (
            <div
              key={stage.key}
              className={`px-2.5 py-1.5 rounded-lg border text-[11px] font-label-statute flex items-center gap-1.5 transition-all ${
                isDone
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : isActive
                  ? 'bg-secondary-fixed/50 border-secondary/50 text-secondary font-bold'
                  : 'bg-surface-container-low border-outline-variant/20 text-on-surface-variant'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]">
                {isDone ? 'check_circle' : isActive ? 'pending' : 'radio_button_unchecked'}
              </span>
              <span className="truncate">{stage.label}</span>
            </div>
          );
        })}
      </div>

      {/* Progress Bar Container */}
      <div className="w-full h-3 rounded-full bg-surface-container-high overflow-hidden relative">
        <div
          className={`h-full transition-all duration-500 rounded-full ${
            isCompleted
              ? 'bg-emerald-600'
              : isFailed
              ? 'bg-red-600'
              : isCancelled
              ? 'bg-amber-500'
              : isAwaitingReview
              ? 'bg-indigo-600'
              : 'bg-gradient-to-r from-secondary to-indigo-500 animate-pulse'
          }`}
          style={{ width: `${Math.max(task.progress, 0)}%` }}
        ></div>
      </div>

      {/* Current Step Highlight */}
      <div className="bg-surface-container-low rounded-lg px-3 py-2 flex items-center gap-2 font-body-sm text-[12px] border border-outline-variant/20">
        <span
          className={`material-symbols-outlined text-[16px] shrink-0 ${
            isFailed
              ? 'text-red-600'
              : isCompleted
              ? 'text-emerald-600'
              : isCancelled
              ? 'text-amber-600'
              : isAwaitingReview
              ? 'text-indigo-600'
              : 'text-secondary animate-spin'
          }`}
        >
          {isFailed ? 'error' : isCompleted ? 'task_alt' : isCancelled ? 'cancel' : isAwaitingReview ? 'edit_document' : 'autorenew'}
        </span>
        <span className="font-semibold text-on-surface-variant shrink-0">Công việc hiện tại:</span>
        <span className="font-medium text-on-surface">{task.current_step}</span>
      </div>

      {/* Realtime Split PDF vs Extracted OCR View */}
      {task.document_type === 'pdf' && ocrPreview && (
        <div className="flex flex-col gap-2.5 border-t border-outline-variant/20 pt-2.5">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-label-statute">
            <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/25 text-on-surface">
              Trang đã xử lý: <strong>{ocrPreview.processed_pages}/{ocrPreview.total_pages || '?'}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/25 text-on-surface-variant">
              Text: <strong className="text-on-surface">{ocrPreview.text_pages}</strong> · OCR scan:{' '}
              <strong className="text-on-surface">{ocrPreview.ocr_pages}</strong>
              {ocrPreview.empty_pages > 0 && (
                <>
                  {' '}
                  · Trống: <strong>{ocrPreview.empty_pages}</strong>
                </>
              )}
            </span>
            {ocrPreview.heuristic_score !== undefined && ocrPreview.heuristic_score !== null && (
              <span className="px-2.5 py-1 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-800 font-semibold">
                Chất lượng văn bản: {Math.round(ocrPreview.heuristic_score)}/100
              </span>
            )}
            {ocrPreview.articles_count !== undefined && ocrPreview.articles_count !== null && (
              <span className="px-2.5 py-1 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800 font-semibold">
                Điều bóc tách: {ocrPreview.articles_count} Điều
              </span>
            )}
          </div>

          <div className="rounded-lg border border-outline-variant/25 bg-surface-container-low/70 overflow-hidden">
            <div className="px-3 py-2 flex items-center justify-between gap-2 flex-wrap bg-surface-container-low border-b border-outline-variant/20">
              <div className="flex items-center gap-2 text-[12px] font-semibold text-on-surface">
                <span className="material-symbols-outlined text-[16px] text-secondary">chrome_reader_mode</span>
                <span>Đối chiếu trang PDF & nội dung trích xuất</span>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <form onSubmit={handleJumpToPage} className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => goToPage(viewPage - 1)}
                    disabled={viewPage <= 1 || isEditing}
                    className="w-6 h-6 rounded border border-outline-variant/35 bg-surface-container-lowest hover:bg-surface-container text-on-surface flex items-center justify-center disabled:opacity-40 cursor-pointer"
                    title="Trang trước"
                  >
                    <span className="material-symbols-outlined text-[15px]">chevron_left</span>
                  </button>
                  <span className="text-[11px] text-on-surface-variant ml-0.5">Trang</span>
                  <input
                    type="number"
                    min={1}
                    max={totalPages || undefined}
                    value={pageInput}
                    onChange={(e) => setPageInput(e.target.value)}
                    disabled={isEditing}
                    aria-label="Số thứ tự trang"
                    className="w-14 px-1.5 py-0.5 text-center rounded border border-outline-variant/40 bg-surface-container-lowest text-[12px] font-label-code text-on-surface focus:outline-none focus:border-secondary disabled:opacity-60"
                  />
                  <span className="text-[11px] text-on-surface-variant">/ {totalPages || '?'}</span>
                  <button
                    type="submit"
                    disabled={isEditing}
                    className="px-2 py-0.5 rounded bg-secondary/10 hover:bg-secondary/20 text-secondary border border-secondary/30 text-[11px] font-semibold disabled:opacity-50 cursor-pointer"
                  >
                    Đi tới
                  </button>
                  <button
                    type="button"
                    onClick={() => goToPage(viewPage + 1)}
                    disabled={(totalPages > 0 && viewPage >= totalPages) || isEditing}
                    className="w-6 h-6 rounded border border-outline-variant/35 bg-surface-container-lowest hover:bg-surface-container text-on-surface flex items-center justify-center disabled:opacity-40 cursor-pointer"
                    title="Trang sau"
                  >
                    <span className="material-symbols-outlined text-[15px]">chevron_right</span>
                  </button>
                </form>

                <button
                  type="button"
                  onClick={() => setPreviewExpanded((prev) => !prev)}
                  className="text-[11px] text-on-surface-variant hover:text-on-surface font-medium flex items-center gap-0.5 cursor-pointer ml-1"
                >
                  <span>{previewExpanded ? 'Thu gọn' : 'Mở rộng'}</span>
                  <span className="material-symbols-outlined text-[15px]">
                    {previewExpanded ? 'expand_less' : 'expand_more'}
                  </span>
                </button>
              </div>
            </div>

            {previewExpanded && (
              <div className="p-3 flex flex-col gap-2">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {/* Left Half: PDF Page Preview */}
                  <div className="flex flex-col rounded-lg border border-outline-variant/25 bg-surface-container-lowest overflow-hidden">
                    <div className="px-3 py-1.5 bg-surface-container-low border-b border-outline-variant/20 flex items-center justify-between text-[11px] font-semibold text-on-surface-variant">
                      <span>Trang PDF gốc · Trang {viewPage}</span>
                      <span className="font-normal">Tài liệu nguồn</span>
                    </div>
                    <div className="h-[440px] overflow-auto bg-slate-100 p-2 flex justify-center items-start">
                      {pdfImgError ? (
                        <div className="h-full flex items-center justify-center text-xs text-on-surface-variant text-center px-4">
                          Không tải được ảnh trang PDF số {viewPage}.
                        </div>
                      ) : (
                        <img
                          key={`${task.id}-pdf-page-${viewPage}`}
                          src={api.getTaskPdfPageUrl(task.id, viewPage)}
                          alt={`Trang PDF ${viewPage}`}
                          onError={() => setPdfImgError(true)}
                          className="w-full h-auto max-w-full rounded shadow-sm bg-white"
                        />
                      )}
                    </div>
                  </div>

                  {/* Right Half: Extracted Text + Manual Edit */}
                  <div className="flex flex-col rounded-lg border border-outline-variant/25 bg-surface-container-lowest overflow-hidden">
                    <div className="px-3 py-1.5 bg-surface-container-low border-b border-outline-variant/20 flex items-center justify-between gap-2 flex-wrap">
                      <div className="flex items-center gap-2 text-[11px] font-semibold text-on-surface-variant">
                        <span>Nội dung trích xuất · Trang {viewPage}</span>
                        {methodLabel && (
                          <span className="px-1.5 py-0.5 rounded bg-surface-container text-on-surface font-label-code text-[10px]">
                            {methodLabel}
                          </span>
                        )}
                        {editedPages[viewPage] && (
                          <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[10px] font-semibold">
                            Đã chỉnh sửa
                          </span>
                        )}
                      </div>

                      {isAwaitingReview && isPageExtracted && !isEditing && (
                        <button
                          type="button"
                          onClick={handleStartEdit}
                          disabled={loadingPage === viewPage}
                          className="px-2 py-0.5 rounded border border-secondary/40 bg-secondary/10 hover:bg-secondary/20 text-secondary text-[11px] font-semibold flex items-center gap-1 cursor-pointer disabled:opacity-50"
                        >
                          <span className="material-symbols-outlined text-[14px]">edit</span>
                          <span>Chỉnh sửa</span>
                        </button>
                      )}
                    </div>

                    {!isPageExtracted ? (
                      <div className="h-[440px] flex items-center justify-center text-xs text-on-surface-variant text-center px-6">
                        Trang {viewPage} đang chờ OCR xử lý (hiện đã xong {ocrPreview.processed_pages}/{totalPages} trang).
                      </div>
                    ) : loadingPage === viewPage ? (
                      <div className="h-[440px] flex items-center justify-center text-xs text-on-surface-variant">
                        Đang tải nội dung trang {viewPage}...
                      </div>
                    ) : isEditing ? (
                      <div className="h-[440px] flex flex-col p-2.5 gap-2 bg-surface-container-lowest">
                        <textarea
                          value={draftText}
                          onChange={(e) => setDraftText(e.target.value)}
                          className="flex-1 w-full rounded-md border border-secondary/40 p-2.5 font-body-sm text-[12px] leading-relaxed text-on-surface bg-white focus:outline-none focus:ring-2 focus:ring-secondary/30 resize-none"
                        />
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => setIsEditing(false)}
                            disabled={savingEdit}
                            className="px-2.5 py-1 rounded border border-outline-variant/40 text-on-surface-variant hover:bg-surface-container text-[11px] font-medium cursor-pointer"
                          >
                            Hủy sửa
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleSaveEdit()}
                            disabled={savingEdit}
                            className="px-3 py-1 rounded bg-secondary hover:opacity-90 text-white text-[11px] font-semibold flex items-center gap-1 disabled:opacity-60 cursor-pointer"
                          >
                            <span className="material-symbols-outlined text-[14px]">save</span>
                            <span>{savingEdit ? 'Đang lưu...' : 'Lưu chỉnh sửa'}</span>
                          </button>
                        </div>
                      </div>
                    ) : (
                      <pre className="whitespace-pre-wrap break-words font-body-sm text-[12px] leading-relaxed text-on-surface bg-surface-container-lowest p-3 h-[440px] overflow-y-auto">
                        {currentPageText || '(Trang trống hoặc không trích xuất được văn bản)'}
                      </pre>
                    )}
                  </div>
                </div>

                {saveNotice && <p className="text-[11px] text-emerald-700 font-medium">{saveNotice}</p>}
                {pageLoadError && <p className="text-[11px] text-red-600">{pageLoadError}</p>}
              </div>
            )}
          </div>

          {ocrPreview.warnings.map((warning, idx) => (
            <p key={`ocr-warn-${idx}`} className="text-xs text-amber-800">{warning}</p>
          ))}
        </div>
      )}

      {task.result?.warnings?.map((warning, index) => <p key={index} className="text-xs text-amber-800">{warning}</p>)}
      {task.result?.artifact_ids?.[0] && <a className="text-xs text-secondary underline" href={'/api/files/' + encodeURIComponent(task.result.artifact_ids[0]) + '?download=true'}>Tải file nguồn đã lưu</a>}
      {isFailed && task.error_message && (
        <div className="p-2 rounded bg-red-50 border border-red-200 text-red-700 text-xs font-mono">
          Lỗi: {task.error_message}
        </div>
      )}
    </div>
  );
};


