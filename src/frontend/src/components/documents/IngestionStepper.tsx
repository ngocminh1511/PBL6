'use client';

import React from 'react';
import type { IngestionStep, StepState } from '../../lib/ingestionSteps';

const ICON: Record<StepState, string> = {
  done: 'check', active: 'progress_activity', pending: '', failed: 'close', cancelled: 'block',
};
const DOT: Record<StepState, string> = {
  done: 'bg-emerald-600 text-white border-emerald-600',
  active: 'bg-secondary text-white border-secondary',
  pending: 'bg-surface-container-lowest text-ink-3 border-outline-variant/60',
  failed: 'bg-red-600 text-white border-red-600',
  cancelled: 'bg-amber-500 text-white border-amber-500',
};
const LABEL: Record<StepState, string> = {
  done: 'text-emerald-800', active: 'text-secondary font-semibold', pending: 'text-ink-3',
  failed: 'text-red-700 font-semibold', cancelled: 'text-amber-800 font-semibold',
};

/**
 * Horizontal ingestion stepper; `progress` is shown under the active step.
 * `paused` marks an active step that waits for the user instead of a worker.
 */
export function IngestionStepper({ steps, states, progress, muted = false, paused = false }: {
  steps: IngestionStep[]; states: StepState[]; progress?: number; muted?: boolean; paused?: boolean;
}) {
  return (
    <ol className={`flex items-start w-full overflow-x-auto ${muted ? 'opacity-70' : ''}`} aria-label="Các bước nạp văn bản">
      {steps.map((step, index) => {
        const state = states[index] ?? 'pending';
        const lineDone = index > 0 && state !== 'pending';
        return (
          <li key={step.key} className="flex-1 min-w-[88px] flex flex-col items-center relative"
            aria-current={state === 'active' ? 'step' : undefined}>
            {index > 0 && (
              <span className={`absolute top-[13px] right-1/2 w-full h-0.5 -z-0 ${lineDone ? 'bg-emerald-500' : 'bg-outline-variant/40'}`} />
            )}
            <span className={`relative z-10 w-7 h-7 rounded-full border-2 flex items-center justify-center text-[12px] font-semibold ${DOT[state]}`}>
              {state === 'active' && paused
                ? <span className="material-symbols-outlined text-[16px]">edit_note</span>
                : ICON[state]
                ? <span className={`material-symbols-outlined text-[16px] ${state === 'active' ? 'animate-spin' : ''}`}>{ICON[state]}</span>
                : index + 1}
            </span>
            <span className={`mt-1.5 text-[11.5px] text-center leading-tight px-1 ${LABEL[state]}`}>{step.label}</span>
            {state === 'active' && !paused && progress !== undefined && (
              <span className="text-[11px] text-ink-3 tabular-nums">{Math.round(progress)}%</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
