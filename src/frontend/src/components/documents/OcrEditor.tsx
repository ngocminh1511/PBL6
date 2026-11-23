'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { EditorContent, Extension, useEditor, type Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import { LEVEL_PREFIX, findInLine, lineLevel, textToDoc, type LineLevel } from '../../lib/ocrStructure';

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
    onUpdate: ({ editor: current }) => handlers.current.onChange?.(editorText(current)),
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

  if (!editor) return <div className="h-full flex items-center justify-center text-xs text-on-surface-variant">Đang mở trình soạn thảo…</div>;

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

  const tool = 'h-7 min-w-7 px-1.5 rounded flex items-center justify-center gap-1 text-[11px] font-semibold text-on-surface hover:bg-surface-container disabled:opacity-40 disabled:cursor-not-allowed';

  return (
    <div className="h-full flex flex-col min-h-0">
      {editable && (
        <div className="flex flex-wrap items-center gap-0.5 px-2 py-1 border-b border-outline-variant/25 bg-surface-container-low" role="toolbar" aria-label="Công cụ soạn thảo">
          <button type="button" className={tool} title="Hoàn tác (Ctrl+Z)" onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()}>
            <span className="material-symbols-outlined text-[16px]">undo</span>
          </button>
          <button type="button" className={tool} title="Làm lại (Ctrl+Y)" onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()}>
            <span className="material-symbols-outlined text-[16px]">redo</span>
          </button>
          <span className="w-px h-5 bg-outline-variant/40 mx-1" />
          <span className="text-[10px] text-on-surface-variant mr-0.5">Đánh dấu dòng:</span>
          {(['chapter', 'section', 'article', 'clause', 'point'] as const).map((level) => (
            <button key={level} type="button" className={tool} onClick={() => markLine(level)}
              title={`Thêm "${LEVEL_PREFIX[level].trim()}" vào đầu dòng để hệ thống tách thành ${LEVEL_LABEL[level]}`}>
              {LEVEL_LABEL[level]}
            </button>
          ))}
          <span className="w-px h-5 bg-outline-variant/40 mx-1" />
          <button type="button" className={tool} title="Nối dòng hiện tại với dòng dưới (sửa câu bị ngắt dòng)" onClick={joinNextLine}>
            <span className="material-symbols-outlined text-[16px]">vertical_align_center</span>
            <span>Nối dòng</span>
          </button>
          <button type="button" className={`${tool} ${showFind ? 'bg-secondary/10 text-secondary' : ''}`} title="Tìm & thay thế (Ctrl+F)" onClick={() => setShowFind((v) => !v)}>
            <span className="material-symbols-outlined text-[16px]">find_replace</span>
            <span>Tìm & thay</span>
          </button>
        </div>
      )}

      {editable && showFind && (
        <div className="flex flex-wrap items-center gap-1.5 px-2 py-1.5 border-b border-outline-variant/25 bg-surface-container-lowest text-[11px]">
          <input value={term} onChange={(e) => { setTerm(e.target.value); setNotice(''); }} placeholder="Tìm…" aria-label="Từ cần tìm"
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); findNext(); } }}
            className="w-32 px-1.5 py-0.5 rounded border border-outline-variant/40 bg-white focus:outline-none focus:border-secondary" />
          <input value={replacement} onChange={(e) => setReplacement(e.target.value)} placeholder="Thay bằng…" aria-label="Thay bằng"
            className="w-32 px-1.5 py-0.5 rounded border border-outline-variant/40 bg-white focus:outline-none focus:border-secondary" />
          <button type="button" className={tool} onClick={findNext} disabled={!term}>Tìm tiếp</button>
          <button type="button" className={tool} onClick={replaceCurrent} disabled={!term}>Thay</button>
          <button type="button" className={tool} onClick={replaceAll} disabled={!term}>Thay tất cả</button>
          {notice && <span className="text-on-surface-variant">{notice}</span>}
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto bg-slate-100 p-3">
        <div className="ocr-editor mx-auto max-w-[720px] bg-white shadow-sm rounded px-8 py-6">
          <EditorContent editor={editor} />
        </div>
      </div>

      <div className="flex items-center justify-between gap-2 px-2 py-1 border-t border-outline-variant/25 bg-surface-container-low text-[10px] text-on-surface-variant">
        <span>{counts.article} Điều · {counts.clause} Khoản · {counts.point} Điểm nhận diện trên trang</span>
        {editable && <span>Ctrl+S lưu · Ctrl+F tìm</span>}
      </div>
    </div>
  );
};
