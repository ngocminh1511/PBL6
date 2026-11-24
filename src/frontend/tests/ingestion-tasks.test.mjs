import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/ingestionTasks.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const context = { exports: {} };
runInNewContext(output, context);
const { defaultRevision, revisionLabel, revisionStatusLabel, isEditable } = context.exports;

const rev = (number, kind, status) => ({ id: `r${number}`, number, kind, status });

test('the draft is shown first, else the indexed revision, else the latest', () => {
  assert.equal(defaultRevision([rev(1, 'ocr', 'locked'), rev(2, 'review', 'indexed'), rev(3, 'review', 'draft')]).id, 'r3');
  assert.equal(defaultRevision([rev(1, 'ocr', 'locked'), rev(2, 'review', 'locked'), rev(3, 'review', 'indexed')]).id, 'r3');
  assert.equal(defaultRevision([rev(1, 'ocr', 'locked')]).id, 'r1');
  assert.equal(defaultRevision([]), null);
});

test('only a draft review is editable and revisions are named for people', () => {
  assert.equal(isEditable(rev(3, 'review', 'draft')), true);
  assert.equal(isEditable(rev(2, 'review', 'indexed')), false);
  assert.equal(isEditable(rev(1, 'ocr', 'locked')), false);
  assert.equal(revisionLabel(rev(1, 'ocr', 'locked')), 'OCR gốc');
  assert.equal(revisionLabel(rev(3, 'review', 'draft')), 'Rà soát 2');
  assert.equal(revisionStatusLabel(rev(2, 'review', 'indexed')), 'đang dùng');
});
