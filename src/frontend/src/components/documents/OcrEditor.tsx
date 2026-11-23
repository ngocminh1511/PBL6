'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { EditorContent, Extension, useEditor, type Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import { ChevronDown, ChevronUp, ListTree, Merge, Redo2, RemoveFormatting, Replace, TextSearch, Undo2, X } from 'lucide-react';
import { LEVEL_PREFIX, findInLine, lineLevel, stripLevelPrefix, textToDoc, type LineLevel } from '../../lib/ocrStructure';

const LEVEL_LABEL: Record<Exclude<LineLevel, 'text'>, string> = {
  part: 'Phần', chapter: 'Chương', section: 'Mục', article: 'Điều', clause: 'Khoản', point: 'Điểm',
};

const searchKey = new PluginKey<string>('ocrSearch');

/** Styles each line by the level the parser will read it at, and highlights search matches. */
const StructureHighlight = Extension.create({
  name: 'ocrStructure',
  addProseMirrorPlugins() {
    return [
      new Plugin<string>({
        key: searchKey,
        state: {
          init: () => '',
          apply: (tr, value) => (tr.getMeta(searchKey) as string | undefined) ?? value,
        },
        props: {
          decorations(state) {
            const term = searchKey.getState(state) || '';
            const decorations: Decoration[] = [];
            state.doc.forEach((node, offset) => {
              const text = node.textContent;
              const level = lineLevel(text);
              if (level !== 'text') {
                decorations.push(Decoration.node(offset, offset + node.nodeSize, {
                  class: `ocr-line ocr-${level}`, 'data-level': LEVEL_LABEL[level],
                }));
              }
              for (const [from, to] of findInLine(text, term)) {
                decorations.push(Decoration.inline(offset + 1 + from, offset + 1 + to, { class: 'ocr-match' }));
              }
            });
            return DecorationSet.create(state.doc, decorations);
          },
        },
      }),
    ];
  },
});

/** [from, to) document positions of every match, in document order. */
function matches(editor: Editor, term: string): [number, number][] {
  const found: [number, number][] = [];
  editor.state.doc.forEach((node, offset) => {
    for (const [from, to] of findInLine(node.textContent, term)) found.push([offset + 1 + from, offset + 1 + to]);
  });
  return found;
}

const editorText = (editor: Editor) => editor.getText({ blockSeparator: '\n' });

interface OcrEditorProps {
  value: string;
  editable: boolean;
  onChange?: (text: string) => void;
  onSave?: () => void;
}

/**
 * A small word-processor for one OCR page. The page stays plain text (one
 * paragraph per line), because that is what the parser reads; the toolbar
 * edits structure markers ("Điều 5.", "1.", "a)") instead of fonts.
 */
