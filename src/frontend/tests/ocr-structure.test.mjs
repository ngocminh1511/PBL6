import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/ocrStructure.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const context = { exports: {} };
runInNewContext(output, context);
const { lineLevel, textToDoc, findInLine } = context.exports;

test('lines are styled at the level the PDF parser reads them', () => {
  assert.equal(lineLevel('Chương I NHỮNG QUY ĐỊNH CHUNG'), 'chapter');
  assert.equal(lineLevel('CHƯƠNG 2'), 'chapter');
  assert.equal(lineLevel('Mục 3. HỢP ĐỒNG'), 'section');
  assert.equal(lineLevel('Muc4 Tiền lương'), 'section');
  assert.equal(lineLevel('Điều 35a. Quyền đơn phương'), 'article');
  assert.equal(lineLevel('Điêu 16. Chuẩn cơ sở'), 'article'); // OCR tone-mark slip
  assert.equal(lineLevel('1. Người lao động có quyền'), 'clause');
  assert.equal(lineLevel('2, Người sử dụng lao động'), 'clause');
  assert.equal(lineLevel('a) Được trả lương'), 'point');
  assert.equal(lineLevel('PHẦN THỨ NHẤT'), 'part');
  assert.equal(lineLevel('Theo quy định tại Điều 5'), 'text');
  assert.equal(lineLevel('1.5 triệu đồng'), 'text');
  assert.equal(lineLevel('Chương trình đào tạo'), 'text');
});

test('page text round-trips one paragraph per line, empty lines kept', () => {
  const doc = textToDoc('Điều 1.\r\n\n1. Nội dung');
  assert.equal(doc.content.length, 3);
  assert.equal(doc.content[0].content[0].text, 'Điều 1.');
  assert.equal(doc.content[1].content, undefined);
  assert.equal(doc.content[2].content[0].text, '1. Nội dung');
});

test('search finds every case-insensitive match in a line', () => {
  assert.deepEqual(JSON.parse(JSON.stringify(findInLine('Lao động và LAO ĐỘNG', 'lao động'))), [[0, 8], [12, 20]]);
  assert.deepEqual(JSON.parse(JSON.stringify(findInLine('abc', ''))), []);
});
