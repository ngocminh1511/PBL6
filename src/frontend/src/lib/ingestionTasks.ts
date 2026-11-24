import type { OcrRevision, TaskState } from './types';

export const TASK_STATES: Record<TaskState, { label: string; tone: string }> = {
  running: { label: 'Đang xử lý', tone: 'bg-secondary/10 text-secondary' },
  awaiting_review: { label: 'Chờ rà soát', tone: 'bg-indigo-100 text-indigo-900' },
  indexed: { label: 'Đã lập chỉ mục', tone: 'bg-emerald-100 text-emerald-800' },
  editing: { label: 'Đang sửa', tone: 'bg-amber-100 text-amber-900' },
  removed: { label: 'Đã gỡ khỏi kho', tone: 'bg-slate-200 text-slate-700' },
  failed: { label: 'Lỗi', tone: 'bg-red-100 text-red-800' },
  cancelled: { label: 'Đã hủy', tone: 'bg-slate-100 text-slate-600' },
};

/** The revision to show first: the draft being edited, else the one in the corpus, else the latest. */
export function defaultRevision(revisions: OcrRevision[]): OcrRevision | null {
  return revisions.find((r) => r.status === 'draft')
    ?? revisions.find((r) => r.status === 'indexed')
    ?? revisions[revisions.length - 1]
    ?? null;
}

export function revisionLabel(revision: OcrRevision): string {
  return revision.kind === 'ocr' ? 'OCR gốc' : `Rà soát ${revision.number - 1}`;
}

export function revisionStatusLabel(revision: OcrRevision): string {
  if (revision.kind === 'ocr') return 'chỉ đọc';
  return revision.status === 'draft' ? 'nháp' : revision.status === 'indexed' ? 'đang dùng' : 'cũ';
}

/** Only a draft review can be edited; the OCR output and indexed/locked reviews are kept as they are. */
export const isEditable = (revision: OcrRevision | null) => !!revision && revision.kind === 'review' && revision.status === 'draft';
