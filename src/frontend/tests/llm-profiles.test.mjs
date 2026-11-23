import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
import { JSDOM } from 'jsdom';
import React from 'react';
import ts from 'typescript';

const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', { url: 'http://localhost/admin' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
const { createRoot } = await import('react-dom/client');
const act = React.act || (await import('react-dom/test-utils')).act;
const require = createRequire(import.meta.url);
let service;
const api = new Proxy({}, { get: (_, method) => (...args) => service[method](...args) });
function compile(path, overrides = {}) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const output = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX,
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText;
  const context = { exports: {}, require: name => overrides[name] || require(name), setTimeout, clearTimeout };
  runInNewContext(output, context);
  return context.exports;
}
const ui = compile('../src/components/admin/ui.ts');
const { LLMProfilesManager } = compile('../src/components/admin/LLMProfilesManager.tsx', {
  '../../lib/api': { api, errorMessage: error => error.message }, './ui': ui,
});
const { PostgresSettings } = compile('../src/components/admin/PostgresSettings.tsx', {
  '../../lib/api': { api, errorMessage: error => error.message }, './ui': ui,
});
const adminLogic = compile('../src/lib/admin-config.ts');
const { SettingsPanel } = compile('../src/components/settings/SettingsPanel.tsx', {
  '../../lib/api': { api, errorMessage: error => error.message },
  '../../lib/admin-config': adminLogic,
  '../admin/LLMProfilesManager': { LLMProfilesManager },
  '../admin/PostgresSettings': { PostgresSettings },
  '../admin/ui': ui, './settings.module.css': { page: 'admin-page' },
});
const { default: AdminPage } = compile('../src/app/admin/page.tsx', {
  '../../components/settings/SettingsPanel': { SettingsPanel },
});
const environment = { id: 'environment', name: 'Từ môi trường', mode: 'cloud', provider: 'gemini', model: 'existing-model',
  base_url: '', local_runtime: 'compatible', api_key_source: 'environment', key_configured: true, read_only: true, verification: null };
