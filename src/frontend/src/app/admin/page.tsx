'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Sparkles, Network, Database, GitBranch, FolderOpen, Layers, ScanText, Info, Settings2, RotateCcw, Save, CheckCircle2, Loader2, ChevronDown, AlertCircle } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import type { AdminConfig, AdminConfigValues, AdminSecretValues, ConfigField, ConfigService, ConfigCheckResult, SystemStats } from '../../lib/types';
import { buildConfigUpdate, configGroups, createConfigRequestTracker, ConfigDraft, ConfigFieldSpec } from '../../lib/admin-config';
import { LLMProfilesManager } from '../../components/admin/LLMProfilesManager';
import { PostgresSettings } from '../../components/admin/PostgresSettings';
import { adminInput, adminButton, adminPrimary } from '../../components/admin/ui';
import styles from './admin.module.css';

type CheckState = { checking?: boolean; result?: ConfigCheckResult; error?: string };
const icons = { llm: Sparkles, embedding: Network, qdrant: Database, neo4j: GitBranch, r2: FolderOpen, redis: Layers, ocr: ScanText };
const labels = { llm: 'Mô hình LLM', embedding: 'Embedding', qdrant: 'Qdrant', neo4j: 'Neo4j', r2: 'Lưu trữ file', redis: 'Redis cache', ocr: 'OCR và upload' };
const own = (object: object, key: string) => Object.prototype.hasOwnProperty.call(object, key);

