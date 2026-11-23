/**
 * Line levels the PDF parser recognises (labor_rag/ocr/structure.py PATTERNS).
 * The OCR editor only styles a line by these rules, so what looks like a Điều
 * in the editor is what the parser will split as one.
 */
export type LineLevel = 'part' | 'chapter' | 'section' | 'article' | 'clause' | 'point' | 'text';

const PATTERNS: [Exclude<LineLevel, 'text'>, RegExp][] = [
  ['part', new RegExp(String.raw`^\s*PHẦN\s+(?:(?:THỨ\s+)?(?:NHẤT|HAI|BA|BỐN|NĂM|SÁU|BẢY|TÁM|CHÍN|MƯỜI(?:\s+MỘT|\s+HAI|\s+BA|\s+BỐN|\s+LĂM)?)|[IVXLCDM]+|[0-9]+)`, 'iu')],
  ['chapter', new RegExp(String.raw`^\s*(?:CHƯƠNG|Chương)\s+(?:[IVXLCDM]+|[0-9]+)(?![\p{L}\p{N}])`, 'u')],
  ['section', new RegExp(String.raw`^\s*(?:M[ỤU]C|M[ụu]c)\s*\d+(?![\p{L}\p{N}])`, 'u')],
  ['article', new RegExp(String.raw`^\s*(?:ĐIỀU|[ĐDđd]i[eêèéềếểễệ][unp])\s+[1-9]\d*[a-zđ]?(?=[.,:\s-]|$)`, 'iu')],
  ['clause', new RegExp(String.raw`^\s*(?:[-*•]\s*)?\d+[a-zđ]?(?:\.(?!\d)\s*|[,/:)]\s+(?=[A-ZĐÀ-Ỹ]))`, 'u')],
  ['point', new RegExp(String.raw`^\s*[a-zđA-ZĐ]\)\s+`, 'u')],
];

export function lineLevel(line: string): LineLevel {
  for (const [level, pattern] of PATTERNS) if (pattern.test(line)) return level;
  return 'text';
}

/** Prefix the structure buttons insert, so the parser reads the line at that level. */
export const LEVEL_PREFIX: Record<'chapter' | 'section' | 'article' | 'clause' | 'point', string> = {
  chapter: 'Chương ', section: 'Mục ', article: 'Điều ', clause: '1. ', point: 'a) ',
};

type ParagraphJSON = { type: 'paragraph'; content?: { type: 'text'; text: string }[] };

/** Plain page text -> editor document: one paragraph per line, empty lines kept. */
export function textToDoc(text: string): { type: 'doc'; content: ParagraphJSON[] } {
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  return {
    type: 'doc',
    content: lines.map((line) => (line ? { type: 'paragraph', content: [{ type: 'text', text: line }] } : { type: 'paragraph' })),
  };
}

/** Every match of `term` as [from, to) offsets inside one line; case-insensitive. */
export function findInLine(line: string, term: string): [number, number][] {
  if (!term) return [];
  const hay = line.toLocaleLowerCase('vi');
  const needle = term.toLocaleLowerCase('vi');
  const found: [number, number][] = [];
  for (let at = hay.indexOf(needle); at !== -1; at = hay.indexOf(needle, at + needle.length)) {
    found.push([at, at + needle.length]);
  }
  return found;
}
