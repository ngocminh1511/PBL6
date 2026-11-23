import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../src/lib/textDiff.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const context = { exports: {}, Uint32Array };
runInNewContext(output, context);
const { diffWords } = context.exports;
const plain = (parts) => JSON.parse(JSON.stringify(parts));

test('a changed word is one removal and one addition between kept words', () => {
  assert.deepEqual(plain(diffWords('Người lao động có quyền', 'Người lao động có nghĩa vụ')), [
    { kind: 'same', text: 'Người lao động có ' },
    { kind: 'removed', text: 'quyền' },
    { kind: 'added', text: 'nghĩa vụ' },
  ]);
});

test('each side can be rebuilt from its parts', () => {
  const before = 'Điều 3. Nội dung cũ của Điều 3.';
  const after = 'Điều 3. Nội dung mới của Điều 3 đã sửa.';
  const parts = diffWords(before, after);
  assert.equal(parts.filter((p) => p.kind !== 'added').map((p) => p.text).join(''), before);
  assert.equal(parts.filter((p) => p.kind !== 'removed').map((p) => p.text).join(''), after);
});

test('a missing side is a whole addition or removal', () => {
  assert.deepEqual(plain(diffWords('', 'Mới')), [{ kind: 'added', text: 'Mới' }]);
  assert.deepEqual(plain(diffWords('Cũ', '')), [{ kind: 'removed', text: 'Cũ' }]);
});
