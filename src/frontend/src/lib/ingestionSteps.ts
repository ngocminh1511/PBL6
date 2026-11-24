import type { IngestionTask } from './types';

export type TaskStatus = IngestionTask['status'];
export type StepState = 'done' | 'active' | 'pending' | 'failed' | 'cancelled';
export interface IngestionStep { key: string; label: string; statuses: TaskStatus[] }

const PDF_STEPS: IngestionStep[] = [
  { key: 'upload', label: 'Tải lên', statuses: [] },
  { key: 'ocr', label: 'Đọc & OCR', statuses: ['pending', 'parsing'] },
  { key: 'review', label: 'Rà soát OCR', statuses: ['awaiting_review'] },
  { key: 'compare', label: 'So sánh thay đổi', statuses: ['awaiting_review'] },
  { key: 'index', label: 'Lập chỉ mục', statuses: ['chunking', 'embedding', 'indexing'] },
  { key: 'done', label: 'Hoàn tất', statuses: ['completed'] },
];

const HTML_STEPS: IngestionStep[] = [
  { key: 'upload', label: 'Tải lên', statuses: [] },
  { key: 'parse', label: 'Đọc văn bản', statuses: ['pending', 'parsing'] },
  { key: 'index', label: 'Lập chỉ mục', statuses: ['chunking', 'embedding', 'indexing'] },
  { key: 'done', label: 'Hoàn tất', statuses: ['completed'] },
];

/** Steps shown for a task; Pháp điển HTML has no OCR review. */
export function ingestionSteps(documentType?: string): IngestionStep[] {
  return documentType === 'phap_dien_html' ? HTML_STEPS : PDF_STEPS;
}

/**
 * State of each step. A failed or cancelled task stops at the step of
 * `lastActive`, the last running status the page saw; when unknown, the first
 * processing step is marked.
 */
export function stepStates(steps: IngestionStep[], status: TaskStatus, lastActive?: TaskStatus | null,
  reviewTab?: 'ocr' | 'changes'): StepState[] {
  if (status === 'completed') return steps.map(() => 'done');
  // In review the open tab tells which of the two review steps the user is on.
  if (status === 'awaiting_review' && reviewTab) {
    const on = steps.findIndex((step) => step.key === (reviewTab === 'ocr' ? 'review' : 'compare'));
    return steps.map((_, index) => (index < on ? 'done' : index === on ? 'active' : 'pending'));
  }
  const terminal = status === 'failed' || status === 'cancelled';
  const at: TaskStatus = terminal ? (lastActive && lastActive !== status ? lastActive : 'pending') : status;
  let first = steps.findIndex((step) => step.statuses.includes(at));
  if (first === -1) first = 1;
  return steps.map((step, index) => {
    if (index < first) return 'done';
    if (index === first) return terminal ? (status as 'failed' | 'cancelled') : 'active';
    if (!terminal && step.statuses.includes(at)) return 'active';
    return 'pending';
  });
}

/**
 * What clicking an earlier step does, or null when it cannot go back there:
 * - tab: switch between the two review steps, nothing is lost;
 * - stop: stop the running indexing and return to review (the draft stays);
 * - resume: a cancelled or failed task returns to its draft, without OCR;
 * - reopen: an indexed task opens a new draft; the corpus changes only when it is re-indexed.
 * Only the review steps are targets: going back to upload or OCR means a new upload.
 */
export type StepBack = { kind: 'tab' | 'stop' | 'resume' | 'reopen'; tab: 'ocr' | 'changes' };

export function stepBack(step: IngestionStep, index: number, states: StepState[], task: {
  status: TaskStatus; documentType?: string; hasDraft: boolean; hasIndexed: boolean;
}): StepBack | null {
  if (task.documentType !== 'pdf' || (step.key !== 'review' && step.key !== 'compare')) return null;
  const tab = step.key === 'review' ? 'ocr' : 'changes';
  const current = states.findIndex((state) => state !== 'done');
  const at = current === -1 ? states.length : current;
  if (index >= at && !(task.status === 'failed' || task.status === 'cancelled')) return null;
  if (task.status === 'awaiting_review') return { kind: 'tab', tab };
  if (['chunking', 'embedding', 'indexing'].includes(task.status)) return task.hasDraft ? { kind: 'stop', tab } : null;
  if (task.status === 'failed' || task.status === 'cancelled') return task.hasDraft ? { kind: 'resume', tab } : null;
  if (task.status === 'completed') return task.hasIndexed && !task.hasDraft ? { kind: 'reopen', tab } : null;
  return null;
}
