import type { ASTNode } from './types';

/** Levels of the document tree as the Phap dien and PDF builders name them. */
export type OutlineLevel = 'document' | 'part' | 'chapter' | 'section' | 'article' | 'clause' | 'point' | 'other';

const LEVELS: Record<string, OutlineLevel> = {
  document: 'document', DeMuc: 'document', part: 'part', Phan: 'part',
  chapter: 'chapter', Chuong: 'chapter', section: 'section', Muc: 'section',
  article: 'article', Dieu: 'article', clause: 'clause', point: 'point',
};

/** Lower case without diacritics, for searching Vietnamese titles. */
export const foldText = (value: string) =>
  value.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();

export function levelOf(node: ASTNode): OutlineLevel {
  if (node.point_number) return 'point';
  if (node.clause_number) return 'clause';
  if (node.article_number || node.type === 'Dieu' || node.type === 'article') return 'article';
  return LEVELS[node.type] ?? 'other';
}

const strip = (value: string | null | undefined, word: string) =>
  String(value ?? '').replace(new RegExp('^' + word + '\\s*', 'i'), '').trim();

/** "Điều 5" from article_number "5" or "Điều 5". */
export const articleLabel = (node: ASTNode) => {
  const number = strip(node.article_number, 'Điều');
  return number ? `Điều ${number}` : 'Điều';
};

/** Phap dien article titles end with "(45/2019/QH14)"; the outline shows that as a group instead. */
export function articleTitle(node: ASTNode) {
  const source = node.document_number;
  const title = (node.title || '').trim();
  return source && title.endsWith(`(${source})`) ? title.slice(0, -source.length - 2).trim() : title;
}

export type DocumentCounts = { chuong: number; muc: number; dieu: number; khoan: number; diem: number };

export function countLevels(root: ASTNode | null | undefined): DocumentCounts {
  const counts: DocumentCounts = { chuong: 0, muc: 0, dieu: 0, khoan: 0, diem: 0 };
  const walk = (node: ASTNode) => {
    const level = levelOf(node);
    if (level === 'chapter') counts.chuong++;
    else if (level === 'section') counts.muc++;
    else if (level === 'article') counts.dieu++;
    else if (level === 'clause') counts.khoan++;
    else if (level === 'point') counts.diem++;
    node.children?.forEach(walk);
  };
  if (root) walk(root);
  return counts;
}

/** Every article in reading order. */
export function articlesOf(root: ASTNode | null | undefined): ASTNode[] {
  const found: ASTNode[] = [];
  const walk = (node: ASTNode) => {
    if (levelOf(node) === 'article') { found.push(node); return; }
    node.children?.forEach(walk);
  };
  if (root) walk(root);
  return found;
}

/** Path of container ids (part/chapter/section) down to an article. */
export function pathTo(root: ASTNode | null | undefined, id: string): string[] {
  const search = (node: ASTNode, trail: string[]): string[] | null => {
    if (node.id === id) return trail;
    for (const child of node.children ?? []) {
      const found = search(child, levelOf(node) === 'document' ? trail : [...trail, node.id]);
      if (found) return found;
    }
    return null;
  };
  return root ? search(root, []) ?? [] : [];
}

/** Children of a container: sub-containers, and articles grouped by source document (Phap dien mixes several). */
export type OutlineItem =
  | { kind: 'container'; node: ASTNode }
  | { kind: 'group'; source: string | null; articles: ASTNode[] };

export function outlineItems(node: ASTNode): OutlineItem[] {
  const items: OutlineItem[] = [];
  for (const child of node.children ?? []) {
    const level = levelOf(child);
    if (level === 'article') {
      const source = child.document_number ?? null;
      const last = items[items.length - 1];
      if (last?.kind === 'group' && last.source === source) last.articles.push(child);
      else items.push({ kind: 'group', source, articles: [child] });
    } else if (level !== 'clause' && level !== 'point') {
      items.push({ kind: 'container', node: child });
    }
  }
  return items;
}

export type ArticleLine = { kind: 'text' | 'clause' | 'point'; label?: string; text: string };

const CLAUSE_RE = /^(\d+[a-zđ]?)\.\s+/i;
const POINT_RE = /^([a-zđ]{1,2})\)\s+/i;

function classify(line: string): ArticleLine {
  const clause = line.match(CLAUSE_RE);
  if (clause) return { kind: 'clause', label: `${clause[1]}.`, text: line.slice(clause[0].length) };
  const point = line.match(POINT_RE);
  if (point) return { kind: 'point', label: `${point[1]})`, text: line.slice(point[0].length) };
  return { kind: 'text', text: line };
}

const lines = (text: string) => text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
/** First line of a node's text, enough to tell whether the article text already holds it. */
const head = (text?: string) => (lines(text ?? '')[0] ?? '').replace(/\s+/g, ' ').slice(0, 40);

/**
 * The body of an article as clause and point lines. Phap dien stores the full
 * text on the article and repeats it in the clauses; PDF articles keep an
 * introduction and put the clauses in children. Clauses already in the text
 * are not repeated.
 */
export function articleLines(article: ASTNode): ArticleLine[] {
  const text = article.text ?? '';
  const flat = text.replace(/\s+/g, ' ');
  const children = (article.children ?? []).filter((child) => !flat.includes(head(child.text)) || !head(child.text));
  const out = lines(text).map(classify);
  const add = (node: ASTNode) => {
    const level = levelOf(node);
    const label = level === 'clause' ? `${strip(node.clause_number, 'Khoản')}.`
      : level === 'point' ? `${strip(node.point_number, 'Điểm')})` : undefined;
    lines(node.text ?? '').forEach((line, index) => {
      const parsed = classify(line);
      out.push(index === 0 && label && parsed.kind === 'text'
        ? { kind: level === 'point' ? 'point' : 'clause', label, text: line }
        : parsed);
    });
    node.children?.forEach(add);
  };
  children.forEach(add);
  return out;
}
