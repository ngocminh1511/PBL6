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
  const evidence = (appendix_id, chunk_id) => ({ appendix_id, chunk_id, citation: 'Phụ lục ' + appendix_id });
  const messages = [
    { role: 'assistant', attachments: [], legal_evidence: [evidence('old:pl1', 'c0')] },
    { role: 'user', content: 'Mẫu hợp đồng giúp việc?' },
    { role: 'assistant',
      attachments: [{ appendix_id: '145:pl5', number: 'V', document_number: '145/2020/NĐ-CP' }],
      legal_evidence: [{ citation: 'Điều 35' }, evidence('145:pl5', 'c5'), evidence('145:pl3', 'c3'), evidence('145:pl3', 'c4')] },
  ];
  assert.deepEqual(JSON.parse(JSON.stringify(answerAppendices(messages))), [
    { id: '145:pl5', label: 'Phụ lục V · 145/2020/NĐ-CP', chunkId: 'c5' },
    { id: '145:pl3', label: 'Phụ lục 145:pl3', chunkId: 'c3' },
  ]);
  assert.equal(answerAppendices([{ role: 'user', content: 'hi' }]).length, 0);
});

test('preview and Word links encode the appendix and form', () => {
  assert.equal(api.appendixViewUrl('145:pl5', { form: '01/PLV', chunkId: 'c5' }), '/api/appendices/145%3Apl5/view?form=01%2FPLV&chunk_id=c5');
  assert.equal(api.appendixDocxUrl('145:pl5'), '/api/appendices/145%3Apl5/docx');
});
