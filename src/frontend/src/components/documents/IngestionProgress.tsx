'use client';

import React, { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { IngestionTask } from '../../lib/types';
import { ingestionSteps, stepStates, type TaskStatus } from '../../lib/ingestionSteps';
import { useDocumentStore } from '../../stores/documentStore';
import { OcrEditor } from './OcrEditor';
import { ChangeReview } from './ChangeReview';
import { IngestionStepper } from './IngestionStepper';

interface IngestionProgressProps {
  task: IngestionTask;
  onOpenDocument?: () => void;
  onUploadAnother?: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Đang chờ xử lý',
  parsing: 'Đang đọc & OCR',
  awaiting_review: 'Chờ rà soát',
  chunking: 'Tách cấu trúc',
  embedding: 'Đang lập chỉ mục',
  indexing: 'Đồng bộ dữ liệu',
  completed: 'Hoàn tất',
  failed: 'Thất bại',
  cancelled: 'Đã hủy',
};

const TERMINAL: TaskStatus[] = ['completed', 'failed', 'cancelled'];
const ZOOM_STEPS = [50, 75, 100, 125, 150, 200, 300];
const PANE_HEIGHT = 'h-[calc(100vh-260px)] min-h-[520px]';

type ReviewTab = 'ocr' | 'changes';

export const IngestionProgress: React.FC<IngestionProgressProps> = ({ task, onOpenDocument, onUploadAnother }) => {
  const cancelTask = useDocumentStore((s) => s.cancelTask);
  const confirmTaskReview = useDocumentStore((s) => s.confirmTaskReview);
  const [cancelling, setCancelling] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [previewExpanded, setPreviewExpanded] = useState(true);
  const [reviewTab, setReviewTab] = useState<ReviewTab>('ocr');
  const [targetPage, setTargetPage] = useState<number | null>(null);
  const [pageInput, setPageInput] = useState('1');
  const [pendingPage, setPendingPage] = useState<number | null>(null);
  const [fullPageTexts, setFullPageTexts] = useState<Record<number, string>>({});
  const [pageMethods, setPageMethods] = useState<Record<number, string>>({});
  const [editedPages, setEditedPages] = useState<Record<number, boolean>>({});
  const [loadingPage, setLoadingPage] = useState<number | null>(null);
  const [pageLoadError, setPageLoadError] = useState<string | null>(null);
  const [pdfImgError, setPdfImgError] = useState(false);
  const [zoom, setZoom] = useState<number | 'fit'>('fit');

  const [draftText, setDraftText] = useState('');
  const [draftPage, setDraftPage] = useState<number | null>(null);
  const [editorKey, setEditorKey] = useState(0);
  const [savingEdit, setSavingEdit] = useState(false);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);

  // The last running status, so a failed or cancelled task is marked at the step it stopped on.
  const lastActive = useRef<TaskStatus | null>(null);
  const stripRef = useRef<HTMLDivElement>(null);

  const isCompleted = task.status === 'completed';
  const isFailed = task.status === 'failed';
  const isCancelled = task.status === 'cancelled';
  const isAwaitingReview = task.status === 'awaiting_review';
  const isRunning = !TERMINAL.includes(task.status) && !isAwaitingReview;
  const canCancel = isRunning || isAwaitingReview;
  const statusText = STATUS_LABELS[task.status] || task.status;

  const steps = ingestionSteps(task.document_type);
  const states = stepStates(steps, task.status, lastActive.current);

  const ocrPreview = task.ocr_preview;
  const recentPages = ocrPreview?.recent_pages ?? [];
  const processedPages = ocrPreview?.processed_pages ?? 0;
  const latestProcessedPage = processedPages || recentPages[recentPages.length - 1]?.page_number || 1;
  const totalPages = ocrPreview?.total_pages || latestProcessedPage || 1;
  const viewPage = Math.max(1, Math.min(targetPage ?? latestProcessedPage, Math.max(totalPages, 1)));
  const showOcrPanel = !isAwaitingReview || reviewTab === 'ocr';

  useEffect(() => {
    if (!TERMINAL.includes(task.status)) lastActive.current = task.status;
  }, [task.status]);

  useEffect(() => {
    if (!canCancel) setCancelling(false);
    if (!isAwaitingReview) setConfirming(false);
  }, [canCancel, isAwaitingReview]);

  useEffect(() => {
    lastActive.current = null;
    setTargetPage(null);
    setPageInput('1');
    setPendingPage(null);
    setFullPageTexts({});
    setPageMethods({});
    setEditedPages({});
    setLoadingPage(null);
    setPageLoadError(null);
    setPdfImgError(false);
    setDraftText('');
    setDraftPage(null);
    setSaveNotice(null);
    setPreviewExpanded(true);
    setReviewTab('ocr');
  }, [task.id]);

  useEffect(() => {
    setPageInput(String(viewPage));
    setPdfImgError(false);
    setSaveNotice(null);
    stripRef.current?.querySelector<HTMLElement>(`[data-page="${viewPage}"]`)?.scrollIntoView({ block: 'nearest' });
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
        if (!cancelled) setPageLoadError(errorMessage(e));
      })
      .finally(() => {
        if (!cancelled) setLoadingPage(null);
      });
    return () => {
      cancelled = true;
    };
  }, [task.id, task.document_type, viewPage, ocrPreview?.processed_pages, fullPageTexts]);

  const recentMatch = recentPages.find((p) => p.page_number === viewPage);
  const isPageExtracted = viewPage <= processedPages;
  const currentPageText = fullPageTexts[viewPage] ?? recentMatch?.preview_text ?? '';
  const currentPageMethod = pageMethods[viewPage] ?? recentMatch?.method ?? '';
  const pageLoaded = fullPageTexts[viewPage] !== undefined;
  const canEditPage = isAwaitingReview && isPageExtracted && pageLoaded && draftPage === viewPage;
  // Unsaved edits on the open page; page changes ask first and confirmation waits.
  const isEditing = canEditPage && draftText !== currentPageText;

  // Open the editor on the full text of each page once it is loaded.
  useEffect(() => {
    if (!isAwaitingReview || !pageLoaded || draftPage === viewPage) return;
    setDraftText(fullPageTexts[viewPage] ?? '');
    setDraftPage(viewPage);
    setEditorKey((k) => k + 1);
  }, [isAwaitingReview, pageLoaded, draftPage, viewPage, fullPageTexts]);

  const methodOf = (page: number) => pageMethods[page] ?? recentPages.find((p) => p.page_number === page)?.method ?? '';
  const methodLabel = (method: string) =>
    method === 'ocr' ? 'OCR' : method === 'text' ? 'Text layer' : method === 'empty' ? 'Trang trống' : method;

  const revertDraft = () => {
    setDraftText(currentPageText);
    setEditorKey((k) => k + 1);
    setSaveNotice(null);
  };

  const openPage = (page: number) => {
    setPageLoadError(null);
    setPendingPage(null);
    setTargetPage(page);
    setPageInput(String(page));
  };

  const goToPage = (nextPage: number) => {
    const clamped = Math.max(1, Math.min(nextPage, Math.max(totalPages, 1)));
    if (clamped === viewPage) {
      setPageInput(String(viewPage));
      return;
    }
    if (isEditing) {
      setPendingPage(clamped);
      return;
    }
    openPage(clamped);
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

  const handleSaveEdit = async (): Promise<boolean> => {
    if (savingEdit || !isEditing) return !isEditing;
    setSavingEdit(true);
    setPageLoadError(null);
    setSaveNotice(null);
    try {
      const updated = await api.updateTaskOCRPage(task.id, viewPage, draftText);
      setFullPageTexts((prev) => ({ ...prev, [viewPage]: updated.text }));
      setEditedPages((prev) => ({ ...prev, [viewPage]: true }));
      setDraftText(updated.text);
      setSaveNotice(`Đã lưu chỉnh sửa trang ${viewPage}.`);
      return true;
    } catch (e) {
      setPageLoadError(errorMessage(e));
      return false;
    } finally {
      setSavingEdit(false);
    }
  };

  const saveAndOpenPending = async () => {
    if (pendingPage === null) return;
    const target = pendingPage;
    if (await handleSaveEdit()) openPage(target);
  };

  const discardAndOpenPending = () => {
    if (pendingPage === null) return;
    // Reset the draft to the saved text so the next page opens clean.
    setDraftText(currentPageText);
    openPage(pendingPage);
  };

  // Alt+← / Alt+→ turn pages while the comparison view is open.
  const navigate = useRef(goToPage);
  navigate.current = goToPage;
  useEffect(() => {
    if (task.document_type !== 'pdf' || !ocrPreview || !previewExpanded || !showOcrPanel) return;
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
      e.preventDefault();
      navigate.current(viewPage + (e.key === 'ArrowRight' ? 1 : -1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [task.document_type, ocrPreview, previewExpanded, showOcrPanel, viewPage]);

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

  const zoomIndex = zoom === 'fit' ? ZOOM_STEPS.indexOf(100) : ZOOM_STEPS.indexOf(zoom);
  const stepZoom = (delta: number) => setZoom(ZOOM_STEPS[Math.max(0, Math.min(ZOOM_STEPS.length - 1, zoomIndex + delta))]);

  const statusTone = isCompleted
    ? 'bg-tertiary-fixed text-on-tertiary-fixed'
    : isFailed
    ? 'bg-error-container text-on-error-container'
    : isCancelled
    ? 'bg-amber-100 text-amber-900'
    : isAwaitingReview
    ? 'bg-indigo-100 text-indigo-900'
    : 'bg-secondary-fixed text-on-secondary-fixed';

  const iconButton = 'w-7 h-7 rounded-lg border border-outline-variant/35 bg-surface-container-lowest hover:bg-surface-container text-ink flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed';

  const ocrPanel = task.document_type === 'pdf' && ocrPreview && (
    <div className="rounded-xl border border-outline-variant/25 bg-surface-container-low/70 overflow-hidden">
      {/* Toolbar: page navigation, PDF zoom, collapse */}
      <div className="px-3 py-2 flex items-center justify-between gap-2 flex-wrap bg-surface-container-low border-b border-outline-variant/20">
        <div className="flex items-center gap-2 text-[12px] font-semibold text-ink">
          <span className="material-symbols-outlined text-[16px] text-secondary">chrome_reader_mode</span>
          <span>Đối chiếu trang PDF & nội dung trích xuất</span>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <form onSubmit={handleJumpToPage} className="flex items-center gap-1" title="Alt+← / Alt+→ để chuyển trang">
            <button type="button" onClick={() => goToPage(viewPage - 1)} disabled={viewPage <= 1} className={iconButton} aria-label="Trang trước">
              <span className="material-symbols-outlined text-[16px]">chevron_left</span>
            </button>
            <span className="text-[11.5px] text-ink-3 ml-1">Trang</span>
            <input type="text" inputMode="numeric" value={pageInput} onChange={(e) => setPageInput(e.target.value)}
              onBlur={() => setPageInput(String(viewPage))} aria-label="Số thứ tự trang (Enter để chuyển)"
              className="w-11 px-1 py-0.5 text-center rounded-md border border-outline-variant/40 bg-surface-container-lowest text-[12px] text-ink tabular-nums focus:outline-none focus:border-secondary" />
            <span className="text-[11.5px] text-ink-3 mr-1 tabular-nums">/ {totalPages || '?'}</span>
            <button type="button" onClick={() => goToPage(viewPage + 1)} disabled={totalPages > 0 && viewPage >= totalPages} className={iconButton} aria-label="Trang sau">
              <span className="material-symbols-outlined text-[16px]">chevron_right</span>
            </button>
          </form>

          {previewExpanded && (
            <div className="flex items-center gap-1" aria-label="Thu phóng trang PDF">
              <button type="button" onClick={() => stepZoom(-1)} disabled={zoomIndex <= 0} className={iconButton} aria-label="Thu nhỏ">
                <span className="material-symbols-outlined text-[16px]">zoom_out</span>
              </button>
              <button type="button" onClick={() => setZoom('fit')}
                className={`h-7 px-2 rounded-lg border text-[11.5px] font-medium tabular-nums ${zoom === 'fit' ? 'border-secondary/40 bg-secondary/10 text-secondary' : 'border-outline-variant/35 bg-surface-container-lowest text-ink hover:bg-surface-container'}`}>
                {zoom === 'fit' ? 'Vừa khung' : `${zoom}%`}
              </button>
              <button type="button" onClick={() => stepZoom(1)} disabled={zoomIndex >= ZOOM_STEPS.length - 1} className={iconButton} aria-label="Phóng to">
                <span className="material-symbols-outlined text-[16px]">zoom_in</span>
              </button>
            </div>
          )}

          <button type="button" onClick={() => setPreviewExpanded((prev) => !prev)}
            className="text-[11.5px] text-ink-3 hover:text-ink font-medium flex items-center gap-0.5">
            <span>{previewExpanded ? 'Thu gọn' : 'Mở rộng'}</span>
            <span className="material-symbols-outlined text-[15px]">{previewExpanded ? 'expand_less' : 'expand_more'}</span>
          </button>
        </div>
      </div>

      {pendingPage !== null && (
        <div role="alertdialog" aria-label="Trang có thay đổi chưa lưu"
          className="px-3 py-2 flex flex-wrap items-center gap-2 bg-amber-50 border-b border-amber-200 text-[12px] text-amber-900">
          <span className="material-symbols-outlined text-[16px]">warning</span>
          <span className="flex-1 min-w-[200px]">Trang {viewPage} có thay đổi chưa lưu. Lưu trước khi sang trang {pendingPage}?</span>
          <button type="button" onClick={() => void saveAndOpenPending()} disabled={savingEdit}
            className="px-2.5 py-1 rounded-lg bg-secondary text-white font-semibold hover:opacity-90 disabled:opacity-50">
            {savingEdit ? 'Đang lưu...' : 'Lưu & chuyển'}
          </button>
          <button type="button" onClick={discardAndOpenPending} disabled={savingEdit}
            className="px-2.5 py-1 rounded-lg border border-amber-300 hover:bg-amber-100 font-medium disabled:opacity-50">Bỏ thay đổi</button>
          <button type="button" onClick={() => setPendingPage(null)} disabled={savingEdit}
            className="px-2.5 py-1 rounded-lg hover:bg-amber-100 font-medium disabled:opacity-50">Ở lại</button>
        </div>
      )}

      {previewExpanded && (
        <div className="p-3 flex flex-col gap-2">
          <div className="flex gap-3">
            {/* Page strip */}
            <div ref={stripRef} aria-label="Danh sách trang"
              className={`hidden md:flex flex-col gap-1 w-[60px] shrink-0 overflow-y-auto legal-scroll pr-0.5 ${PANE_HEIGHT}`}>
              {Array.from({ length: Math.max(totalPages, 1) }, (_, i) => i + 1).map((page) => {
                const method = methodOf(page);
                const extracted = page <= processedPages;
                const dot = editedPages[page] ? 'bg-emerald-500'
                  : method === 'ocr' ? 'bg-violet-500'
                  : method === 'empty' ? 'bg-slate-400'
                  : '';
                const label = [`Trang ${page}`, editedPages[page] && 'đã chỉnh sửa', method && methodLabel(method), !extracted && 'chưa xử lý']
                  .filter(Boolean).join(' · ');
                return (
                  <button key={page} type="button" data-page={page} onClick={() => goToPage(page)} title={label} aria-label={label}
                    aria-current={page === viewPage ? 'page' : undefined}
                    className={`relative shrink-0 h-9 rounded-lg border text-[12px] font-medium tabular-nums transition-colors ${
                      page === viewPage ? 'border-secondary bg-secondary/10 text-secondary ring-1 ring-secondary/40'
                        : 'border-outline-variant/30 bg-surface-container-lowest text-ink hover:bg-surface-container'
                    } ${extracted ? '' : 'opacity-40'}`}>
                    {page}
                    {dot && <span className={`absolute top-1 right-1 w-1.5 h-1.5 rounded-full ${dot}`} />}
                  </button>
                );
              })}
            </div>

            <div className="flex-1 min-w-0 grid grid-cols-1 lg:grid-cols-2 gap-3">
              {/* PDF page */}
              <div className="flex flex-col rounded-lg border border-outline-variant/25 bg-surface-container-lowest overflow-hidden">
                <div className="px-3 py-1.5 bg-surface-container-low border-b border-outline-variant/20 flex items-center justify-between text-[11.5px] font-semibold text-ink-3">
                  <span>Trang PDF gốc · Trang {viewPage}</span>
                  <span className="font-normal">Tài liệu nguồn</span>
                </div>
                <div className={`${PANE_HEIGHT} overflow-auto bg-slate-100 p-2`}>
                  {pdfImgError ? (
                    <div className="h-full flex items-center justify-center text-xs text-ink-3 text-center px-4">
                      Không tải được ảnh trang PDF số {viewPage}.
                    </div>
                  ) : (
                    <img key={`${task.id}-pdf-page-${viewPage}`} src={api.getTaskPdfPageUrl(task.id, viewPage)}
                      alt={`Trang PDF ${viewPage}`} onError={() => setPdfImgError(true)}
                      style={{ width: zoom === 'fit' ? '100%' : `${zoom}%` }}
                      className="h-auto max-w-none mx-auto rounded shadow-sm bg-white" />
                  )}
                </div>
              </div>

              {/* Extracted text and editor */}
              <div className="flex flex-col rounded-lg border border-outline-variant/25 bg-surface-container-lowest overflow-hidden">
                <div className="px-3 py-1.5 bg-surface-container-low border-b border-outline-variant/20 flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2 text-[11.5px] font-semibold text-ink-3">
                    <span>Nội dung trích xuất · Trang {viewPage}</span>
                    {currentPageMethod && (
                      <span className="px-1.5 py-0.5 rounded bg-surface-container text-ink text-[11.5px]">{methodLabel(currentPageMethod)}</span>
                    )}
                    {editedPages[viewPage] && (
                      <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 text-[11.5px] font-semibold">Đã chỉnh sửa</span>
                    )}
                    {isEditing && (
                      <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 text-[11.5px] font-semibold">Chưa lưu</span>
                    )}
                  </div>
                  {canEditPage && (
                    <div className="flex items-center gap-1.5">
                      <button type="button" onClick={revertDraft} disabled={savingEdit || !isEditing}
                        className="px-2.5 py-1 rounded-lg border border-outline-variant/40 text-ink-3 hover:bg-surface-container text-[11.5px] font-medium disabled:opacity-40 disabled:cursor-not-allowed">
                        Bỏ thay đổi
                      </button>
                      <button type="button" onClick={() => void handleSaveEdit()} disabled={savingEdit || !isEditing}
                        className="px-3 py-1 rounded-lg bg-secondary hover:opacity-90 text-white text-[11.5px] font-semibold flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed">
                        <span className="material-symbols-outlined text-[14px]">save</span>
                        <span>{savingEdit ? 'Đang lưu...' : 'Lưu trang'}</span>
                      </button>
                    </div>
                  )}
                </div>

                {!isPageExtracted ? (
                  <div className={`${PANE_HEIGHT} flex items-center justify-center text-xs text-ink-3 text-center px-6`}>
                    Trang {viewPage} đang chờ OCR xử lý (hiện đã xong {processedPages}/{totalPages} trang).
                  </div>
                ) : loadingPage === viewPage ? (
                  <div className={`${PANE_HEIGHT} flex items-center justify-center text-xs text-ink-3`}>
                    Đang tải nội dung trang {viewPage}...
                  </div>
                ) : canEditPage ? (
                  <div className={PANE_HEIGHT}>
                    <OcrEditor key={`${task.id}-${viewPage}-${editorKey}`} value={draftText} editable={!savingEdit}
                      onChange={setDraftText} onSave={() => void handleSaveEdit()} />
                  </div>
                ) : (
                  <pre className={`whitespace-pre-wrap break-words text-[12px] leading-relaxed text-ink bg-surface-container-lowest p-3 overflow-y-auto ${PANE_HEIGHT}`}>
                    {currentPageText || '(Trang trống hoặc không trích xuất được văn bản)'}
                  </pre>
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-3">
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />Đã chỉnh sửa</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-violet-500" />OCR scan</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-slate-400" />Trang trống</span>
            <span className="ml-auto">Alt+← / Alt+→ chuyển trang</span>
          </div>
          {saveNotice && <p className="text-[11.5px] text-emerald-700 font-medium">{saveNotice}</p>}
          {pageLoadError && <p role="alert" className="text-[11.5px] text-red-600">{pageLoadError}</p>}
        </div>
      )}
    </div>
  );

  return (
    <div className="w-full bg-surface-container-lowest rounded-xl p-space-md shadow-sm border border-secondary/30 flex flex-col gap-4 animate-fadeIn">
      {/* Header: document, status and actions */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-secondary/10 flex items-center justify-center text-secondary shrink-0">
            <span className="material-symbols-outlined text-[20px]">{task.document_type === 'pdf' ? 'picture_as_pdf' : 'html'}</span>
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-[14px] font-semibold text-ink truncate" title={task.file_name}>{task.file_name}</span>
            <span className="text-[11.5px] text-ink-3 flex items-center gap-1.5">
              {task.document_type === 'pdf' ? 'Văn bản PDF (OCR)' : 'Pháp điển HTML'}
              <span className={`px-2 py-0.5 rounded font-semibold ${statusTone}`}>
                {statusText}{isRunning ? ` · ${Math.round(task.progress)}%` : ''}
              </span>
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {canCancel && (
            <button type="button" onClick={handleCancel} disabled={cancelling || confirming}
              className="px-3 py-1.5 rounded-lg border border-red-300 bg-red-50 hover:bg-red-100 text-red-700 text-[12px] font-semibold flex items-center gap-1 transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
              <span className="material-symbols-outlined text-[15px]">stop_circle</span>
              <span>{cancelling ? 'Đang hủy...' : 'Hủy xử lý'}</span>
            </button>
          )}
          {isAwaitingReview && (
            <button type="button" onClick={handleConfirm} disabled={confirming || isEditing}
              title={isEditing ? 'Hãy lưu hoặc bỏ chỉnh sửa trước khi xác nhận lập chỉ mục' : undefined}
              className="px-3 py-1.5 rounded-lg bg-secondary hover:opacity-90 text-white text-[12px] font-semibold flex items-center gap-1 transition-all disabled:opacity-60 disabled:cursor-not-allowed shadow-sm">
              <span className="material-symbols-outlined text-[15px]">check_circle</span>
              <span>{confirming ? 'Đang bắt đầu...' : 'Xác nhận & Lập chỉ mục'}</span>
            </button>
          )}
          {TERMINAL.includes(task.status) && onUploadAnother && (
            <button type="button" onClick={onUploadAnother}
              className="px-3 py-1.5 rounded-lg border border-secondary/40 text-secondary hover:bg-secondary/10 text-[12px] font-semibold flex items-center gap-1">
              <span className="material-symbols-outlined text-[15px]">add</span>
              <span>Nạp văn bản khác</span>
            </button>
          )}
          {isCompleted && onOpenDocument && (
            <button type="button" onClick={onOpenDocument}
              className="px-3 py-1.5 rounded-lg bg-secondary hover:opacity-90 text-white text-[12px] font-semibold flex items-center gap-1 shadow-sm">
              <span className="material-symbols-outlined text-[15px]">folder_open</span>
              <span>Xem văn bản trong kho</span>
            </button>
          )}
        </div>
      </div>

      {/* Stepper and current work */}
      <div className="flex flex-col gap-3 rounded-xl bg-surface-container-low/60 border border-outline-variant/20 px-3 pt-4 pb-3">
        <IngestionStepper steps={steps} states={states} progress={task.progress} paused={isAwaitingReview} />
        <div className="flex items-center gap-2 text-[12px] pt-2 border-t border-outline-variant/20">
          <span className={`material-symbols-outlined text-[16px] shrink-0 ${
            isFailed ? 'text-red-600' : isCompleted ? 'text-emerald-600' : isCancelled ? 'text-amber-600' : isAwaitingReview ? 'text-indigo-600' : 'text-secondary animate-spin'
          }`}>
            {isFailed ? 'error' : isCompleted ? 'task_alt' : isCancelled ? 'cancel' : isAwaitingReview ? 'edit_document' : 'autorenew'}
          </span>
          <span className="font-semibold text-ink-3 shrink-0">Công việc hiện tại:</span>
          <span className="font-medium text-ink">{task.current_step}</span>
        </div>
        {isRunning && (
          <div className="w-full h-1.5 rounded-full bg-surface-container-high overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-secondary to-indigo-500 transition-all duration-500"
              style={{ width: `${Math.max(task.progress, 0)}%` }} />
          </div>
        )}
      </div>

      {task.document_type === 'pdf' && ocrPreview && (
        <div className="flex flex-wrap items-center gap-2 text-[11.5px]">
          <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/25 text-ink">
            Trang đã xử lý: <strong>{processedPages}/{ocrPreview.total_pages || '?'}</strong>
          </span>
          <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/25 text-ink-3">
            Text: <strong className="text-ink">{ocrPreview.text_pages}</strong> · OCR scan: <strong className="text-ink">{ocrPreview.ocr_pages}</strong>
            {ocrPreview.empty_pages > 0 && <> · Trống: <strong>{ocrPreview.empty_pages}</strong></>}
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
      )}

      {isAwaitingReview && task.document_type === 'pdf' && (
        <div role="tablist" aria-label="Rà soát trước khi lập chỉ mục" className="flex items-center gap-1 p-1 rounded-lg bg-surface-container self-start">
          {([['ocr', 'fact_check', 'Rà soát OCR'], ['changes', 'difference', 'So sánh thay đổi']] as const).map(([key, icon, label]) => (
            <button key={key} type="button" role="tab" aria-selected={reviewTab === key} onClick={() => setReviewTab(key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12.5px] font-medium transition-all ${
                reviewTab === key ? 'bg-surface-container-lowest text-secondary shadow-sm' : 'text-ink-3 hover:text-ink'
              }`}>
              <span className="material-symbols-outlined text-[17px]">{icon}</span>
              {label}
              {key === 'ocr' && isEditing && <span className="w-1.5 h-1.5 rounded-full bg-amber-500" title="Có thay đổi chưa lưu" />}
            </button>
          ))}
        </div>
      )}

      {showOcrPanel && ocrPanel}
      {task.document_type === 'pdf' && ocrPreview && showOcrPanel && ocrPreview.warnings.map((warning, idx) => (
        <p key={`ocr-warn-${idx}`} className="text-xs text-amber-800">{warning}</p>
      ))}

      {/* Kept mounted so an analysis survives switching between the review tabs. */}
      {isAwaitingReview && task.document_type === 'pdf' && (
        <div className={reviewTab === 'changes' ? 'flex flex-col gap-2' : 'hidden'}>
          {isEditing && (
            <p className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-[12px] text-amber-900">
              Trang {viewPage} còn thay đổi chưa lưu ở tab Rà soát OCR; lưu trang trước khi phân tích để so sánh dùng nội dung mới nhất.
            </p>
          )}
          <ChangeReview key={task.id} taskId={task.id} hasUnsavedEdits={isEditing} />
        </div>
      )}

      {task.result?.warnings?.map((warning, index) => <p key={index} className="text-xs text-amber-800">{warning}</p>)}
      {task.result?.artifact_ids?.[0] && (
        <a className="text-xs text-secondary underline self-start" href={'/api/files/' + encodeURIComponent(task.result.artifact_ids[0]) + '?download=true'}>
          Tải file nguồn đã lưu
        </a>
      )}
      {isFailed && task.error_message && (
        <div className="p-2 rounded bg-red-50 border border-red-200 text-red-700 text-xs font-mono">Lỗi: {task.error_message}</div>
      )}
    </div>
  );
};
