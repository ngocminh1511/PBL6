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
export function stepStates(steps: IngestionStep[], status: TaskStatus, lastActive?: TaskStatus | null): StepState[] {
  if (status === 'completed') return steps.map(() => 'done');
  const terminal = status === 'failed' || status === 'cancelled';
  const at: TaskStatus = terminal ? (lastActive && lastActive !== status ? lastActive : 'pending') : status;
  let first = steps.findIndex((step) => step.statuses.includes(at));
  if (first === -1) first = 1;
  return steps.map((step, index) => {
    if (index < first) return 'done';
    if (index === first || step.statuses.includes(at)) return terminal ? (status as 'failed' | 'cancelled') : 'active';
    return 'pending';
  });
}
