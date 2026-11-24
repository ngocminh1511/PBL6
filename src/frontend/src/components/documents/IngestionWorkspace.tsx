'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useDocumentStore } from '../../stores/documentStore';
import { ingestionSteps } from '../../lib/ingestionSteps';
import { IngestionList } from './IngestionList';
import { IngestionProgress } from './IngestionProgress';
import { IngestionStepper } from './IngestionStepper';

const PDF_STEPS = ingestionSteps('pdf');
const DEFAULT_WIDTH = 30; // percent of the row for the upload list
const MIN_WIDTH = 20;
const MAX_WIDTH = 50;
const STORAGE_KEY = 'ingestion.listWidth';

function loadWidth() {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEY));
    if (value >= MIN_WIDTH && value <= MAX_WIDTH) return value;
  } catch { /* storage unavailable: default */ }
  return DEFAULT_WIDTH;
}

/**
 * Upload list on the left, the selected upload on the right. The selected
 * task lives in the URL (?task=), so a reload or another machine opens the
 * same upload; its OCR text comes from the server's revisions.
 */
export function IngestionWorkspace({ taskId, onSelectTask, onUpload, onOpenDocument }: {
  taskId: string | null;
  onSelectTask: (id: string) => void;
  onUpload: () => void;
  onOpenDocument: (documentId: string | null) => void;
}) {
  const { tasks, tasksLoading, tasksError, fetchTasks, activeTask, openTask } = useDocumentStore();

  useEffect(() => { void fetchTasks(); }, [fetchTasks]);
  // Open the task named in the URL; a fresh upload names itself once it starts.
  useEffect(() => {
    if (taskId && activeTask?.id !== taskId) void openTask(taskId);
  }, [taskId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (activeTask && activeTask.id !== taskId) onSelectTask(activeTask.id);
  }, [activeTask?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = activeTask && (!taskId || activeTask.id === taskId) ? activeTask : null;

  // The list column is resizable on desktop; the bar between the columns drags it.
  const row = useRef<HTMLDivElement>(null);
  const last = useRef<number | null>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  useEffect(() => { setWidth(loadWidth()); }, []);
  useEffect(() => { try { localStorage.setItem(STORAGE_KEY, String(width)); } catch { /* not kept */ } }, [width]);
  const drag = (dx: number) => {
    const total = row.current?.clientWidth || 1;
    setWidth((w) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, w + (dx / total) * 100)));
  };

  return (
    <div ref={row} className="flex flex-col lg:flex-row gap-space-md lg:gap-0 items-stretch lg:items-start"
      style={{ ['--list-width' as string]: `${width}%` }}>
      <div className="lg:sticky lg:top-4 shrink-0 w-full lg:w-[var(--list-width)] h-[45vh] lg:h-[calc(100vh-7.5rem)] min-h-[360px]">
        <IngestionList tasks={tasks} loading={tasksLoading} error={tasksError} selectedId={taskId}
          onSelect={onSelectTask} onUpload={onUpload} />
      </div>

      <div role="separator" aria-orientation="vertical" title="Kéo để đổi độ rộng · nhấp đúp để đặt lại"
        onDoubleClick={() => setWidth(DEFAULT_WIDTH)}
        onPointerDown={(e) => { last.current = e.clientX; e.currentTarget.setPointerCapture(e.pointerId); }}
        onPointerMove={(e) => {
          if (last.current === null) return;
          drag(e.clientX - last.current);
          last.current = e.clientX;
        }}
        onPointerUp={() => { last.current = null; }}
        className="hidden lg:flex group shrink-0 w-4 self-stretch lg:sticky lg:top-4 lg:h-[calc(100vh-7.5rem)] justify-center cursor-col-resize touch-none select-none">
        <span className="w-0.5 my-2 rounded-full bg-outline-variant/30 group-hover:bg-secondary/40 group-active:bg-secondary/70 transition-colors" />
      </div>

      <div className="min-w-0 flex-1">
        {shown ? (
          <IngestionProgress task={shown} onUploadAnother={onUpload}
            onOpenDocument={() => onOpenDocument(shown.document_id ?? shown.result?.document_ids?.[0] ?? null)} />
        ) : (
          <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm px-space-md py-12 flex flex-col items-center gap-5 text-center">
            <div className="w-14 h-14 rounded-2xl bg-secondary-fixed flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined text-[30px]">upload_file</span>
            </div>
            <div className="flex flex-col gap-1 max-w-md">
              <span className="text-[15px] font-semibold text-ink">{taskId ? 'Đang mở lượt nạp…' : 'Chọn một lượt nạp hoặc nạp văn bản mới'}</span>
              <span className="text-[12.5px] text-ink-3">
                Mọi lượt nạp được giữ lại cùng bản OCR và các bản rà soát, nên có thể mở lại để xem, sửa và nạp lại mà không phải OCR lại.
              </span>
            </div>
            <div className="w-full max-w-3xl pt-4 border-t border-outline-variant/20">
              <IngestionStepper steps={PDF_STEPS} states={PDF_STEPS.map(() => 'pending')} muted />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