let root;
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const button = text => Array.from(document.querySelectorAll('button')).find(item => !item.closest('[hidden]') && item.textContent.trim() === text);
const field = text => Array.from(document.querySelectorAll('label')).find(item => item.textContent.startsWith(text))?.querySelector('input,select');
async function click(element) {
  assert.ok(element, 'control exists');
  await act(async () => { element.click(); });
}
async function fill(element, value) {
  assert.ok(element, 'field exists');
  await act(async () => {
    const prototype = element.tagName === 'SELECT' ? dom.window.HTMLSelectElement.prototype : dom.window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value);
    element.dispatchEvent(new dom.window.Event(element.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  });
}
async function mount(overrides = {}) {
  let version = 1;
  const profiles = [environment];
  const calls = { saves: [], models: [] };
  const listing = () => ({ profiles: [...profiles], active_profile_id: 'environment', config_version: version, can_save: true, encryption_ready: true });
  service = {
    listLLMProfiles: async () => listing(),
    listProfileModels: async input => { calls.models.push(input); return { provider: input.provider, models: ['installed-qwen', 'installed-llama'] }; },
    checkLLMProfile: async () => ({ service: 'llm', status: 'passed', message: 'Kết nối thành công.', checked_at: new Date().toISOString(), latency_ms: 1, details: {} }),
    saveLLMProfile: async input => {
      calls.saves.push(input); version++;
      const { api_key, ...publicProfile } = input;
      profiles.push({ ...publicProfile, id: 'profile-' + calls.saves.length, read_only: false, key_configured: true, verification: null });
      return listing();
    }, ...overrides,
  };
  await act(async () => {
    root = createRoot(document.getElementById('app'));
    root.render(React.createElement(LLMProfilesManager, { config: { config_version: 1, can_save: true, encryption_ready: true }, onChanged: async () => {} }));
  });
  return calls;
}
afterEach(async () => { if (root) await act(async () => root.unmount()); root = null; });

test('adding starts by choosing Local or Cloud before showing provider fields', async () => {
  await mount();
  await click(button('Thêm cấu hình'));
  assert.ok(document.querySelector('dialog[open]'));
  assert.equal(field('Nhà cung cấp'), undefined);
  assert.equal(field('API key'), undefined);
  const local = Array.from(document.querySelectorAll('button')).find(item => item.getAttribute('aria-pressed') === 'false' && item.textContent.startsWith('Local'));
  await click(local);
  await act(async () => { await sleep(550); });
  assert.ok(field('Máy chủ local'));
  assert.equal(field('Nhà cung cấp'), undefined);
  const choices = Array.from(document.querySelectorAll('#llm-profile-model option')).map(item => item.value);
  assert.ok(choices.includes('installed-qwen') && choices.includes('installed-llama'));
});

test('two Gemini connections can be added without replacing each other', async () => {
  const calls = await mount();
  for (const name of ['Gemini cá nhân', 'Gemini dự án']) {
    await click(button('Thêm cấu hình'));
    await click(Array.from(document.querySelectorAll('button')).find(item => item.textContent.startsWith('Cloud') && item.hasAttribute('aria-pressed')));
    await fill(field('Tên cấu hình'), name);
    await fill(field('API key'), 'secret-for-' + name);
    await click(button('Nhập thủ công'));
    await fill(document.getElementById('llm-profile-model'), 'selected-gemini');
    assert.equal(button('Lưu cấu hình').disabled, false);
    await click(button('Lưu cấu hình'));
  }
  assert.equal(calls.saves.length, 2);
  assert.equal(calls.saves[0].provider, 'gemini');
  assert.notEqual(calls.saves[0].api_key, calls.saves[1].api_key);
  assert.ok(document.querySelector('tbody').textContent.includes('Gemini cá nhân'));
  assert.ok(document.querySelector('tbody').textContent.includes('Gemini dự án'));
  assert.equal(document.body.textContent.includes('secret-for-'), false);
});

test('a late local model discovery response cannot populate a different server', async () => {
  let resolveOld;
  await mount({ listProfileModels: input => input.base_url.includes('11434')
    ? new Promise(resolve => { resolveOld = resolve; })
    : Promise.resolve({ provider: 'local', models: ['new-server-model'] }) });
  await click(button('Thêm cấu hình'));
  await click(Array.from(document.querySelectorAll('button')).find(item => item.textContent.startsWith('Local') && item.hasAttribute('aria-pressed')));
  await act(async () => { await sleep(550); });
  await fill(field('Địa chỉ máy chủ'), 'http://localhost:1234/v1');
  await act(async () => { resolveOld({ provider: 'local', models: ['old-server-model'] }); });
  assert.equal(document.getElementById('llm-profile-model').textContent.includes('old-server-model'), false);
  await act(async () => { await sleep(550); });
  assert.ok(document.getElementById('llm-profile-model').textContent.includes('new-server-model'));
});

test('editing the selected model invalidates a pending successful verification', async () => {
  let finish;
  await mount({ checkLLMProfile: () => new Promise(resolve => { finish = resolve; }) });
  await click(button('Thêm cấu hình'));
  await click(Array.from(document.querySelectorAll('button')).find(item => item.textContent.startsWith('Local') && item.hasAttribute('aria-pressed')));
  await act(async () => { await sleep(550); });
  await fill(document.getElementById('llm-profile-model'), 'installed-qwen');
  await click(button('Kiểm tra'));
  await fill(document.getElementById('llm-profile-model'), 'installed-llama');
  await act(async () => { finish({ status: 'passed', message: 'OLD CHECK PASSED', details: {} }); });
  assert.equal(document.body.textContent.includes('OLD CHECK PASSED'), false);
});

async function mountPostgres(overrides = {}) {
  const config = { configured: false, connection_status: 'unavailable', host: '', port: 5432, database: '', username: '',
    sslmode: 'require', password_configured: false, source: 'default', environment_override: false, pending_restart: false, pending_apply: false, can_apply: false, saved: false, message: '' };
  const calls = { checks: [], saves: [], applies: 0 };
  service = {
    getPostgresConfig: async () => config,
    checkPostgresConfig: async input => { calls.checks.push(input); return { status: 'passed', message: 'Kết nối PostgreSQL thành công.', checked_at: new Date().toISOString(), latency_ms: 1, details: {} }; },
    savePostgresConfig: async input => { calls.saves.push(input); return { ...config, configured: true, host: 'db.example', database: 'app',
      saved: true, pending_restart: false, pending_apply: true, can_apply: true, message: 'Đã lưu vào .env.' }; },
    applyPostgresConfig: async () => { calls.applies++; return { ...config, configured: true, saved: true, connection_status: 'connected',
      host: 'db.example', database: 'app', message: 'Đã áp dụng kết nối PostgreSQL.' }; },
    ...overrides,
  };
  await act(async () => { root = createRoot(document.getElementById('app')); root.render(React.createElement(PostgresSettings)); });
  return calls;
}

test('PostgreSQL bootstrap shows saved state and applies without entering credentials again', async () => {
  const calls = await mountPostgres();
  assert.equal(button('Lưu vào .env').disabled, true);
  await fill(document.getElementById('postgres-url'), 'postgresql://user:private-pass@db.example/app');
  assert.equal(button('Lưu vào .env').disabled, false);
  await click(button('Lưu vào .env'));
  assert.equal(calls.saves.length, 1);
  assert.ok(document.body.textContent.includes('Đã lưu · chưa áp dụng'));
  assert.equal(button('Đã lưu').disabled, true);
  assert.equal(document.getElementById('postgres-url').value, '');
  assert.equal(document.body.textContent.includes('private-pass'), false);
  await click(button('Áp dụng kết nối đã lưu'));
  assert.equal(calls.applies, 1);
  assert.ok(document.body.textContent.includes('Đang dùng kết nối đã lưu'));
});

test('PostgreSQL field mode sends host, port, database and SSL explicitly', async () => {
  const calls = await mountPostgres();
  await click(button('Nhập từng trường'));
  await fill(field('Host'), 'db.example');
  await fill(field('Port'), '6543');
  await fill(field('Tên database'), 'app');
  await fill(field('Tên người dùng'), 'user');
  await fill(field('Mật khẩu'), 'test-password');
  await click(button('Kiểm tra'));
  assert.equal(calls.checks[0].mode, 'fields');
  assert.equal(calls.checks[0].port, 6543);
  assert.equal(calls.checks[0].sslmode, 'require');
  assert.equal(calls.checks[0].password, 'test-password');
  assert.ok(document.body.textContent.includes('Kết nối PostgreSQL thành công.'));
});

test('editing a PostgreSQL connection invalidates a pending successful check', async () => {
  let finish;
  await mountPostgres({ checkPostgresConfig: () => new Promise(resolve => { finish = resolve; }) });
  await fill(document.getElementById('postgres-url'), 'postgresql://user:pass@old.example/app');
  await click(button('Kiểm tra'));
  await fill(document.getElementById('postgres-url'), 'postgresql://user:pass@new.example/app');
  await act(async () => { finish({ status: 'passed', message: 'STALE POSTGRES CHECK', checked_at: new Date().toISOString(), latency_ms: 1 }); });
  assert.equal(document.body.textContent.includes('STALE POSTGRES CHECK'), false);
});


test('reloading PostgreSQL settings keeps the saved badge and does not claim an unsaved form', async () => {
  await mountPostgres({ getPostgresConfig: async () => ({ configured: true, saved: true, pending_apply: true, pending_restart: false, can_apply: true,
    connection_status: 'unavailable', host: 'db.example', port: 5432, database: 'app', username: 'user', sslmode: 'require', password_configured: true }) });
  assert.ok(document.body.textContent.includes('Đã lưu · chưa áp dụng'));
  assert.ok(document.body.textContent.includes('Thông tin đã được lưu, bạn không cần nhập lại.'));
  assert.equal(button('Đã lưu').disabled, true);
  assert.ok(button('Áp dụng kết nối đã lưu'));
  assert.equal(document.body.textContent.includes('Chưa kiểm tra thay đổi trên form'), false);
});

const navButton = name => Array.from(document.querySelectorAll('nav[aria-label="Nhóm cấu hình"] button')).find(item => item.textContent.trim() === name);
const verified = name => !!navButton(name)?.parentElement.querySelector('[aria-label="Đã kiểm tra thành công"]');
const passed = service => ({ service, status: 'passed', message: 'Kiểm tra thành công.', checked_at: new Date().toISOString(), latency_ms: 1, details: {} });

async function mountAdmin(overrides = {}) {
  const config = { config_version: 1, can_save: false, encryption_ready: false, configuration_error: null,
    postgres_status: 'unavailable', sources: {}, environment_sources: {}, environment_values: {},
    environment_secret_configured: {}, secret_configured: {}, available_collections: { legal: 'test-model' },
    collection_models: {}, embedding_model: 'test-model', embedding_backend: 'modal', query_embedding_backend: 'modal',
    modal_app_name: 'test-app', qdrant_url: 'https://vectors.example', qdrant_collection: 'legal', qdrant_timeout: 10,
    neo4j_uri: 'neo4j+s://graph.example', neo4j_user: 'user', neo4j_database: 'database',
    ocr_model: 'vgg_transformer', ocr_device: '', ocr_dpi: 300, max_upload_bytes: 50 * 1024 * 1024,
    ocr_beamsearch: false, ocr_semantic_chunking: false,
    redis_enabled: true, startup: { cors_origins: [] },
    embedding_catalog: [
      { model: 'test-model', label: 'Test', dimensions: 1024, max_tokens: 8192, collection: 'legal' },
      { model: 'bkai-foundation-models/vietnamese-bi-encoder', label: 'BKAI', dimensions: 768, max_tokens: 256, collection: 'legal_ld_v7_bkai' },
    ] };
  const postgres = { configured: true, saved: true, pending_apply: true, can_apply: true, pending_restart: false,
    connection_status: 'unavailable', host: 'db.example', port: 5432, database: 'app', username: 'user',
    sslmode: 'require', password_configured: true, environment_override: false };
  service = {
    getAdminConfig: async () => config,
    getSystemStats: async () => ({ vector_db_status: 'connected', graph_db_status: 'connected', redis_status: 'not_checked' }),
    getPostgresConfig: async () => postgres,
    listLLMProfiles: async () => ({ profiles: [environment], active_profile_id: environment.id, config_version: 1 }),
    checkAdminConfig: async name => passed(name),
    checkPostgresConfig: async () => passed('postgres'),
    checkLLMProfile: async () => passed('llm'),
    ...overrides,
  };
  await act(async () => {
    root = createRoot(document.getElementById('app'));
    root.render(React.createElement(AdminPage));
  });
}

test('sidebar ticks reflect live connections and leave unchecked groups without ticks', async () => {
  await mountAdmin();
  assert.equal(verified('Qdrant'), true);
  assert.equal(verified('Neo4j'), true);
  for (const name of ['Mô hình LLM', 'PostgreSQL', 'Embedding', 'Lưu trữ file', 'Redis cache', 'OCR và upload']) {
    assert.equal(verified(name), false, name);
  }
  assert.equal(document.querySelector('[aria-labelledby="settings-group-title"]'), null, 'LLM has a single settings panel');
});

test('sidebar ignores old successes after edits and clears ticks after a failed recheck', async () => {
  let finish;
  await mountAdmin({ checkAdminConfig: () => new Promise(resolve => { finish = resolve; }) });
  await click(navButton('Neo4j'));
  await click(button('Kiểm tra'));
  assert.equal(verified('Neo4j'), false);
  await fill(document.getElementById('config-neo4j_uri'), 'neo4j+s://new.example');
  await act(async () => { finish(passed('neo4j')); });
  assert.equal(verified('Neo4j'), false);

  service.checkAdminConfig = async () => passed('neo4j');
  await click(button('Kiểm tra'));
  assert.equal(verified('Neo4j'), true);
  await click(navButton('OCR và upload'));
  assert.equal(verified('Neo4j'), true, 'switching panels preserves the verification');
  await click(navButton('Neo4j'));
  service.checkAdminConfig = async () => { throw new Error('offline'); };
  await click(button('Kiểm tra'));
  assert.equal(verified('Neo4j'), false, 'a live probe cannot override a newer check failure');
});

test('editing embedding clears related vector checks while keeping unrelated graph ticks', async () => {
  await mountAdmin();
  await click(navButton('Embedding'));
  await fill(document.getElementById('config-embedding_model'), 'another-model');
  assert.equal(verified('Qdrant'), false);
  assert.equal(verified('Neo4j'), true);
  await click(button('Kiểm tra'));
  assert.equal(verified('Embedding'), true);
  await click(navButton('Qdrant'));
  await fill(document.getElementById('config-qdrant_collection'), 'another-collection');
  assert.equal(verified('Embedding'), false);
});

test('LLM and PostgreSQL verification survives navigation and connection edits remove the tick', async () => {
  await mountAdmin();
  await click(document.querySelector('button[aria-label="Kiểm tra Từ môi trường"]'));
  assert.equal(verified('Mô hình LLM'), true);
  assert.ok(document.querySelector('tbody td:first-child [aria-label="Đã kiểm tra thành công"]'));
  await click(navButton('PostgreSQL'));
  await click(button('Kiểm tra'));
  assert.equal(verified('PostgreSQL'), true);
  await click(navButton('Neo4j'));
  assert.equal(verified('Mô hình LLM'), true);
  assert.equal(verified('PostgreSQL'), true);
  await click(navButton('PostgreSQL'));
  await fill(document.getElementById('postgres-url'), 'postgresql://user:pass@new.example/app');
  assert.equal(verified('PostgreSQL'), false);
  await click(navButton('Mô hình LLM'));
  service.checkLLMProfile = async () => { throw new Error('offline'); };
  await click(document.querySelector('button[aria-label="Kiểm tra Từ môi trường"]'));
  assert.equal(verified('Mô hình LLM'), false);
});

test('a failed LLM recheck does not fall back to an older saved verification', async () => {
  const profile = { ...environment, verification: passed('llm') };
  await mountAdmin({ listLLMProfiles: async () => ({ profiles: [profile], active_profile_id: profile.id, config_version: 1 }),
    checkLLMProfile: async () => { throw new Error('offline'); } });
  assert.equal(verified('Mô hình LLM'), true);
  await click(document.querySelector('button[aria-label="Kiểm tra Từ môi trường"]'));
  assert.equal(verified('Mô hình LLM'), false);
  assert.equal(document.querySelector('tbody td:first-child [aria-label="Đã kiểm tra thành công"]'), null);
});

test('checking an inactive LLM profile does not verify the active LLM connection', async () => {
  const other = { ...environment, id: 'other', name: 'Other LLM', read_only: false };
  await mountAdmin({ listLLMProfiles: async () => ({ profiles: [environment, other], active_profile_id: environment.id, config_version: 1 }) });
  await click(document.querySelector('button[aria-label="Kiểm tra Other LLM"]'));
  assert.equal(verified('Mô hình LLM'), false);
  const row = Array.from(document.querySelectorAll('tbody tr')).find(item => item.textContent.includes('Other LLM'));
  assert.ok(row.querySelector('td:first-child [aria-label="Đã kiểm tra thành công"]'));
});

test('choosing a benchmarked embedding model switches to the collection indexed with it', async () => {
  await mountAdmin();
  await click(navButton('Embedding'));
  const select = document.getElementById('config-embedding_model');
  assert.deepEqual(Array.from(select.options).map(item => item.value), ['test-model', 'bkai-foundation-models/vietnamese-bi-encoder']);
  await fill(select, 'bkai-foundation-models/vietnamese-bi-encoder');
  await click(navButton('Qdrant'));
  assert.equal(document.getElementById('config-qdrant_collection').value, 'legal_ld_v7_bkai');
  await click(navButton('Embedding'));
  await fill(document.getElementById('config-embedding_model'), 'test-model');
  await click(navButton('Qdrant'));
  assert.equal(document.getElementById('config-qdrant_collection').value, 'legal', 'the collection follows the model back');
});