export const OcrEditor: React.FC<OcrEditorProps> = ({ value, editable, onChange, onSave }) => {
  const [showFind, setShowFind] = useState(false);
  const [term, setTerm] = useState('');
  const [replacement, setReplacement] = useState('');
  const [notice, setNotice] = useState('');
  const [showOutline, setShowOutline] = useState(false);
  // Level of the line holding the cursor, so the toolbar shows how the parser reads it.
  const [cursorLevel, setCursorLevel] = useState<LineLevel>('text');
  // The editor keeps its first props; read the latest callbacks through refs.
  const handlers = useRef({ onChange, onSave });
  handlers.current = { onChange, onSave };

  const editor = useEditor({
    immediatelyRender: false,
    editable,
    extensions: [
      StarterKit.configure({
        heading: false, bulletList: false, orderedList: false, listItem: false, blockquote: false,
        codeBlock: false, code: false, bold: false, italic: false, strike: false,
        horizontalRule: false, hardBreak: false,
      }),
      StructureHighlight,
    ],
    content: textToDoc(value),
    editorProps: {
      attributes: { class: 'ocr-editor-content', spellcheck: 'false', 'aria-label': 'Nội dung trang OCR' },
      handleKeyDown: (_view, event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
          event.preventDefault();
          handlers.current.onSave?.();
          return true;
        }
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
          event.preventDefault();
          setShowFind(true);
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor: current }) => {
      handlers.current.onChange?.(editorText(current));
      setCursorLevel(lineLevel(current.state.selection.$from.parent.textContent));
    },
    onSelectionUpdate: ({ editor: current }) => setCursorLevel(lineLevel(current.state.selection.$from.parent.textContent)),
  });

  useEffect(() => { editor?.setEditable(editable); }, [editor, editable]);

  // Push the search term into the highlight plugin.
  useEffect(() => {
    if (!editor) return;
    editor.view.dispatch(editor.state.tr.setMeta(searchKey, showFind ? term : ''));
  }, [editor, term, showFind]);

  const counts = useMemo(() => {
    const result = { article: 0, clause: 0, point: 0 };
    for (const line of value.split('\n')) {
      const level = lineLevel(line);
      if (level === 'article' || level === 'clause' || level === 'point') result[level] += 1;
    }
    return result;
  }, [value]);

  // Chapters, sections and articles on the page, by line index, for the jump list.
  const outline = useMemo(() => value.split('\n').flatMap((line, index) => {
    const level = lineLevel(line);
    return level === 'part' || level === 'chapter' || level === 'section' || level === 'article'
      ? [{ index, text: line.trim() }] : [];
  }), [value]);

  if (!editor) return <div className="h-full flex items-center justify-center text-xs text-ink-3">Đang mở trình soạn thảo…</div>;

  const markLine = (level: keyof typeof LEVEL_PREFIX) => {
    const { $from } = editor.state.selection;
    const line = $from.parent.textContent;
    if (lineLevel(line) === level) return;
    editor.chain().focus().insertContentAt($from.start(), LEVEL_PREFIX[level]).run();
  };

  const joinNextLine = () => {
    const { state } = editor;
    const { $from } = state.selection;
    const end = $from.end();
    if (end + 1 >= state.doc.content.size) return;
    const needsSpace = !/\s$/.test($from.parent.textContent) && $from.parent.textContent.length > 0;
    const tr = state.tr;
    if (needsSpace) tr.insertText(' ', end);
    const at = end + (needsSpace ? 1 : 0);
    tr.delete(at, at + 2);
    editor.view.dispatch(tr);
    editor.commands.focus();
  };

  const findNext = () => {
    const found = matches(editor, term);
    if (!found.length) { setNotice('Không tìm thấy.'); return; }
    const head = editor.state.selection.to;
    const [from, to] = found.find(([start]) => start >= head) ?? found[0];
    editor.chain().focus().setTextSelection({ from, to }).scrollIntoView().run();
    setNotice(`${found.length} kết quả`);
  };

  const replaceCurrent = () => {
    const { from, to } = editor.state.selection;
    const selected = editor.state.doc.textBetween(from, to);
    if (!term || selected.toLocaleLowerCase('vi') !== term.toLocaleLowerCase('vi')) { findNext(); return; }
    editor.chain().focus().insertContentAt({ from, to }, replacement).run();
    findNext();
  };

  const replaceAll = () => {
    const found = matches(editor, term);
    if (!found.length) { setNotice('Không tìm thấy.'); return; }
    const tr = editor.state.tr;
    for (const [from, to] of [...found].reverse()) {
      if (replacement) tr.insertText(replacement, from, to); else tr.delete(from, to);
    }
    editor.view.dispatch(tr);
    setNotice(`Đã thay ${found.length} chỗ.`);
  };

  const unmarkLine = () => {
    const { $from } = editor.state.selection;
    const line = $from.parent.textContent;
    const stripped = stripLevelPrefix(line);
    if (stripped === line) return;
    editor.chain().focus().insertContentAt({ from: $from.start(), to: $from.end() }, stripped).run();
  };

  /** Put the cursor at the start of line `index` and scroll it into view. */
  const jumpToLine = (index: number) => {
    let target = -1;
    editor.state.doc.forEach((_node, offset, i) => { if (i === index) target = offset + 1; });
    if (target >= 0) editor.chain().focus().setTextSelection(target).scrollIntoView().run();
  };

  const group = 'flex items-center gap-0.5 p-0.5 rounded-lg bg-surface-container-lowest border border-outline-variant/30';
  const tool = 'h-7 min-w-7 px-1.5 rounded-md flex items-center justify-center gap-1 text-[11.5px] font-semibold text-ink hover:bg-surface-container disabled:opacity-40 disabled:cursor-not-allowed transition-colors';
  const active = 'bg-secondary/10 text-secondary';

  return (
    <div className="h-full flex flex-col min-h-0">
      {editable && (
        <div className="flex flex-wrap items-center gap-1.5 px-2 py-1.5 border-b border-outline-variant/25 bg-surface-container-low" role="toolbar" aria-label="Công cụ soạn thảo">
          <div className={group}>
            <button type="button" className={tool} title="Hoàn tác (Ctrl+Z)" aria-label="Hoàn tác" onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()}>
              <Undo2 size={15} />
            </button>
            <button type="button" className={tool} title="Làm lại (Ctrl+Y)" aria-label="Làm lại" onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()}>
              <Redo2 size={15} />
            </button>
          </div>

          <div className={group} role="group" aria-label="Cấu trúc dòng">
            {(['chapter', 'section', 'article', 'clause', 'point'] as const).map((level) => (
              <button key={level} type="button" className={`${tool} ${cursorLevel === level ? active : ''}`} onClick={() => markLine(level)}
                aria-pressed={cursorLevel === level}
                title={cursorLevel === level ? `Dòng này đang được đọc là ${LEVEL_LABEL[level]}`
                  : `Thêm "${LEVEL_PREFIX[level].trim()}" vào đầu dòng để hệ thống tách thành ${LEVEL_LABEL[level]}`}>
                {LEVEL_LABEL[level]}
              </button>
            ))}
            <button type="button" className={tool} onClick={unmarkLine} disabled={cursorLevel === 'text'}
              title="Bỏ ký hiệu cấu trúc ở đầu dòng, để dòng được đọc là văn bản thường" aria-label="Bỏ đánh dấu dòng">
              <RemoveFormatting size={15} />
            </button>
          </div>

          <div className={group}>
            <button type="button" className={tool} title="Nối dòng hiện tại với dòng dưới (sửa câu bị ngắt dòng)" onClick={joinNextLine}>
              <Merge size={15} />
              <span>Nối dòng</span>
            </button>
            <button type="button" className={`${tool} ${showFind ? active : ''}`} title="Tìm & thay thế (Ctrl+F)" aria-pressed={showFind} onClick={() => setShowFind((v) => !v)}>
              <Replace size={15} />
              <span>Tìm & thay</span>
            </button>
          </div>
        </div>
      )}

      {editable && showFind && (
        <div className="flex flex-wrap items-center gap-1.5 px-2 py-1.5 border-b border-outline-variant/25 bg-surface-container-lowest text-[11.5px]">
          <div className="flex items-center gap-1 px-1.5 rounded-md border border-outline-variant/40 bg-white focus-within:border-secondary">
            <TextSearch size={14} className="text-ink-3" />
            <input value={term} onChange={(e) => { setTerm(e.target.value); setNotice(''); }} placeholder="Tìm…" aria-label="Từ cần tìm" autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); findNext(); } if (e.key === 'Escape') setShowFind(false); }}
              className="w-28 py-1 bg-transparent focus:outline-none" />
          </div>
          <input value={replacement} onChange={(e) => setReplacement(e.target.value)} placeholder="Thay bằng…" aria-label="Thay bằng"
            className="w-32 px-1.5 py-1 rounded-md border border-outline-variant/40 bg-white focus:outline-none focus:border-secondary" />
          <div className={group}>
            <button type="button" className={tool} onClick={findNext} disabled={!term}>Tìm tiếp</button>
            <button type="button" className={tool} onClick={replaceCurrent} disabled={!term}>Thay</button>
            <button type="button" className={tool} onClick={replaceAll} disabled={!term}>Thay tất cả</button>
          </div>
          {notice && <span className="text-ink-3">{notice}</span>}
          <button type="button" className={`${tool} ml-auto`} onClick={() => setShowFind(false)} aria-label="Đóng tìm kiếm"><X size={14} /></button>
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto bg-slate-100 p-3">
        <div className="ocr-editor mx-auto max-w-[720px] bg-white shadow-sm rounded px-8 py-6">
          <EditorContent editor={editor} />
        </div>
      </div>

      <div className="border-t border-outline-variant/25 bg-surface-container-low text-[11.5px] text-ink-3">
        {showOutline && outline.length > 0 && (
          <ul className="max-h-28 overflow-y-auto legal-scroll px-2 py-1 border-b border-outline-variant/20" aria-label="Các Điều trên trang">
            {outline.map(({ index, text }) => (
              <li key={index}>
                <button type="button" onClick={() => jumpToLine(index)}
                  className="w-full text-left truncate px-1.5 py-0.5 rounded hover:bg-surface-container text-ink">{text}</button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-center justify-between gap-2 px-2 py-1">
          <button type="button" onClick={() => setShowOutline((v) => !v)} disabled={!outline.length}
            className="flex items-center gap-1 hover:text-ink disabled:hover:text-ink-3 disabled:cursor-default" aria-expanded={showOutline}>
            <ListTree size={14} />
            <span>{counts.article} Điều · {counts.clause} Khoản · {counts.point} Điểm nhận diện trên trang</span>
            {outline.length > 0 && (showOutline ? <ChevronDown size={14} /> : <ChevronUp size={14} />)}
          </button>
          {editable && <span>Ctrl+S lưu · Ctrl+F tìm</span>}
        </div>
      </div>
    </div>
  );
};
