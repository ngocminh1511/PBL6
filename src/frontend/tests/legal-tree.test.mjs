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
const source = readFileSync(new URL('../src/components/inspector/LegalTree.tsx', import.meta.url), 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX,
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText;
const context = { exports: {}, require, console: { ...console, error: () => {} } };
runInNewContext(output, context);
const { LegalTree } = context.exports;

const tree = { id: 'doc', type: 'document', title: 'Bộ luật Lao động', children: [
  { id: 'ch3', type: 'Chuong', title: 'Chương III HỢP ĐỒNG LAO ĐỘNG', children: [
    { id: 'm1', type: 'Muc', title: 'Mục 1 GIAO KẾT', children: [
      { id: 'd20', type: 'Dieu', article_number: '20', title: 'Loại hợp đồng lao động', children: [
        { id: 'k1', type: 'clause', article_number: '20', clause_number: '1', title: 'Hợp đồng phải được giao kết', children: [
          { id: 'pa', type: 'point', article_number: '20', clause_number: '1', point_number: 'a', title: 'Không xác định thời hạn',
            text: 'Không xác định thời hạn, trong đó hai bên không xác định thời hạn chấm dứt.' }] }] }] }] }] };

test('each level has its own marker and the cited provision is opened and highlighted', () => {
  const focus = { path: new Set(['doc', 'ch3', 'm1', 'd20']), active: new Set(['d20']), first: 'd20' };
  const doc = new JSDOM(renderToStaticMarkup(React.createElement(LegalTree, { node: tree, focus }))).window.document;
  const text = doc.body.textContent;
  assert.match(text, /Điều 20Loại hợp đồng lao động/);
  assert.match(text, /1Hợp đồng phải được giao kết/);
  assert.match(text, /a\)Không xác định thời hạn/);
  assert.ok(!text.includes('[Điều]'), 'no bracketed type labels');
  const summaries = Array.from(doc.querySelectorAll('summary'));
  const article = summaries.find(item => item.textContent.includes('Loại hợp đồng'));
  assert.match(article.className, /ring-navy/);
  assert.equal(article.closest('details').hasAttribute('open'), true);
  assert.match(summaries.find(item => item.textContent.includes('Chương III')).textContent, /1$/, 'containers show child counts');
});
