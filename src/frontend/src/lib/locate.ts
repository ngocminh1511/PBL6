import type { ASTNode, EvidenceItem } from './types';

/** Nodes of the hierarchy tree to open and highlight for one piece of legal evidence. */
export interface TreeFocus {
  /** Every node from the root down to the targets: these are opened. */
  path: Set<string>;
  /** The article, or the khoan the evidence cites: these are highlighted. */
  active: Set<string>;
  /** First highlighted node in tree order: the one scrolled into view. */
  first: string;
}

type Kind = 'article' | 'clause' | 'point';

// Uploaded documents carry the number only in the title ("Điều 5 ...", "5 ..."), the versioned corpus in fields.
const leadingNumber = (title: string) => title.match(/\d+[a-zđ]?/i)?.[0] ?? null;

function numberOf(node: ASTNode, kind: Kind): string | null {
  const explicit = node[`${kind}_number` as const];
  if (explicit) return String(explicit).trim();
  return node.type === kind ? leadingNumber(node.title) : null;
}

const isClause = (node: ASTNode) => numberOf(node, 'clause') !== null && numberOf(node, 'point') === null;
const isArticle = (node: ASTNode) =>
  numberOf(node, 'article') !== null && numberOf(node, 'clause') === null && numberOf(node, 'point') === null;

/** '3' -> {3}; '1-8' -> {1..8}; '1, 3' -> {1, 3}. */
function clauseNumbers(spec?: string | null): Set<string> {
  const numbers = new Set<string>();
  for (const part of (spec || '').split(/[,;]/)) {
    const range = part.trim().match(/^(\d+)\s*-\s*(\d+)$/);
    if (range) {
      const end = Math.min(Number(range[2]), Number(range[1]) + 200);
      for (let n = Number(range[1]); n <= end; n++) numbers.add(String(n));
    } else if (part.trim()) numbers.add(part.trim());
  }
  return numbers;
}

/** Finds the cited Điều (and its cited khoan) in the tree; null when the tree does not contain it. */
export function locateEvidence(tree: ASTNode, evidence: Pick<EvidenceItem, 'meta_dieu' | 'meta_khoan'>): TreeFocus | null {
  if (!evidence.meta_dieu) return null;
  const wanted = String(evidence.meta_dieu).trim();
  const clauses = clauseNumbers(evidence.meta_khoan);

  const search = (node: ASTNode, trail: string[]): TreeFocus | null => {
    const here = [...trail, node.id];
    if (isArticle(node) && numberOf(node, 'article') === wanted) {
      const path = new Set(here);
      const active: string[] = [];
      const collect = (parent: ASTNode, parents: string[]) => {
        for (const child of parent.children || []) {
          const chain = [...parents, child.id];
          if (isClause(child) && clauses.has(numberOf(child, 'clause')!)) {
            active.push(child.id);
            chain.forEach(id => path.add(id));
          } else collect(child, chain);
        }
      };
      if (clauses.size) collect(node, here);
      const targets = active.length ? active : [node.id];
      return { path, active: new Set(targets), first: targets[0] };
    }
    for (const child of node.children || []) {
      const found = search(child, here);
      if (found) return found;
    }
    return null;
  };
  return search(tree, []);
}

