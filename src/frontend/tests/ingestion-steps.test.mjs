import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const load = (file) => {
  const source = readFileSync(new URL(`../src/lib/${file}`, import.meta.url), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const context = { exports: {} };
  runInNewContext(output, context);
  return context.exports;
};
const { ingestionSteps, stepStates, stepBack } = load('ingestionSteps.ts');
const { stripLevelPrefix } = load('ocrStructure.ts');

const pdf = ingestionSteps('pdf');

test('a running task marks earlier steps done and its own step active', () => {
  assert.deepEqual([...stepStates(pdf, 'parsing')], ['done', 'active', 'pending', 'pending', 'pending', 'pending']);
  assert.deepEqual([...stepStates(pdf, 'embedding')], ['done', 'done', 'done', 'done', 'active', 'pending']);
});

test('awaiting review covers both the OCR review and the change comparison', () => {
  assert.deepEqual([...stepStates(pdf, 'awaiting_review')], ['done', 'done', 'active', 'active', 'pending', 'pending']);
});

test('a completed task marks every step done', () => {
  assert.ok(stepStates(pdf, 'completed').every((s) => s === 'done'));
});

test('a failed task stops at the last running step the page saw', () => {
  assert.deepEqual([...stepStates(pdf, 'failed', 'chunking')], ['done', 'done', 'done', 'done', 'failed', 'pending']);
  assert.deepEqual([...stepStates(pdf, 'cancelled', 'awaiting_review')], ['done', 'done', 'cancelled', 'pending', 'pending', 'pending']);
  assert.deepEqual([...stepStates(pdf, 'failed')], ['done', 'failed', 'pending', 'pending', 'pending', 'pending']);
});

test('Pháp điển HTML has no review steps', () => {
  const html = ingestionSteps('phap_dien_html');
  assert.equal(html.length, 4);
  assert.deepEqual([...stepStates(html, 'indexing')], ['done', 'done', 'active', 'pending']);
});

test('removing a line marker leaves the text the parser reads as plain', () => {
  assert.equal(stripLevelPrefix('Điều 5. Phạm vi điều chỉnh'), 'Phạm vi điều chỉnh');
  assert.equal(stripLevelPrefix('1. Người lao động có quyền'), 'Người lao động có quyền');
  assert.equal(stripLevelPrefix('a) Được trả lương'), 'Được trả lương');
  assert.equal(stripLevelPrefix('Chương II'), '');
  assert.equal(stripLevelPrefix('Văn bản thường'), 'Văn bản thường');
});

test('in review the open tab marks which review step is current', () => {
  assert.deepEqual([...stepStates(pdf, 'awaiting_review', null, 'ocr')], ['done', 'done', 'active', 'pending', 'pending', 'pending']);
  assert.deepEqual([...stepStates(pdf, 'awaiting_review', null, 'changes')], ['done', 'done', 'done', 'active', 'pending', 'pending']);
});

test('only earlier review steps can be gone back to, each with its own action', () => {
  const back = (status, index, extra = {}, tab) => {
    const states = stepStates(pdf, status, status === 'cancelled' || status === 'failed' ? 'embedding' : null, tab);
    const result = stepBack(pdf[index], index, states, { status, documentType: 'pdf', hasDraft: true, hasIndexed: false, ...extra });
    return result && `${result.kind}:${result.tab}`;
  };
  assert.equal(back('awaiting_review', 2, {}, 'changes'), 'tab:ocr');
  assert.equal(back('awaiting_review', 3, {}, 'ocr'), null); // forward goes through the tabs
  assert.equal(back('embedding', 3), 'stop:changes');
  assert.equal(back('embedding', 1), null); // no going back to OCR
  assert.equal(back('cancelled', 2), 'resume:ocr');
  assert.equal(back('cancelled', 2, { hasDraft: false }), null);
  assert.equal(back('completed', 2, { hasDraft: false, hasIndexed: true }), 'reopen:ocr');
  assert.equal(back('completed', 2, { hasDraft: true, hasIndexed: true }), null);
  assert.equal(stepBack(pdf[2], 2, stepStates(pdf, 'completed'), { status: 'completed', documentType: 'phap_dien_html', hasDraft: false, hasIndexed: true }), null);
});
