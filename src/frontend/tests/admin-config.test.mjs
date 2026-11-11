import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

// Compile the pure form logic in memory; no browser, credentials or extra runner needed.
const source = readFileSync(new URL('../src/lib/admin-config.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const context = { exports: {} };
runInNewContext(compiled, context);
const { buildConfigUpdate, createConfigRequestTracker } = context.exports;
const plain = value => JSON.parse(JSON.stringify(value));

test('saving one group excludes credentials and resets from other groups', () => {
  const draft = { gemini_api_key: 'unsaved-private', qdrant_url: 'http://localhost:6333', qdrant_api_key: '' };
  assert.deepEqual(plain(buildConfigUpdate(4, draft, ['neo4j_password', 'qdrant_timeout'], 'qdrant')), {
    qdrant_url: 'http://localhost:6333', qdrant_api_key: '', reset_fields: ['qdrant_timeout'], config_version: 4,
  });
  assert.equal(draft.gemini_api_key, 'unsaved-private');
});

test('save all preserves explicit false, empty authentication and environment resets', () => {
  assert.deepEqual(plain(buildConfigUpdate(2, { redis_enabled: false, local_llm_api_key: '' }, ['gemini_api_key'])), {
    redis_enabled: false, local_llm_api_key: '', reset_fields: ['gemini_api_key'], config_version: 2,
  });
});

test('an old successful check cannot confirm an edited endpoint', async () => {
  const tracker = createConfigRequestTracker();
  const revision = tracker.begin('qdrant');
  const response = Promise.resolve({ status: 'passed' });
  tracker.invalidate('qdrant_url');
  const result = await response;
  assert.equal(result.status, 'passed');
  assert.equal(tracker.isCurrent('qdrant', revision), false);
});

test('changing embedding invalidates related collection checks only', () => {
  const tracker = createConfigRequestTracker();
  const vector = tracker.begin('qdrant');
  const llm = tracker.begin('llm');
  tracker.invalidate('embedding_model');
  assert.equal(tracker.isCurrent('qdrant', vector), false);
  assert.equal(tracker.isCurrent('llm', llm), true);
});

test('a newer check and discarding changes supersede earlier requests', () => {
  const tracker = createConfigRequestTracker();
  const first = tracker.begin('llm');
  const second = tracker.begin('llm');
  assert.equal(tracker.isCurrent('llm', first), false);
  assert.equal(tracker.isCurrent('llm', second), true);
  tracker.invalidateAll();
  assert.equal(tracker.isCurrent('llm', second), false);
});
