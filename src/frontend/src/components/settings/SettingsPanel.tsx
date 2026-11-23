'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Sparkles, Network, Database, GitBranch, FolderOpen, Layers, ScanText, Info, Settings2, RotateCcw, Save, CheckCircle2, Loader2, ChevronDown, AlertCircle, Search, X } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import type { AdminConfig, AdminConfigValues, AdminSecretValues, ConfigField, ConfigService, SystemStats } from '../../lib/types';
import { buildConfigUpdate, configGroups, createConfigRequestTracker, isConfigVerified, ConfigCheckState, ConfigDraft, ConfigFieldSpec } from '../../lib/admin-config';
import { LLMProfilesManager } from '../admin/LLMProfilesManager';
import { PostgresSettings } from '../admin/PostgresSettings';
import { adminInput, adminButton, adminPrimary } from '../admin/ui';
import styles from './settings.module.css';

const icons = { llm: Sparkles, embedding: Network, qdrant: Database, neo4j: GitBranch, r2: FolderOpen, redis: Layers, ocr: ScanText };
const labels = { llm: 'Mô hình LLM', embedding: 'Embedding', qdrant: 'Qdrant', neo4j: 'Neo4j', r2: 'Lưu trữ file', redis: 'Redis cache', ocr: 'OCR và upload' };
const own = (object: object, key: string) => Object.prototype.hasOwnProperty.call(object, key);

export type SettingsSection = ConfigService | 'postgres' | 'info';
type Section = SettingsSection;

export const SETTINGS_SECTIONS: SettingsSection[] = ['llm', 'postgres', 'embedding', 'qdrant', 'neo4j', 'r2', 'redis', 'ocr', 'info'];

interface SettingsPanelProps {
  /** `modal` fills its dialog; `page` draws its own card for the /admin route. */
  variant?: 'page' | 'modal';
  initialSection?: SettingsSection;
  onSectionChange?: (section: SettingsSection) => void;
  onClose?: () => void;
}

