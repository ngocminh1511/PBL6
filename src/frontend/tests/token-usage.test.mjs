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
  const context = { exports: {}, require: name => overrides[name] || require(name), console, setTimeout, clearTimeout };
  runInNewContext(output, context);
  return context.exports;
}
const tokenComponent = compile('../src/components/chat/TokenUsage.tsx');
const apiModule = compile('../src/lib/api.ts');
const { ChatMessage } = compile('../src/components/chat/ChatMessage.tsx', {
  './TokenUsage': tokenComponent, './PipelineTrace': { PipelineTrace: () => null },
  './CitationChip': { CitationChip: () => null }, '../../lib/api': apiModule,
  './MarkdownAnswer': compile('../src/components/chat/MarkdownAnswer.tsx', {
    '../../lib/citationLinks': compile('../src/lib/citationLinks.ts'),
  }),
  '../../stores/chatStore': { useChatStore: select => select({ focusEvidence: () => {} }) },
});
const { TokenUsage } = tokenComponent;
const call = { stage: 'generation', provider: 'groq', model: 'test-model', status: 'succeeded',
  input_tokens: 51, output_tokens: 9, total_tokens: 60 };
const usage = { status: 'complete', input_tokens: 152, output_tokens: 16, total_tokens: 168,
  executed_stages: ['session_title', 'intent', 'generation'], calls: [
    { ...call, stage: 'session_title', input_tokens: 101, output_tokens: 7, total_tokens: 108 }, call] };
const domFor = element => new JSDOM(renderToStaticMarkup(element)).window.document;

test('historical assistant replies show unknown usage and user messages do not get a token footer', () => {
  const message = { id: 'old', session_id: 's', role: 'assistant', content: 'Xin chào', created_at: '2026-11-18' };
  const doc = domFor(React.createElement(ChatMessage, { message, index: 1 }));
  assert.match(doc.body.textContent, /Token LLM: Chưa có số liệu/);
  assert.doesNotMatch(doc.body.textContent, /Tổng: 0/);
  const user = domFor(React.createElement(ChatMessage, { message: { ...message, role: 'user' }, index: 0 }));
  assert.doesNotMatch(user.body.textContent, /Token LLM/);
});

test('summary includes all calls and the details distinguish local routing from skipped retrieval', () => {
  const doc = domFor(React.createElement(TokenUsage, { usage }));
  assert.match(doc.querySelector('summary').textContent, /Đầu vào: 152 · Đầu ra: 16 · Tổng: 168/);
  const rows = Array.from(doc.querySelectorAll('tbody tr'));
  assert.match(rows.find(row => row.textContent.includes('Phân loại ý định')).textContent, /Không gọi LLM000/);
  assert.match(rows.find(row => row.textContent.includes('Truy hồi chứng cứ')).textContent, /Không chạy———/);
  assert.equal(doc.querySelector('details').open, false);
  doc.querySelector('summary').click();
  assert.equal(doc.querySelector('details').open, true);
});

test('a rejected requested count is separate from the partial processed total', () => {
  const partial = { ...usage, status: 'partial', input_tokens: 101, output_tokens: 7, total_tokens: 108,
    calls: [usage.calls[0], { ...call, status: 'failed', http_status: 429,
      input_tokens: null, output_tokens: null, total_tokens: null, requested_tokens: 6864 }] };
  const doc = domFor(React.createElement(TokenUsage, { usage: partial }));
  assert.match(doc.querySelector('summary').textContent, /Tổng: 108/);
  assert.match(doc.querySelector('summary').textContent, /Chưa đủ số liệu.*1 lượt gọi lỗi/);
  assert.doesNotMatch(doc.querySelector('summary').textContent, /6[.,]?864/);
  assert.match(doc.querySelector('table').textContent, /Yêu cầu bị từ chối: 6\.864 token \(không cộng vào tổng đã xử lý\)/);
});

test('a provider without usage reports unknown values instead of invented zeros', () => {
  const doc = domFor(React.createElement(TokenUsage, { usage: { ...usage, status: 'unavailable',
    input_tokens: null, output_tokens: null, total_tokens: null,
    calls: [{ ...call, input_tokens: null, output_tokens: null, total_tokens: null }] } }));
  assert.match(doc.querySelector('summary').textContent, /Chưa có số liệu/);
  const generation = Array.from(doc.querySelectorAll('tbody tr')).find(row => row.textContent.includes('Sinh câu trả lời'));
  assert.equal(generation.querySelectorAll('td')[1].textContent, '—');
});

test('failed asks retain returned usage and starting another session clears it without a fake answer', async () => {
  const error = { isAxiosError: true, response: { status: 503, data: { detail: 'Đã đạt hạn mức', token_usage: usage } } };
  const { useChatStore } = compile('../src/stores/chatStore.ts', { '../lib/api': {
    api: { ask: async () => { throw error; } }, errorMessage: apiModule.errorMessage,
    errorTokenUsage: apiModule.errorTokenUsage,
  } });
  await useChatStore.getState().sendMessage('Câu hỏi');
  assert.equal(useChatStore.getState().error, 'Đã đạt hạn mức');
  assert.equal(useChatStore.getState().errorTokenUsage, usage);
  assert.equal(useChatStore.getState().messages.length, 0);
  await useChatStore.getState().createSession();
  assert.equal(useChatStore.getState().errorTokenUsage, null);
});
