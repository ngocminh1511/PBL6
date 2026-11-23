import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import ts from 'typescript';

const require = createRequire(import.meta.url);
function compile(path, overrides = {}) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText;
  const context = { exports: {}, require: name => overrides[name] || require(name), URLSearchParams };
  runInNewContext(output, context);
  return context.exports;
}
const api = compile('../src/lib/api.ts');
const { answerAppendices } = compile('../src/components/inspector/AppendixPanel.tsx', {
  '../../lib/api': api, '../../stores/chatStore': { useChatStore: () => ({}) },
});

test('appendices of the latest answer are merged from attachments and cited evidence', () => {
  const messages = [
    { role: 'assistant', attachments: [], legal_evidence: [{ appendix_id: 'old:pl1', citation: 'Phụ lục cũ' }] },
    { role: 'user', content: 'Mẫu hợp đồng giúp việc?' },
    { role: 'assistant',
      attachments: [{ appendix_id: '145:pl5', number: 'V', document_number: '145/2020/NĐ-CP' }],
      legal_evidence: [
        { citation: 'Điều 35' },
        // Unembedded form: only its metadata reached the answer; chunk_id equals the appendix id.
        { appendix_id: '145:pl5', chunk_id: '145:pl5', citation: 'Phụ lục V', view_url: '/api/appendices/145%3Apl5/view' },
        { appendix_id: '145:pl3', chunk_id: '145:pl3:p1', citation: 'Phụ lục III',
          view_url: '/api/appendices/145%3Apl3/view?chunk_id=145%3Apl3%3Ap1' }] },
  ];
  assert.deepEqual(JSON.parse(JSON.stringify(answerAppendices(messages))), [
    { id: '145:pl5', label: 'Phụ lục V · 145/2020/NĐ-CP' },
    { id: '145:pl3', label: 'Phụ lục III', chunkId: '145:pl3:p1' },
  ]);
  assert.equal(answerAppendices([{ role: 'user', content: 'hi' }]).length, 0);
});

test('only chunks the backend put in view_url are highlighted', () => {
  assert.equal(api.chunkFromViewUrl('/api/appendices/a/view?chunk_id=a%3Ap2'), 'a:p2');
  assert.equal(api.chunkFromViewUrl('/api/appendices/a/view'), undefined);
  assert.equal(api.chunkFromViewUrl(undefined), undefined);
});

test('preview and Word links encode the appendix and form', () => {
  assert.equal(api.appendixViewUrl('145:pl5', { form: '01/PLV', chunkId: 'c5' }), '/api/appendices/145%3Apl5/view?form=01%2FPLV&chunk_id=c5');
  assert.equal(api.appendixDocxUrl('145:pl5'), '/api/appendices/145%3Apl5/docx');
});