export default function AdminPage() {
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [selected, setSelected] = useState<ConfigService | 'postgres' | 'info'>('llm');
  const [draft, setDraft] = useState<ConfigDraft>({});
  const [resets, setResets] = useState<ConfigField[]>([]);
  const [checks, setChecks] = useState<Partial<Record<ConfigService, CheckState>>>({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState<ConfigService | 'all' | null>(null);
  const requests = useRef(createConfigRequestTracker());
  const statsRevision = useRef(0);

  useEffect(() => {
    let alive = true;
    api.getAdminConfig().then(value => { if (alive) setConfig(value); }).catch(e => { if (alive) setError(errorMessage(e)); });
    const revision = ++statsRevision.current;
    api.getSystemStats().then(value => { if (alive && revision === statsRevision.current) setStats(value); }).catch(() => {});
    return () => { alive = false; statsRevision.current++; requests.current.invalidateAll(); };
  }, []);

  async function refreshConfig() {
    setConfig(await api.getAdminConfig());
    setStats(null);
    const revision = ++statsRevision.current;
    api.getSystemStats().then(value => { if (revision === statsRevision.current) setStats(value); }).catch(() => {});
  }

  function invalidate(field: ConfigField) {
    const groups = requests.current.invalidate(field);
    setChecks(previous => ({ ...previous, ...Object.fromEntries(groups.map(group => [group, {}])) }));
    setMessage('');
  }

  function change(field: ConfigField, nextValue: ConfigDraft[ConfigField]) {
    invalidate(field);
    setResets(previous => previous.filter(item => item !== field));
    setDraft(previous => { const next = { ...previous }; if (nextValue === undefined) delete next[field]; else next[field] = nextValue; return next; });
  }

  function reset(field: ConfigField) {
    invalidate(field);
    setDraft(previous => { const next = { ...previous }; delete next[field]; return next; });
    setResets(previous => previous.includes(field) ? previous : [...previous, field]);
  }

  function value(field: ConfigField): ConfigDraft[ConfigField] {
    if (own(draft, field)) return draft[field];
    if (field === 'query_embedding_backend' && (resets.includes(field) ? config?.environment_query_embedding_inherits : config?.query_embedding_inherits)) return value('embedding_backend');
    if (resets.includes(field)) return config?.environment_values[field as keyof AdminConfigValues];
    return config?.[field as keyof AdminConfigValues];
  }

  function changed(service?: ConfigService) {
    const fields = service ? configGroups.find(group => group.id === service)!.fields.map(field => field.key) : null;
    return [...Object.keys(draft), ...resets].some(key => !fields || fields.includes(key as ConfigField));
  }

  async function check(service: ConfigService) {
    if (!config) return;
    const revision = requests.current.begin(service);
    setChecks(previous => ({ ...previous, [service]: { checking: true } }));
    try {
      const result = await api.checkAdminConfig(service, buildConfigUpdate(config.config_version, draft, resets, service));
      if (requests.current.isCurrent(service, revision)) setChecks(previous => ({ ...previous, [service]: { result } }));
    } catch (e) { if (requests.current.isCurrent(service, revision)) setChecks(previous => ({ ...previous, [service]: { error: errorMessage(e) } })); }
  }

  async function save(service?: ConfigService) {
    if (!config) return;
    setSaving(service || 'all'); setError(''); setMessage('');
    const payload = buildConfigUpdate(config.config_version, draft, resets, service);
    const submitted = [...Object.keys(payload).filter(key => key !== 'reset_fields' && key !== 'config_version'), ...(payload.reset_fields || [])];
    requests.current.invalidateAll();
    setChecks(previous => Object.fromEntries(Object.entries(previous).map(([key, state]) => [key, state.checking ? {} : state])));
    try {
      setConfig(await api.updateAdminConfig(payload));
      setDraft(previous => Object.fromEntries(Object.entries(previous).filter(([key]) => !submitted.includes(key))));
      setResets(previous => previous.filter(key => !submitted.includes(key)));
      setMessage('Đã lưu và áp dụng thay đổi.');
      setStats(null);
      const revision = ++statsRevision.current;
      api.getSystemStats().then(value => { if (revision === statsRevision.current) setStats(value); }).catch(() => {});
    } catch (e) { setError(errorMessage(e)); }
    finally { setSaving(null); }
  }

  function fieldControl(field: ConfigFieldSpec) {
    if (!config) return null;
    if (field.key === 'modal_app_name' && value('embedding_backend') !== 'modal' && value('query_embedding_backend') !== 'modal') return null;
    if (field.key === 'ocr_semantic_model' && !value('ocr_semantic_chunking')) return null;
    const raw = value(field.key), id = 'config-' + field.key;
    const pending = own(draft, field.key) || resets.includes(field.key);
    const source = resets.includes(field.key) ? config.environment_sources[field.key] : config.sources[field.key];
    const sourceLabel = { saved: 'Đã lưu', environment: 'Từ môi trường', default: 'Mặc định' }[source];
    const secret = field.key as keyof AdminSecretValues;
    const configured = resets.includes(field.key) ? config.environment_secret_configured[secret] : config.secret_configured[secret];
    const secretStatus = own(draft, field.key) ? draft[field.key] === '' ? 'Không dùng xác thực' : 'Key mới chưa lưu' : configured ? 'Đã có key · để trống để giữ nguyên' : 'Chưa thiết lập';
    let control: React.ReactNode;
    if (field.kind === 'checkbox') control = <label className="flex items-center gap-2 h-10 text-sm text-slate-600"><input id={id} type="checkbox" className="accent-secondary w-4 h-4" checked={Boolean(raw)} disabled={!!saving} onChange={e => change(field.key, e.target.checked)} />{raw ? 'Đang bật' : 'Đang tắt'}</label>;
    else if (field.kind === 'select') control = <select id={id} className={adminInput} value={String(raw ?? '')} disabled={!!saving} onChange={e => change(field.key, e.target.value)}>{field.options?.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>;
    else if (field.kind === 'binding') {
      const collection = String(value('qdrant_collection') || ''), registry = (value('collection_models') || {}) as Record<string, string>;
      control = <div><input id={id} className={adminInput} disabled={!!saving || !collection} value={registry[collection] ?? config.available_collections[collection] ?? ''} onChange={e => change('collection_models', { ...registry, [collection]: e.target.value })} placeholder="Tên model đã dùng khi index" />
        <p className="mt-1 text-xs text-slate-400">Collection: {collection || 'Chưa chọn'}</p></div>;
    } else {
      const display = field.kind === 'secret' ? String(draft[field.key] ?? '') : field.kind === 'number' && raw !== '' ? Number(raw) / (field.scale || 1) : String(raw ?? '');
      control = <><input id={id} className={adminInput} type={field.kind === 'secret' ? 'password' : field.kind === 'number' ? 'number' : 'text'} value={display}
        min={field.min} step={field.kind === 'number' ? 1 : undefined} autoComplete={field.kind === 'secret' ? 'new-password' : 'off'} disabled={!!saving}
        list={field.key === 'qdrant_collection' ? 'registered-collections' : field.key === 'embedding_model' ? 'embedding-models' : undefined}
        placeholder={field.kind === 'secret' ? secretStatus : undefined} onChange={e => change(field.key, field.kind === 'number' ? e.target.value === '' ? '' : Number(e.target.value) * (field.scale || 1) : field.kind === 'secret' && !e.target.value ? undefined : e.target.value)} />
        {field.optionalAuth && <label className="inline-flex items-center gap-2 text-xs text-slate-400 mt-1"><input type="checkbox" className="accent-secondary" disabled={!!saving} checked={own(draft, field.key) && draft[field.key] === ''} onChange={e => change(field.key, e.target.checked ? '' : undefined)} />Không dùng xác thực</label>}
        {field.key === 'redis_url' && config.redis_endpoint && !pending && <p className="text-xs text-slate-400 break-all">{config.redis_endpoint}</p>}</>;
    }
    return <div key={field.key} className="space-y-1.5 min-w-0"><div className="flex items-center justify-between gap-2">
      <label htmlFor={id} className="text-sm font-medium text-slate-700">{field.label}</label><span className="flex items-center gap-1.5 shrink-0">
        <span className={'text-[11px] ' + (pending ? 'text-secondary' : 'text-slate-400')}>{pending ? resets.includes(field.key) ? 'Dùng môi trường' : 'Chưa lưu' : sourceLabel}</span>
        <button type="button" disabled={!!saving || resets.includes(field.key)} className="p-1 rounded text-slate-400 hover:text-secondary disabled:opacity-30" title="Dùng giá trị từ môi trường" aria-label={'Dùng giá trị môi trường: ' + field.label} onClick={() => reset(field.key)}><RotateCcw size={12} /></button>
      </span></div>{control}{field.hint && <p className="text-xs text-slate-400">{field.hint}</p>}</div>;
  }

  if (!config) return <div className={styles.page + ' max-w-6xl mx-auto p-6 text-slate-500'} role={error ? 'alert' : 'status'}>{error || 'Đang tải cấu hình hệ thống…'}</div>;
  const group = configGroups.find(item => item.id === selected);
  const state = group && checks[group.id], result = state?.result;
  const statuses = [
    ['PostgreSQL', config.postgres_status], ['Qdrant', stats?.vector_db_status], ['Neo4j', stats?.graph_db_status], ['Redis', stats?.redis_status],
  ];

  return <main className={styles.page + ' max-w-6xl mx-auto px-4 sm:px-6 py-6'}>
    <div className="mb-5"><div className="flex items-center gap-2.5"><Settings2 size={21} className="text-secondary" /><h1 className="text-[22px] leading-7 font-semibold tracking-tight">Cấu hình hệ thống</h1></div>
      <p className="text-sm text-slate-500 mt-1.5">Quản lý kết nối và lựa chọn dịch vụ cho hệ thống tra cứu.</p></div>
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mb-5 text-xs text-slate-500">{statuses.map(([name, status]) => <span key={name} title={status || 'Chưa kiểm tra'} className="inline-flex items-center gap-1.5"><span className={'w-1.5 h-1.5 rounded-full ' + (status === 'connected' ? 'bg-emerald-500' : status === 'unavailable' ? 'bg-red-400' : 'bg-slate-300')} />{name}<span className="text-slate-400">{status === 'connected' ? 'Đã kết nối' : status === 'unavailable' ? 'Không kết nối' : status === 'disabled' ? 'Đang tắt' : 'Chưa kiểm tra'}</span></span>)}</div>
    {config.configuration_error && <p role="alert" className="mb-4 p-3 bg-red-50 text-red-700 rounded-xl text-sm">{config.configuration_error}</p>}
    {(!config.can_save || !config.encryption_ready) && <details className="mb-5 px-4 py-3 rounded-xl border border-amber-200 bg-amber-50/60 text-sm text-amber-900">
      <summary className="cursor-pointer font-medium">Cần hoàn tất thiết lập để lưu cấu hình{!config.can_save && !config.encryption_ready ? ' · PostgreSQL và khóa mã hóa' : !config.can_save ? ' · PostgreSQL' : ' · Khóa mã hóa'}</summary>
      <p className="text-xs mt-2 leading-5">Bạn vẫn có thể thêm bản nháp và kiểm tra kết nối. {!config.can_save && 'Thiết lập DATABASE_URL và khởi động lại backend để lưu. '}{!config.encryption_ready && 'Thiết lập CONFIG_ENCRYPTION_KEY để lưu API key riêng.'}</p>
      {!config.can_save && <button type="button" className="mt-2 text-xs font-medium text-secondary hover:underline" onClick={() => setSelected('postgres')}>Mở cấu hình PostgreSQL</button>}
    </details>}
    {(error || message) && <p role={error ? 'alert' : 'status'} className={'mb-4 px-4 py-3 rounded-xl text-sm ' + (error ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700')}>{error || message}</p>}
    <div className="grid md:grid-cols-[190px_minmax(0,1fr)] gap-5 items-start">
      <nav aria-label="Nhóm cấu hình" className="flex overflow-x-auto md:flex-col gap-1 md:sticky md:top-20 md:border-r md:border-slate-200 md:pr-4 pb-2">
        {configGroups.map(item => { const Icon = icons[item.id]; return <React.Fragment key={item.id}><button type="button" aria-current={selected === item.id ? 'page' : undefined} onClick={() => { setSelected(item.id); setError(''); }}
          className={'flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-left whitespace-nowrap transition-colors ' + (selected === item.id ? 'bg-secondary/10 text-secondary font-semibold' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800')}>
          <Icon size={17} />{labels[item.id]}{item.id !== 'llm' && changed(item.id) && <span className="w-1.5 h-1.5 bg-secondary rounded-full ml-auto" title="Có thay đổi chưa lưu" />}</button>
          {item.id === 'llm' && <button type="button" aria-current={selected === 'postgres' ? 'page' : undefined} onClick={() => { setSelected('postgres'); setError(''); }}
            className={'flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-left whitespace-nowrap transition-colors ' + (selected === 'postgres' ? 'bg-secondary/10 text-secondary font-semibold' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800')}><Database size={17} />PostgreSQL</button>}
          </React.Fragment>; })}
        <div className="hidden md:block h-px bg-slate-200 my-2" /><button type="button" onClick={() => setSelected('info')} className={'flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-left whitespace-nowrap ' + (selected === 'info' ? 'bg-secondary/10 text-secondary font-semibold' : 'text-slate-500 hover:bg-slate-100')}><Info size={17} />Thông tin hệ thống</button>
      </nav>
      <div className="min-w-0 space-y-4">
        {selected === 'llm' ? <LLMProfilesManager config={config} onChanged={refreshConfig} /> : selected === 'postgres' ? <PostgresSettings onApplied={async () => { requests.current.invalidateAll(); setChecks({}); await refreshConfig(); }} /> : selected === 'info' ? <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100"><h2 className="text-base font-semibold">Thông tin hệ thống</h2><p className="text-sm text-slate-500 mt-1">Các thiết lập khởi động được quản lý qua môi trường.</p></div>
          <dl className="divide-y divide-slate-100 text-sm">{[
            ['PostgreSQL', config.postgres_endpoint || 'Chưa cấu hình DATABASE_URL'], ['Dataset', config.dataset_id], ['Phiên bản cấu hình', String(config.config_version)],
            ['Chế độ demo', config.demo_mode ? 'Bật' : 'Tắt'], ['Phiên tra cứu đã lưu', String(stats?.active_sessions_count ?? 'Chưa có số liệu')],
            ['Thư mục upload', config.startup.upload_dir], ['Thư mục runtime', config.startup.interim_dir], ['CORS', config.startup.cors_origins.join(', ')],
          ].map(([label, content]) => <div key={label} className="px-5 py-3 grid sm:grid-cols-[180px_1fr] gap-2"><dt className="text-slate-500">{label}</dt><dd className="break-all">{content}</dd></div>)}</dl>
          <p className="px-5 py-4 bg-slate-50/50 text-xs text-slate-400">DATABASE_URL, CONFIG_ENCRYPTION_KEY, JWT, CORS và BACKEND_ORIGIN cần khởi động lại dịch vụ khi thay đổi.</p>
        </section> : group && <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden" aria-labelledby="settings-group-title">
          <div className="px-5 py-4 border-b border-slate-100"><div className="flex justify-between items-center"><h2 id="settings-group-title" className="text-base font-semibold">{group.title}</h2>{changed(group.id) && <span className="text-xs text-secondary">Chưa lưu</span>}</div><p className="text-sm text-slate-500 mt-1 leading-5">{group.hint}</p></div>
          <div className="p-5 space-y-5"><div className="grid sm:grid-cols-2 gap-x-5 gap-y-4">{group.fields.filter(field => !field.advanced).map(fieldControl)}</div>
            {group.fields.some(field => field.advanced) && <details className="border-t border-slate-100 pt-3"><summary className="flex items-center gap-1 cursor-pointer text-sm text-slate-500 font-medium"><ChevronDown size={14} />Tùy chọn nâng cao</summary><div className="grid sm:grid-cols-2 gap-x-5 gap-y-4 mt-4">{group.fields.filter(field => field.advanced).map(fieldControl)}</div></details>}
          </div>
          <div className="px-5 py-4 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div aria-live="polite" className={'text-xs ' + (result?.status === 'passed' ? 'text-emerald-600' : state?.error || result?.status === 'failed' || result?.status === 'not_configured' ? 'text-red-600' : 'text-slate-400')}>
              <p className="flex items-center gap-1.5">{state?.checking ? <Loader2 size={14} className="animate-spin" /> : result?.status === 'passed' ? <CheckCircle2 size={14} /> : state?.error ? <AlertCircle size={14} /> : null}
                {state?.checking ? 'Đang kiểm tra…' : state?.error || result?.message || 'Chưa kiểm tra thay đổi'}</p>
              {result && <p className="mt-1 text-[11px] text-slate-400">{new Date(result.checked_at).toLocaleString('vi-VN')} · {result.latency_ms} ms{result.details.dimensions ? ` · ${result.details.dimensions} chiều` : ''}</p>}
            </div>
            <div className="flex gap-2 shrink-0"><button type="button" className={adminButton} disabled={!!saving || state?.checking || !!config.configuration_error} onClick={() => check(group.id)}><CheckCircle2 size={15} />Kiểm tra</button>
              <button type="button" className={adminPrimary} disabled={!!saving || !config.can_save || !changed(group.id)} onClick={() => save(group.id)}>{saving === group.id ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}{saving === group.id ? 'Đang lưu…' : 'Lưu thay đổi'}</button></div>
          </div>
          {group.id === 'redis' && <div className="px-5 pb-4"><button type="button" className="text-xs text-slate-400 hover:text-secondary" onClick={async () => { try { setMessage((await api.flushCache()).message); } catch (e) { setError(errorMessage(e)); } }}>Xóa cache của ứng dụng</button></div>}
        </section>}
        {changed() && <div className="flex flex-wrap items-center justify-end gap-2"><button type="button" className={adminButton} disabled={!!saving} onClick={() => { requests.current.invalidateAll(); setDraft({}); setResets([]); setChecks({}); setError(''); setMessage(''); }}>Hủy thay đổi chưa lưu</button>
          <button type="button" className={adminPrimary} disabled={!!saving || !config.can_save} onClick={() => save()}>Lưu tất cả thay đổi</button></div>}
      </div>
    </div>
    <datalist id="registered-collections">{Object.keys(config.available_collections).map(name => <option key={name} value={name} />)}</datalist>
    <datalist id="embedding-models">{Array.from(new Set(Object.values(config.available_collections))).map(model => <option key={model} value={model} />)}</datalist>
  </main>;
}
