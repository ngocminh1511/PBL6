export type DiffPart = { kind: 'same' | 'added' | 'removed'; text: string };

/** Words with the whitespace that follows them, so joining the parts restores the text. */
const tokens = (text: string) => text.match(/\S+\s*|\s+/g) ?? [];

const MAX_CELLS = 4_000_000;

/**
 * Word-level diff of an old and a new text (longest common subsequence).
 * Texts too long to compare word by word come back as one removal and one addition.
 */
export function diffWords(before: string, after: string): DiffPart[] {
  const a = tokens(before);
  const b = tokens(after);
  if (a.length * b.length > MAX_CELLS) {
    return [
      ...(before ? [{ kind: 'removed' as const, text: before }] : []),
      ...(after ? [{ kind: 'added' as const, text: after }] : []),
    ];
  }
  const width = b.length + 1;
  const lcs = new Uint32Array((a.length + 1) * width);
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i * width + j] = a[i].trim() === b[j].trim()
        ? lcs[(i + 1) * width + j + 1] + 1
        : Math.max(lcs[(i + 1) * width + j], lcs[i * width + j + 1]);
    }
  }
  const parts: DiffPart[] = [];
  const push = (kind: DiffPart['kind'], text: string) => {
    const last = parts[parts.length - 1];
    if (last && last.kind === kind) last.text += text; else parts.push({ kind, text });
  };
  let i = 0, j = 0;
  while (i < a.length && j < b.length) {
    if (a[i].trim() === b[j].trim()) { push('same', b[j]); i++; j++; }
    else if (lcs[(i + 1) * width + j] >= lcs[i * width + j + 1]) push('removed', a[i++]);
    else push('added', b[j++]);
  }
  while (i < a.length) push('removed', a[i++]);
  while (j < b.length) push('added', b[j++]);
  return parts;
}