export function SettingsPanel({ variant = 'page', initialSection = 'llm', onSectionChange, onClose }: SettingsPanelProps) {
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [selected, setSelected] = useState<Section>(initialSection);
  const [search, setSearch] = useState('');
  const [draft, setDraft] = useState<ConfigDraft>({});
  const [resets, setResets] = useState<ConfigField[]>([]);
  const [checks, setChecks] = useState<Partial<Record<ConfigService, ConfigCheckState>>>({});
  const [llmVerified, setLLMVerified] = useState(false);
  const [postgresVerified, setPostgresVerified] = useState(false);
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

  useEffect(() => { setSelected(initialSection); }, [initialSection]);

  function select(section: Section) {
    setSelected(section);
    onSectionChange?.(section);
  }

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
    return <div key={field.key} className="py-4 grid gap-x-6 gap-y-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,320px)] min-w-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <label htmlFor={id} className="text-[13.5px] font-medium text-ink">{field.label}</label>
          <span className={'text-[11px] ' + (pending ? 'text-secondary' : 'text-muted')}>{pending ? resets.includes(field.key) ? 'Dùng môi trường' : 'Chưa lưu' : sourceLabel}</span>
          <button type="button" disabled={!!saving || resets.includes(field.key)} className="p-1 rounded text-muted hover:text-secondary disabled:opacity-30" title="Dùng giá trị từ môi trường" aria-label={'Dùng giá trị môi trường: ' + field.label} onClick={() => reset(field.key)}><RotateCcw size={12} /></button>
        </div>
        {field.hint && <p className="mt-0.5 text-[12.5px] leading-5 text-ink-3">{field.hint}</p>}
      </div>
      <div className="min-w-0 space-y-1">{control}</div>
    </div>;
  }

  const query = search.trim().toLowerCase();
  const matches = (label: string, fields: ConfigFieldSpec[] = []) =>
    !query || label.toLowerCase().includes(query) || fields.some(item => item.label.toLowerCase().includes(query));
  const groupOf = (id: ConfigService) => configGroups.find(item => item.id === id)!;

  function navItem(id: Section, label: string, Icon: typeof Sparkles, isVerified: boolean, dirty: boolean) {
    return <div key={id} className="flex items-center gap-1.5 shrink-0">
      <span className="inline-flex w-4 shrink-0 items-center justify-center">{isVerified && <CheckCircle2 size={15} className="text-emerald-600" role="img" aria-label="Đã kiểm tra thành công" />}</span>
      <button type="button" aria-current={selected === id ? 'page' : undefined} onClick={() => { select(id); setError(''); }}
        className={'flex flex-1 min-w-0 items-center gap-2.5 px-2.5 py-2 rounded-xl text-[13.5px] text-left whitespace-nowrap transition-colors ' + (selected === id ? 'bg-stone-2 text-ink font-medium' : 'text-ink-3 hover:bg-stone hover:text-ink')}>
        <Icon size={16} className="shrink-0" aria-hidden="true" />{label}{dirty && <span className="w-1.5 h-1.5 bg-secondary rounded-full ml-auto" title="Có thay đổi chưa lưu" />}</button>
    </div>;
  }

  const frame = variant === 'modal'
    ? 'h-full'
    : 'h-[calc(100vh-24px)] my-3 mr-3 bg-white rounded-2xl border border-ink/8 overflow-hidden';

  if (!config) return <div className={styles.page + ' ' + frame + ' flex items-center justify-center text-[13.5px] text-ink-3'} role={error ? 'alert' : 'status'}>{error || 'Đang tải cấu hình hệ thống…'}</div>;
  const group = configGroups.find(item => item.id === selected);
  const state = group && checks[group.id], result = state?.result;
  const statuses = [
    ['PostgreSQL', config.postgres_status], ['Qdrant', stats?.vector_db_status], ['Neo4j', stats?.graph_db_status], ['Redis', stats?.redis_status],
  ];
  const connections: Partial<Record<ConfigService, string>> = {
    qdrant: stats?.vector_db_status, neo4j: stats?.graph_db_status, redis: stats?.redis_status,
  };
  const sectionTitle = selected === 'info' ? 'Thông tin hệ thống' : selected === 'postgres' ? 'PostgreSQL' : labels[selected];
  const sectionHint = selected === 'info' ? 'Các thiết lập khởi động được quản lý qua môi trường.'
    : selected === 'postgres' ? 'Cơ sở dữ liệu lưu phiên hỏi đáp, cấu hình và tác vụ.' : group?.hint;
  const navGroups: Array<{ title: string; items: Section[] }> = [
    { title: 'Trợ lý', items: ['llm'] },
    { title: 'Dữ liệu & chỉ mục', items: ['postgres', 'embedding', 'qdrant', 'neo4j', 'r2', 'redis'] },
    { title: 'Xử lý tài liệu', items: ['ocr'] },
  ];

  return <div className={styles.page + ' ' + frame + ' flex flex-col md:flex-row min-h-0 text-ink'}>
    {/* Settings navigation */}
    <aside className="md:w-[240px] shrink-0 border-b md:border-b-0 md:border-r border-ink/8 bg-paper flex flex-col min-h-0">
      <div className="px-4 pt-4 pb-3 flex items-center gap-2">
        <Settings2 size={18} className="text-secondary" />
        <h1 id="settings-title" className="text-[16px] font-semibold tracking-tight">Cấu hình hệ thống</h1>
      </div>
      <div className="px-3 pb-2 relative">
        <Search size={14} className="text-muted absolute left-6 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm cấu hình…" aria-label="Tìm cấu hình"
          className="w-full pl-8 pr-3 py-1.5 text-[12.5px] bg-white border border-ink/8 rounded-xl placeholder:text-muted focus:outline-none focus:border-secondary/40" />
      </div>
      <nav aria-label="Nhóm cấu hình" className="flex md:flex-col gap-0.5 overflow-x-auto md:overflow-y-auto legal-scroll px-2 pb-3 min-h-0">
        {navGroups.map(section => {
          const items = section.items.filter(id => id === 'postgres' ? matches('PostgreSQL') : matches(labels[id as ConfigService], groupOf(id as ConfigService).fields));
          if (!items.length) return null;
          return <React.Fragment key={section.title}>
            <div className="hidden md:block px-2.5 pt-3 pb-1 text-[11px] font-medium text-muted">{section.title}</div>
            {items.map(id => id === 'postgres'
              ? navItem('postgres', 'PostgreSQL', Database, postgresVerified, false)
              : navItem(id, labels[id as ConfigService], icons[id as ConfigService],
                id === 'llm' ? llmVerified : isConfigVerified(checks[id as ConfigService], connections[id as ConfigService]),
                id !== 'llm' && changed(id as ConfigService)))}
          </React.Fragment>;
        })}
        {matches('Thông tin hệ thống') && <>
          <div className="hidden md:block h-px bg-ink/8 my-2 mx-2.5" />
          {navItem('info', 'Thông tin hệ thống', Info, false, false)}
        </>}
      </nav>
    </aside>

    {/* Section content */}
    <section className="flex-1 min-w-0 flex flex-col min-h-0">
      <header className="px-6 pt-5 pb-4 border-b border-ink/6 flex items-start justify-between gap-4 shrink-0">
        <div className="min-w-0">
          <h2 id="settings-group-heading" className="text-[17px] font-semibold tracking-tight">{sectionTitle}</h2>
          {sectionHint && <p className="mt-1 text-[12.5px] leading-5 text-ink-3 max-w-[70ch]">{sectionHint}</p>}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2.5 text-[11.5px] text-ink-3">{statuses.map(([name, status]) => <span key={name} title={status || 'Chưa kiểm tra'} className="inline-flex items-center gap-1.5"><span className={'w-1.5 h-1.5 rounded-full ' + (status === 'connected' ? 'bg-emerald-500' : status === 'unavailable' ? 'bg-red-400' : 'bg-stone-3')} />{name} <span className="text-muted">{status === 'connected' ? 'Đã kết nối' : status === 'unavailable' ? 'Không kết nối' : status === 'disabled' ? 'Đang tắt' : 'Chưa kiểm tra'}</span></span>)}</div>
        </div>
        {onClose && <button type="button" onClick={onClose} aria-label="Đóng cấu hình" className="p-1.5 rounded-lg text-ink-3 hover:text-ink hover:bg-stone shrink-0"><X size={18} /></button>}
      </header>

      <div className="flex-1 overflow-y-auto legal-scroll px-6 py-5 space-y-4 min-h-0">
        {config.configuration_error && <p role="alert" className="p-3 bg-red-50 text-red-700 rounded-xl text-sm">{config.configuration_error}</p>}
        {(!config.can_save || !config.encryption_ready) && <details className="px-4 py-3 rounded-xl border border-[#9A6B2F]/25 bg-[#FAF7F0] text-sm text-[#473822]">
          <summary className="cursor-pointer font-medium">Cần hoàn tất thiết lập để lưu cấu hình{!config.can_save && !config.encryption_ready ? ' · PostgreSQL và khóa mã hóa' : !config.can_save ? ' · PostgreSQL' : ' · Khóa mã hóa'}</summary>
          <p className="text-xs mt-2 leading-5">Bạn vẫn có thể thêm bản nháp và kiểm tra kết nối. {!config.can_save && 'Thiết lập DATABASE_URL và khởi động lại backend để lưu. '}{!config.encryption_ready && 'Thiết lập CONFIG_ENCRYPTION_KEY để lưu API key riêng.'}</p>
          {!config.can_save && <button type="button" className="mt-2 text-xs font-medium text-secondary hover:underline" onClick={() => select('postgres')}>Mở cấu hình PostgreSQL</button>}
        </details>}
        {(error || message) && <p role={error ? 'alert' : 'status'} className={'px-4 py-3 rounded-xl text-sm ' + (error ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700')}>{error || message}</p>}

        <div hidden={selected !== 'llm'}><LLMProfilesManager config={config} onChanged={refreshConfig} onVerificationChange={setLLMVerified} /></div>
        <div hidden={selected !== 'postgres'}><PostgresSettings onVerificationChange={setPostgresVerified} onApplied={async () => { requests.current.invalidateAll(); setChecks({}); await refreshConfig(); }} /></div>
        {selected === 'info' ? <dl className="divide-y divide-ink/6 text-[13.5px]">{[
            ['PostgreSQL', config.postgres_endpoint || 'Chưa cấu hình DATABASE_URL'], ['Dataset', config.dataset_id], ['Phiên bản cấu hình', String(config.config_version)],
            ['Chế độ demo', config.demo_mode ? 'Bật' : 'Tắt'], ['Phiên tra cứu đã lưu', String(stats?.active_sessions_count ?? 'Chưa có số liệu')],
            ['Thư mục upload', config.startup.upload_dir], ['Thư mục runtime', config.startup.interim_dir], ['CORS', config.startup.cors_origins.join(', ')],
          ].map(([label, content]) => <div key={label} className="py-3 grid sm:grid-cols-[200px_1fr] gap-2"><dt className="text-ink-3">{label}</dt><dd className="break-all font-mono text-[12.5px]">{content}</dd></div>)}
          <p className="pt-4 text-xs text-muted">DATABASE_URL, CONFIG_ENCRYPTION_KEY, JWT, CORS và BACKEND_ORIGIN cần khởi động lại dịch vụ khi thay đổi.</p>
        </dl> : group && selected !== 'llm' && <div aria-labelledby="settings-group-title">
          <h3 id="settings-group-title" className="sr-only">{group.title}</h3>
          <div className="divide-y divide-ink/6 -mt-2">{group.fields.filter(field => !field.advanced).map(fieldControl)}</div>
          {group.fields.some(field => field.advanced) && <details className="mt-2 border-t border-ink/6 pt-3"><summary className="flex items-center gap-1 cursor-pointer text-[13px] text-ink-3 font-medium"><ChevronDown size={14} />Tùy chọn nâng cao</summary>
            <div className="divide-y divide-ink/6">{group.fields.filter(field => field.advanced).map(fieldControl)}</div></details>}
          {group.id === 'redis' && <button type="button" className="mt-4 text-xs text-muted hover:text-secondary" onClick={async () => { try { setMessage((await api.flushCache()).message); } catch (e) { setError(errorMessage(e)); } }}>Xóa cache của ứng dụng</button>}
        </div>}
      </div>

      {(group && selected !== 'llm' && selected !== 'info' || changed()) && <footer className="px-6 py-3 border-t border-ink/8 bg-paper flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
        {group && selected !== 'llm' && selected !== 'info' ? <div aria-live="polite" className={'text-xs ' + (result?.status === 'passed' ? 'text-emerald-700' : state?.error || result?.status === 'failed' || result?.status === 'not_configured' ? 'text-red-600' : 'text-muted')}>
          <p className="flex items-center gap-1.5">{state?.checking ? <Loader2 size={14} className="animate-spin" /> : result?.status === 'passed' ? <CheckCircle2 size={14} /> : state?.error ? <AlertCircle size={14} /> : null}
            {state?.checking ? 'Đang kiểm tra…' : state?.error || result?.message || 'Chưa kiểm tra thay đổi'}</p>
          {result && <p className="mt-1 text-[11px] text-muted">{new Date(result.checked_at).toLocaleString('vi-VN')} · {result.latency_ms} ms{result.details.dimensions ? ` · ${result.details.dimensions} chiều` : ''}</p>}
        </div> : <span />}
        <div className="flex flex-wrap gap-2 shrink-0 justify-end">
          {group && selected !== 'llm' && selected !== 'info' && <>
            <button type="button" className={adminButton} disabled={!!saving || state?.checking || !!config.configuration_error} onClick={() => check(group.id)}><CheckCircle2 size={15} />Kiểm tra</button>
            <button type="button" className={adminPrimary} disabled={!!saving || !config.can_save || !changed(group.id)} onClick={() => save(group.id)}>{saving === group.id ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}{saving === group.id ? 'Đang lưu…' : 'Lưu thay đổi'}</button>
          </>}
          {changed() && <>
            <button type="button" className={adminButton} disabled={!!saving} onClick={() => { requests.current.invalidateAll(); setDraft({}); setResets([]); setChecks({}); setError(''); setMessage(''); }}>Hủy thay đổi chưa lưu</button>
            <button type="button" className={adminPrimary} disabled={!!saving || !config.can_save} onClick={() => save()}>Lưu tất cả thay đổi</button>
          </>}
        </div>
      </footer>}
    </section>
    <datalist id="registered-collections">{Object.keys(config.available_collections).map(name => <option key={name} value={name} />)}</datalist>
    <datalist id="embedding-models">{Array.from(new Set(Object.values(config.available_collections))).map(model => <option key={model} value={model} />)}</datalist>
  </div>;
}
