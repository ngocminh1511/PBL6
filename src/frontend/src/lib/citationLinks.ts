import type { EvidenceItem } from './types';

/** Href prefix of an answer citation that opens retrieved evidence: `#evidence-<index>`. */
export const EVIDENCE_HREF = '#evidence-';

// Same rules as labor_rag/generation/citation_verify.py: "Điều N", then the
// document number named before the next "Điều" within 120 characters.
// The project targets ES5, so letters are listed instead of \p{L}.
const CITE_RE = /Điều\s+(\d+[a-zđ]?)(?![A-Za-zÀ-ỹĐđ0-9.])/g;
const SO_HIEU_RE = /\d+\/\d{4}\/[A-Za-zÀ-ỹĐđ0-9_-]+/;
const SO_HIEU_WINDOW = 120;
// Clause named around the citation: "Khoản 1 Điều 35" or "Điều 35 ... khoản 1".
const KHOAN_BEFORE_RE = /khoản\s+(\d+)[^.\n]{0,20}$/i;
const KHOAN_AFTER_RE = /^[^.\n]{0,60}?khoản\s+(\d+)/i;

function clauses(spec?: string): Set<string> {
  const numbers = new Set<string>();
  for (const part of (spec || '').split(/[,;]/)) {
    const range = part.trim().match(/^(\d+)\s*-\s*(\d+)$/);
    if (range) for (let n = Number(range[1]); n <= Math.min(Number(range[2]), Number(range[1]) + 200); n++) numbers.add(String(n));
    else if (part.trim()) numbers.add(part.trim());
  }
  return numbers;
}

function find(evidences: EvidenceItem[], dieu: string, soHieu: string | null, khoan: string | null): number {
  const candidates = evidences
    .map((ev, index) => ({ ev, index }))
    .filter(({ ev }) => ev.meta_dieu && String(ev.meta_dieu).trim() === dieu && !ev.appendix_id)
    .filter(({ ev }) => !soHieu || ev.citation.includes(soHieu) || ev.document_number === soHieu);
  if (!candidates.length) return -1;
  // Without a document number the Điều must name one document only.
  if (!soHieu && new Set(candidates.map(({ ev }) => ev.document_id || ev.citation)).size > 1) return -1;
  const byClause = khoan ? candidates.find(({ ev }) => clauses(ev.meta_khoan).has(khoan)) : undefined;
  return (byClause ?? candidates[0]).index;
}

/**
 * Turns each "Điều N <số hiệu>" in the answer that names retrieved evidence into a
 * Markdown link `[Điều N <số hiệu>](#evidence-i)`. Citations that match no evidence stay text.
 */
export function linkCitations(content: string, evidences: EvidenceItem[] | undefined): string {
  if (!content || !evidences?.length) return content;
  let out = '';
  let last = 0;
  CITE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CITE_RE.exec(content))) {
    const start = match.index;
    if (start < last) continue;
    let end = start + match[0].length;
    const tail = content.slice(end, end + SO_HIEU_WINDOW).split('Điều', 1)[0];
    const soHieu = tail.match(SO_HIEU_RE);
    if (soHieu) end += soHieu.index! + soHieu[0].length;
    const khoan = content.slice(Math.max(0, start - 40), start).match(KHOAN_BEFORE_RE)?.[1]
      ?? content.slice(end).match(KHOAN_AFTER_RE)?.[1] ?? null;
    const index = find(evidences, match[1], soHieu?.[0] ?? null, khoan);
    if (index < 0) continue;
    // "[Điều 35 Bộ luật số 45/2019/QH14]" written by the model: the link replaces the brackets.
    let from = start;
    if (content[start - 1] === '[' && content[end] === ']') { from = start - 1; end += 1; }
    const label = content.slice(start, from === start ? end : end - 1).replace(/[[\]]/g, '');
    out += content.slice(last, from) + `[${label}](${EVIDENCE_HREF}${index})`;
    last = end;
  }
  return out + content.slice(last);
}
