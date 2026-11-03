'use client';

import React from 'react';
import { IngestionTask } from '../../lib/types';

interface IngestionProgressProps {
  task: IngestionTask;
}

export const IngestionProgress: React.FC<IngestionProgressProps> = ({ task }) => {
  const isCompleted = task.status === 'completed';
  const isFailed = task.status === 'failed';

  return (
    <div className="w-full bg-surface-container-lowest rounded-xl p-space-md shadow-sm border border-secondary/30 flex flex-col gap-2.5 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-secondary/10 flex items-center justify-center text-secondary">
            <span className="material-symbols-outlined text-[18px]">
              {isCompleted ? 'check_circle' : isFailed ? 'error' : 'hourglass_top'}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="font-headline-sm text-headline-sm text-on-surface">
              Tiến trình Nạp tài liệu: {task.file_name}
            </span>
            <span className="font-label-code text-[11px] text-on-surface-variant">
              Mã nhiệm vụ: {task.id.slice(0, 8)} • Loại: {task.document_type.toUpperCase()}
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
                : 'bg-secondary-fixed text-on-secondary-fixed'
            }`}
          >
            {task.status.toUpperCase()} ({Math.round(task.progress)}%)
          </span>
        </div>
      </div>

      {/* Progress Bar Container */}
      <div className="w-full h-3 rounded-full bg-surface-container-high overflow-hidden relative">
        <div
          className={`h-full transition-all duration-500 rounded-full ${
            isCompleted
              ? 'bg-emerald-600'
              : isFailed
              ? 'bg-red-600'
              : 'bg-gradient-to-r from-secondary to-indigo-500 animate-pulse'
          }`}
          style={{ width: `${Math.max(task.progress, 5)}%` }}
        ></div>
      </div>

      {/* Step details & Chunks Counter */}
      <div className="flex items-center justify-between font-label-code text-[11px] text-on-surface-variant pt-0.5">
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-[15px] text-secondary">sync</span>
          <span className="font-medium text-on-surface">{task.current_step}</span>
        </div>
        {task.total_chunks > 0 && (
          <span className="font-metric-num text-secondary font-bold">
            Tạo vector: {task.embedded_chunks} / {task.total_chunks} đoạn
          </span>
        )}
      </div>

      {isFailed && task.error_message && (
        <div className="p-2 rounded bg-red-50 border border-red-200 text-red-700 text-xs font-mono">
          Lỗi: {task.error_message}
        </div>
      )}
    </div>
  );
};

