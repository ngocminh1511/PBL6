'use client';

import React, { useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { IngestionTask, OCRPagePreview } from '../../lib/types';
import { useDocumentStore } from '../../stores/documentStore';

interface IngestionProgressProps {
  task: IngestionTask;
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Đang chờ xử lý',
  parsing: 'Đang đọc & OCR',
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

export const IngestionProgress: React.FC<IngestionProgressProps> = ({ task }) => {
  const cancelTask = useDocumentStore((s) => s.cancelTask);
  const [cancelling, setCancelling] = useState(false);
  const [previewExpanded, setPreviewExpanded] = useState(true);
  const [pinnedPage, setPinnedPage] = useState<number | null>(null);
  const [fullPageTexts, setFullPageTexts] = useState<Record<number, string>>({});
  const [loadingPage, setLoadingPage] = useState<number | null>(null);
  const [pageLoadError, setPageLoadError] = useState<string | null>(null);

  const isCompleted = task.status === 'completed';
  const isFailed = task.status === 'failed';
  const isCancelled = task.status === 'cancelled';
  const isRunning = !isCompleted && !isFailed && !isCancelled;
  const currentStage = isCompleted ? 3 : stageIndex(task.status);
  const statusText = STATUS_LABELS[task.status] || task.status;

  useEffect(() => {
    if (!isRunning) {
      setCancelling(false);
    }
  }, [isRunning]);

  useEffect(() => {
    setPinnedPage(null);
    setFullPageTexts({});
    setLoadingPage(null);
    setPageLoadError(null);
    setPreviewExpanded(true);
  }, [task.id]);

  const ocrPreview = task.ocr_preview;
  const recentPages = ocrPreview?.recent_pages ?? [];
  const activePage: OCRPagePreview | undefined =
    pinnedPage !== null
      ? recentPages.find((p) => p.page_number === pinnedPage) ?? recentPages[recentPages.length - 1]
      : recentPages[recentPages.length - 1];

  const handleLoadFullPage = async (pageNumber: number) => {
    if (loadingPage === pageNumber) return;
    setLoadingPage(pageNumber);
    setPageLoadError(null);
    try {
      const detail = await api.getTaskOCRPage(task.id, pageNumber);
      setFullPageTexts((prev) => ({ ...prev, [pageNumber]: detail.text }));
    } catch (e) {
      setPageLoadError(errorMessage(e));
    } finally {
      setLoadingPage(null);
    }
  };

  const confidencePercent =
    ocrPreview?.avg_confidence !== undefined && ocrPreview?.avg_confidence !== null
      ? Math.round(ocrPreview.avg_confidence * 100)
      : null;

  const confidenceBadgeClass =
    confidencePercent === null
      ? ''
      : confidencePercent >= 85
      ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
      : confidencePercent >= 70
      ? 'bg-amber-50 border-amber-200 text-amber-800'
      : 'bg-red-50 border-red-200 text-red-700';

  const handleCancel = async () => {
    if (!isRunning || cancelling) return;
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
              {isCompleted ? 'check_circle' : isFailed ? 'error' : isCancelled ? 'cancel' : 'sync'}
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

        <div className="flex items-center gap-2">
          <span
            className={`font-label-statute text-label-statute px-2.5 py-1 rounded font-bold ${
              isCompleted
                ? 'bg-tertiary-fixed text-on-tertiary-fixed'
                : isFailed
                ? 'bg-error-container text-on-error-container'
                : isCancelled
                ? 'bg-amber-100 text-amber-900'
                : 'bg-secondary-fixed text-on-secondary-fixed'
            }`}
          >
            {statusText} ({Math.round(task.progress)}%)
          </span>
          {isRunning && (
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelling}
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
              : 'bg-gradient-to-r from-secondary to-indigo-500 animate-pulse'
          }`}
          style={{ width: `${Math.max(task.progress, 0)}%` }}
        ></div>
      </div>

      {/* Current Step Highlight */}
      <div className="bg-surface-container-low rounded-lg px-3 py-2 flex items-center gap-2 font-body-sm text-[12px] border border-outline-variant/20">
        <span className={`material-symbols-outlined text-[16px] shrink-0 ${isFailed ? 'text-red-600' : isCompleted ? 'text-emerald-600' : isCancelled ? 'text-amber-600' : 'text-secondary animate-spin'}`}>
          {isFailed ? 'error' : isCompleted ? 'task_alt' : isCancelled ? 'cancel' : 'autorenew'}
        </span>
        <span className="font-semibold text-on-surface-variant shrink-0">Công việc hiện tại:</span>
        <span className="font-medium text-on-surface">{task.current_step}</span>
      </div>

      {/* Realtime OCR Inspection Metrics & Live Page Preview */}
      {task.document_type === 'pdf' && ocrPreview && (
        <div className="flex flex-col gap-2.5 border-t border-outline-variant/20 pt-2.5">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-label-statute">
            <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/25 text-on-surface">
              Trang đã xử lý: <strong>{ocrPreview.processed_pages}/{ocrPreview.total_pages || '?'}</strong>
            </span>
            <span className="px-2.5 py-1 rounded-md bg-surface-container-low border border-outline-variant/25 text-on-surface-variant">
              Text: <strong className="text-on-surface">{ocrPreview.text_pages}</strong> · OCR scan: <strong className="text-on-surface">{ocrPreview.ocr_pages}</strong>
              {ocrPreview.empty_pages > 0 && <> · Trống: <strong>{ocrPreview.empty_pages}</strong></>}
            </span>
            {confidencePercent !== null && (
              <span className={`px-2.5 py-1 rounded-md border font-semibold ${confidenceBadgeClass}`}>
                Độ tin cậy OCR TB: {confidencePercent}%
              </span>
            )}
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

          {recentPages.length > 0 && (
            <div className="rounded-lg border border-outline-variant/25 bg-surface-container-low/70 overflow-hidden">
              <div className="px-3 py-2 flex items-center justify-between gap-2 bg-surface-container-low border-b border-outline-variant/20">
                <div className="flex items-center gap-2 text-[12px] font-semibold text-on-surface">
                  <span className="material-symbols-outlined text-[16px] text-secondary">preview</span>
                  <span>Kiểm tra nội dung OCR realtime</span>
                  {activePage && (
                    <span className="font-normal text-[11px] text-on-surface-variant">
                      (Trang {activePage.page_number} · {activePage.method === 'ocr' ? `OCR${activePage.confidence != null ? ` ${Math.round(activePage.confidence * 100)}%` : ''}` : activePage.method === 'text' ? 'Text layer' : activePage.method} · {activePage.char_count} ký tự)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {pinnedPage !== null && isRunning && (
                    <button
                      type="button"
                      onClick={() => setPinnedPage(null)}
                      className="text-[11px] text-secondary hover:underline font-medium cursor-pointer"
                    >
                      Theo trang mới nhất
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setPreviewExpanded((prev) => !prev)}
                    className="text-[11px] text-on-surface-variant hover:text-on-surface font-medium flex items-center gap-0.5 cursor-pointer"
                  >
                    <span>{previewExpanded ? 'Thu gọn' : 'Mở rộng'}</span>
                    <span className="material-symbols-outlined text-[15px]">
                      {previewExpanded ? 'expand_less' : 'expand_more'}
                    </span>
                  </button>
                </div>
              </div>

              {previewExpanded && activePage && (
                <div className="p-2.5 flex flex-col gap-2">
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                    {recentPages.map((p) => {
                      const isSelected = p.page_number === activePage.page_number;
                      const pageConf = p.confidence != null ? `${Math.round(p.confidence * 100)}%` : null;
                      return (
                        <button
                          key={p.page_number}
                          type="button"
                          onClick={() => setPinnedPage(p.page_number)}
                          className={`px-2 py-1 rounded text-[11px] font-label-code shrink-0 border transition-colors cursor-pointer ${
                            isSelected
                              ? 'bg-secondary text-white border-secondary font-semibold'
                              : 'bg-surface-container-lowest text-on-surface-variant border-outline-variant/30 hover:border-secondary/50'
                          }`}
                        >
                          Tr.{p.page_number} · {p.method === 'ocr' ? (pageConf ? `OCR ${pageConf}` : 'OCR') : p.method === 'text' ? 'Text' : p.method}
                        </button>
                      );
                    })}
                  </div>

                  <pre className="whitespace-pre-wrap break-words font-body-sm text-[12px] leading-relaxed text-on-surface bg-surface-container-lowest rounded-md border border-outline-variant/20 p-2.5 max-h-48 overflow-y-auto">
                    {fullPageTexts[activePage.page_number] ?? (activePage.preview_text || '(Trang trống hoặc không trích xuất được văn bản)')}
                  </pre>

                  {pageLoadError && (
                    <p className="text-[11px] text-red-600">{pageLoadError}</p>
                  )}

                  {activePage.char_count > activePage.preview_text.length &&
                    fullPageTexts[activePage.page_number] === undefined && (
                      <div className="flex justify-end">
                        <button
                          type="button"
                          onClick={() => void handleLoadFullPage(activePage.page_number)}
                          disabled={loadingPage === activePage.page_number}
                          className="text-[11px] text-secondary hover:underline font-semibold disabled:opacity-60 cursor-pointer"
                        >
                          {loadingPage === activePage.page_number
                            ? 'Đang tải toàn bộ trang...'
                            : `Xem đầy đủ trang ${activePage.page_number} (${activePage.char_count} ký tự)`}
                        </button>
                      </div>
                    )}
                </div>
              )}
            </div>
          )}

          {ocrPreview.warnings.map((warning, idx) => (
            <p key={`ocr-warn-${idx}`} className="text-xs text-amber-800">{warning}</p>
          ))}
        </div>
      )}

      {task.result?.warnings.map((warning, index) => <p key={index} className="text-xs text-amber-800">{warning}</p>)}
      {task.result?.artifact_ids[0] && <a className="text-xs text-secondary underline" href={'/api/files/' + encodeURIComponent(task.result.artifact_ids[0]) + '?download=true'}>Tải file nguồn đã lưu</a>}
      {isFailed && task.error_message && (
        <div className="p-2 rounded bg-red-50 border border-red-200 text-red-700 text-xs font-mono">
          Lỗi: {task.error_message}
        </div>
      )}
    </div>
  );
};


