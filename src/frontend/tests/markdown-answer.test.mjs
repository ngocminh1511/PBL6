import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { JSDOM } from 'jsdom';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ts from 'typescript';

const require = createRequire(import.meta.url);
function compile(path, overrides = {}) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText;
  const context = { exports: {}, require: name => overrides[name] || require(name), console };
  runInNewContext(output, context);
  return context.exports;
}
const citationLinks = compile('../src/lib/citationLinks.ts');
const { linkCitations } = citationLinks;
const { MarkdownAnswer } = compile('../src/components/chat/MarkdownAnswer.tsx', { '../../lib/citationLinks': citationLinks });

const render = (content, props = {}) => renderToStaticMarkup(React.createElement(MarkdownAnswer, { content, ...props }));
const ev = (citation, meta_dieu, extra = {}) => ({ chunk_id: citation, ten: '', text: '', source: '', score: 0,
  amendments: [], citation, meta_dieu, document_id: citation.split(' số ')[1], ...extra });
const evidences = [
  ev('Điều 35 Bộ luật số 45/2019/QH14', '35', { meta_khoan: '1' }),
  ev('Điều 36 Bộ luật số 45/2019/QH14', '36', { meta_khoan: '2' }),
  ev('Điều 7 Nghị định số 145/2020/NĐ-CP', '7', { meta_khoan: '2' }),
];

test('answer Markdown renders as formatted elements, not literal markers', () => {
  const html = render([
    'Thời hạn báo trước phụ thuộc vào bên chấm dứt:',
    '',
    '1. **Người lao động chấm dứt:**',
    '   - Báo trước **ít nhất 45 ngày**.',
    '',
    '> Căn cứ: *Điểm a Khoản 1 Điều 35 Bộ luật số 45/2019/QH14.*',
  ].join('\n'));
  assert.match(html, /<ol[^>]*>/);
  assert.match(html, /<ul[^>]*>/);
  assert.match(html, /<strong[^>]*>ít nhất 45 ngày<\/strong>/);
  assert.match(html, /<blockquote[^>]*>[\s\S]*<em[^>]*>Điểm a Khoản 1 Điều 35/);
  assert.doesNotMatch(html, /\*\*/);
});

test('raw HTML in an answer is escaped, not rendered', () => {
  const html = render('Xem <script>alert(1)</script> <b>x</b>');
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(html, /<b>x<\/b>/);
});

test('tables from remark-gfm render', () => {
  const html = render('| Bên | Thời hạn |\n|---|---|\n| NLĐ | 45 ngày |');
  assert.match(html, /<table[^>]*>/);
  assert.match(html, /<td[^>]*>45 ngày<\/td>/);
});

test('bracketed and inline citations of retrieved evidence become links', () => {
  assert.equal(linkCitations('Căn cứ: [Điều 35 Bộ luật số 45/2019/QH14] khoản 1, điểm a', evidences),
    'Căn cứ: [Điều 35 Bộ luật số 45/2019/QH14](#evidence-0) khoản 1, điểm a');
  assert.equal(linkCitations('Căn cứ: Điểm a Khoản 2 Điều 7 Nghị định số 145/2020/NĐ-CP.', evidences),
    'Căn cứ: Điểm a Khoản 2 [Điều 7 Nghị định số 145/2020/NĐ-CP](#evidence-2).');
});

test('citations that match no retrieved evidence stay plain text', () => {
  const text = 'Theo Điều 99 Bộ luật số 45/2019/QH14 và Điều 35 Nghị định số 1/2021/NĐ-CP.';
  assert.equal(linkCitations(text, evidences), text);
  assert.equal(linkCitations(text, []), text);
});

test('a clause named in the answer picks the matching chunk of the same Điều', () => {
  const split = [ev('Điều 35 Bộ luật số 45/2019/QH14', '35', { meta_khoan: '1', chunk_id: 'a' }),
    ev('Điều 35 Bộ luật số 45/2019/QH14', '35', { meta_khoan: '2', chunk_id: 'b' })];
  assert.match(linkCitations('Khoản 2 Điều 35 Bộ luật số 45/2019/QH14', split), /#evidence-1/);
});

test('a linked citation renders as a button without its brackets', () => {
  const dom = new JSDOM('<div id="root"></div>');
  const html = render('Căn cứ: [Điều 36 Bộ luật số 45/2019/QH14] khoản 2', { evidences, onCite: () => {} });
  dom.window.document.getElementById('root').innerHTML = html;
  const button = dom.window.document.querySelector('button');
  assert.ok(button, 'citation renders as a button');
  assert.equal(button.textContent, 'Điều 36 Bộ luật số 45/2019/QH14');
  assert.doesNotMatch(html, /\[Điều 36/);
});
