'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Plus, Cloud, HardDrive, Check, CheckCircle2, Circle, Copy, Pencil, Trash2, X, RefreshCw, Loader2, ArrowRight, AlertCircle } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import type { AdminConfig, AdminConfigValues, ConfigCheckResult, LLMProfile, LLMProfileInput, LLMProfilesResponse, LLMProvider } from '../../lib/types';
import { adminButton, adminInput, adminPrimary } from './ui';

const providers = { gemini: 'Google Gemini', openai: 'OpenAI', anthropic: 'Anthropic', openrouter: 'OpenRouter', groq: 'Groq', qwen: 'Qwen / Alibaba Cloud', local: 'Local' };
const cloudEndpoints = { openrouter: 'https://openrouter.ai/api/v1', groq: 'https://api.groq.com/openai/v1', qwen: '' };
const providerDocs: Partial<Record<LLMProvider, string>> = {
  gemini: 'https://ai.google.dev/gemini-api/docs/rate-limits', openai: 'https://platform.openai.com/docs/guides/rate-limits',
  anthropic: 'https://docs.anthropic.com/en/api/rate-limits', openrouter: 'https://openrouter.ai/docs/quickstart',
  groq: 'https://console.groq.com/docs/rate-limits', qwen: 'https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope',
};
type ProfileForm = Omit<LLMProfileInput, 'mode'> & { mode: 'cloud' | 'local' | null; api_key: string };
const emptyForm = (): ProfileForm => ({ name: '', mode: null, provider: 'gemini', model: '', base_url: '', local_runtime: 'ollama', api_key_source: 'custom', api_key: '', activate: false });
const needsEndpoint = (current: ProfileForm) => current.mode === 'local' || current.provider in cloudEndpoints;

export function LLMProfilesManager({ config, onChanged, onVerificationChange }: { config: AdminConfig; onChanged: () => Promise<void>; onVerificationChange?: (verified: boolean) => void }) {
  const [data, setData] = useState<LLMProfilesResponse | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filter, setFilter] = useState<'all' | 'cloud' | 'local'>('all');
  const [form, setForm] = useState<ProfileForm | null>(null);
  const [editing, setEditing] = useState<LLMProfile | null>(null);
  const [copySource, setCopySource] = useState<LLMProfile | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [modelsError, setModelsError] = useState('');
  const [loadingModels, setLoadingModels] = useState(false);
  const [manualModel, setManualModel] = useState(false);
  const [check, setCheck] = useState<ConfigCheckResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState('');
  const [formError, setFormError] = useState('');
  const [rowChecks, setRowChecks] = useState<Record<string, ConfigCheckResult | null>>({});
  const [deleting, setDeleting] = useState<LLMProfile | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const formRevision = useRef(0);
  const modelRequest = useRef(0);
  const listRequest = useRef(0);

  useEffect(() => {
    const revision = ++listRequest.current;
    api.listLLMProfiles().then(result => { if (revision === listRequest.current) { setData(result); setRowChecks({}); } })
      .catch(e => { if (revision === listRequest.current) setError(errorMessage(e)); });
    return () => { listRequest.current++; };
  }, [config.config_version]);

  const activeProfile = data?.profiles.find(profile => profile.id === data.active_profile_id);
  const activeVerification = activeProfile && (Object.prototype.hasOwnProperty.call(rowChecks, activeProfile.id) ? rowChecks[activeProfile.id] : activeProfile.verification);
  const activeDraft = !!form && editing?.id === activeProfile?.id;
  const verified = data?.config_version === config.config_version && (activeDraft ? check?.status === 'passed' : activeVerification?.status === 'passed');
  useEffect(() => { onVerificationChange?.(verified); }, [verified, onVerificationChange]);

  useEffect(() => {
    if (form && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [form]);

  useEffect(() => () => { formRevision.current++; modelRequest.current++; }, []);

  function payload(current = form): LLMProfileInput {
    if (!current?.mode) throw new Error('Chọn Local hoặc Cloud trước.');
    const result: LLMProfileInput = { ...current, mode: current.mode, config_version: data?.config_version ?? config.config_version };
    if (!current.api_key) delete result.api_key;
    if (editing) result.profile_id = editing.id;
    else if (copySource) result.copy_key_from = copySource.id;
    return result;
  }

  function defaultEndpoint(provider: LLMProvider) {
    const fromEnvironment = config.environment_values?.[(provider + '_base_url') as keyof AdminConfigValues];
    return typeof fromEnvironment === 'string' ? fromEnvironment : cloudEndpoints[provider as keyof typeof cloudEndpoints] || '';
  }

  async function fetchModels(current = form) {
    if (!current?.mode || (needsEndpoint(current) && !current.base_url.trim())) return;
    const request = ++modelRequest.current;
    setLoadingModels(true); setModelsError('');
    try {
      const response = await api.listProfileModels(payload(current));
      if (request !== modelRequest.current) return;
      setModels(response.models);
      if (!response.models.length) setModelsError('Máy chủ chưa trả về model nào.');
      if (response.models.length === 1 && !current.model) {
        formRevision.current++; setCheck(null);
        setForm(previous => previous ? { ...previous, model: response.models[0] } : previous);
      }
    } catch (e) {
      if (request === modelRequest.current) { setModels([]); setModelsError(errorMessage(e)); }
    } finally { if (request === modelRequest.current) setLoadingModels(false); }
  }

  // Local model choices come from the selected server, never an invented fixed list.
  useEffect(() => {
    if (form?.mode !== 'local' || !form.base_url) return;
    const timer = setTimeout(() => { void fetchModels(form); }, 450);
    return () => { clearTimeout(timer); modelRequest.current++; };
    // Only connection changes require discovery; choosing a model keeps the list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form?.mode, form?.base_url, form?.api_key, form?.api_key_source, form?.local_runtime]);

  function update(changes: Partial<ProfileForm>) {
    formRevision.current++; setCheck(null); setChecking(false); setFormError('');
    if (['mode', 'provider', 'base_url', 'api_key', 'api_key_source'].some(key => key in changes)) {
      modelRequest.current++; setModels([]); setModelsError(''); setLoadingModels(false);
    }
    setForm(previous => previous ? { ...previous, ...changes } : previous);
  }

  function open(profile?: LLMProfile, duplicate = false) {
    formRevision.current++; modelRequest.current++;
    setModels([]); setModelsError(''); setCheck(null); setFormError(''); setChecking(false); setLoadingModels(false); setManualModel(false);
    setEditing(profile && !duplicate && !profile.read_only ? profile : null);
    setCopySource(profile && duplicate && !profile.read_only ? profile : null);
    setForm(profile ? { name: duplicate || profile.read_only ? profile.name + ' · bản riêng' : profile.name,
      mode: profile.mode, provider: profile.provider, model: profile.model, base_url: profile.base_url,
      local_runtime: profile.local_runtime, api_key_source: profile.api_key_source, api_key: '', activate: false }
      : emptyForm());
  }

  function close() {
    if (busy === 'save') return;
    formRevision.current++; modelRequest.current++;
    dialog.current?.close(); setForm(null); setEditing(null); setChecking(false); setLoadingModels(false);
  }

  async function runCheck() {
    const revision = ++formRevision.current;
    setChecking(true); setCheck(null); setFormError('');
    try {
      const result = await api.checkLLMProfile(payload());
      if (revision === formRevision.current) setCheck(result);
    } catch (e) { if (revision === formRevision.current) setFormError(errorMessage(e)); }
    finally { if (revision === formRevision.current) setChecking(false); }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy('save'); setFormError('');
    try {
      const result = await api.saveLLMProfile(payload(), editing?.id);
      listRequest.current++; setData(result);
      if (editing) setRowChecks(previous => { const next = { ...previous }; delete next[editing.id]; return next; });
      dialog.current?.close(); setForm(null); setEditing(null); modelRequest.current++; formRevision.current++;
      setNotice('Đã lưu cấu hình LLM.');
      await onChanged();
    } catch (e) { setFormError(errorMessage(e)); }
    finally { setBusy(''); }
  }

  async function activate(profile: LLMProfile) {
    if (!data) return;
    setBusy(profile.id); setError(''); setNotice('');
    try {
      const result = await api.activateLLMProfile(profile.id, data.config_version);
      listRequest.current++; setData(result); setNotice('Đang sử dụng ' + profile.name + '.');
      setRowChecks(previous => { const next = { ...previous }; delete next[profile.id]; return next; });
      await onChanged();
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(''); }
  }

  async function checkRow(profile: LLMProfile) {
    const revision = listRequest.current;
    setBusy('check-' + profile.id); setError('');
    setRowChecks(previous => ({ ...previous, [profile.id]: null }));
    try {
      const result = await api.checkLLMProfile({ ...profile, profile_id: profile.id });
      if (revision === listRequest.current) setRowChecks(previous => ({ ...previous, [profile.id]: result }));
    } catch (e) { if (revision === listRequest.current) setError(errorMessage(e)); }
    finally { setBusy(''); }
  }

  async function remove(profile: LLMProfile) {
    if (!data) return;
    setBusy('delete'); setError('');
    try {
      const result = await api.deleteLLMProfile(profile.id, data.config_version);
      listRequest.current++; setData(result); setDeleting(null); setNotice('Đã xóa cấu hình ' + profile.name + '.');
      await onChanged();
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(''); }
  }

  const rows = data?.profiles.filter(profile => filter === 'all' || profile.mode === filter) || [];
  const keyOwner = editing || copySource;
  const hasStoredKey = !!keyOwner?.key_configured && keyOwner.api_key_source === 'custom' && keyOwner.provider === form?.provider;
  const hasDraftKey = !!form?.api_key || hasStoredKey;
  const canCheck = !!form?.mode && !!form.model.trim() && (!needsEndpoint(form) || !!form.base_url.trim()) &&
    (form.api_key_source !== 'custom' || hasDraftKey);

  return <section className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
    <div className="flex items-start justify-between gap-4 px-5 py-5 border-b border-slate-100">
      <div><h2 className="text-base font-semibold">Quản lý cấu hình LLM</h2>
        <p className="text-sm text-slate-500 mt-1">Thêm nhiều kết nối và chọn cấu hình dùng cho trợ lý.</p></div>
      <button type="button" className={adminPrimary + ' shrink-0'} disabled={!!busy} onClick={() => open()}><Plus size={16} />Thêm cấu hình</button>
    </div>
    <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100 gap-3">
      <div className="flex p-1 rounded-xl bg-slate-100 gap-1">{(['all', 'cloud', 'local'] as const).map(kind =>
        <button key={kind} type="button" onClick={() => setFilter(kind)} className={'px-3 py-1 rounded-lg text-xs font-medium ' + (filter === kind ? 'bg-white shadow-sm text-on-surface' : 'text-slate-500 hover:text-slate-800')}>
          {{ all: 'Tất cả', cloud: 'Cloud', local: 'Local' }[kind]}</button>)}</div>
      <span className="text-xs text-slate-400">{data ? data.profiles.length + ' cấu hình' : 'Đang tải…'}</span>
    </div>
    {(error || notice) && <div role={error ? 'alert' : 'status'} className={'mx-5 mt-4 px-3 py-2 rounded-xl text-sm ' + (error ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700')}>{error || notice}</div>}
    {!data && !error && <p className="p-6 text-sm text-slate-500 flex items-center gap-2"><Loader2 size={16} className="animate-spin" />Đang tải cấu hình…</p>}
    {data && <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
      <table className="w-full text-sm text-left"><thead className="bg-slate-50/70 text-slate-500 text-xs">
        <tr><th className="w-10 pl-5 pr-0 py-3"><span className="sr-only">Kiểm tra kết nối</span></th><th className="font-medium px-3 py-3">Tên cấu hình</th><th className="font-medium px-3 py-3">Model</th><th className="font-medium px-3 py-3">Trạng thái</th><th className="font-medium px-5 py-3 text-right">Thao tác</th></tr>
      </thead><tbody>{rows.map(profile => {
        const active = profile.id === data.active_profile_id;
        const verification = Object.prototype.hasOwnProperty.call(rowChecks, profile.id) ? rowChecks[profile.id] : profile.verification;
        const Icon = profile.mode === 'local' ? HardDrive : Cloud;
        return <tr key={profile.id} className={'border-t border-slate-100 ' + (active ? 'bg-secondary/[0.025]' : '')}>
          <td className="pl-5 pr-0 py-4">{verification?.status === 'passed' && <CheckCircle2 size={16} className="text-emerald-600" role="img" aria-label="Đã kiểm tra thành công" />}</td>
          <td className="px-3 py-4"><div className="flex items-center gap-3 min-w-[170px]">
            <span className={'p-2 rounded-xl ' + (profile.mode === 'local' ? 'bg-slate-100 text-slate-600' : 'bg-secondary/5 text-secondary')}><Icon size={17} aria-hidden="true" /></span>
            <div><p className="font-medium">{profile.name}</p><p className="text-xs text-slate-500 mt-0.5">{profile.mode === 'local' ? 'Local' : 'Cloud'} · {profile.mode === 'local' ? ({ ollama: 'Ollama', lmstudio: 'LM Studio', compatible: 'API tương thích' }[profile.local_runtime]) : providers[profile.provider]}</p></div>
          </div></td>
          <td className="px-3 py-4 max-w-[190px]"><p className="truncate" title={profile.model}>{profile.model || 'Chưa chọn model'}</p>
            <p className="text-xs text-slate-400 mt-0.5">{profile.api_key_source === 'none' ? 'Không dùng key' : profile.key_configured ? profile.api_key_source === 'environment' ? 'Key từ môi trường' : 'Key riêng' : 'Chưa có key'}</p></td>
          <td className="px-3 py-4 whitespace-nowrap"><div className="flex flex-col items-start gap-1.5">
            {active && <span className="inline-flex gap-1 items-center rounded-full px-2 py-0.5 bg-secondary/10 text-secondary text-[11px] font-medium"><Circle size={7} fill="currentColor" />Đang sử dụng</span>}
            <span title={verification?.checked_at ? verification.message + ' · ' + new Date(verification.checked_at).toLocaleString('vi-VN') : undefined}
              className={'inline-flex items-center gap-1 text-xs ' + (verification?.status === 'passed' ? 'text-emerald-600' : verification ? 'text-red-600' : 'text-slate-400')}>
              {verification?.status === 'passed' ? <CheckCircle2 size={13} /> : <Circle size={12} />}
              {verification?.status === 'passed' ? 'Đã kiểm tra' : verification ? 'Kiểm tra thất bại' : 'Chưa kiểm tra'}</span>
          </div></td>
          <td className="px-5 py-4"><div className="flex items-center justify-end gap-1.5 whitespace-nowrap">
            {!active && <button className={adminButton + ' h-8 text-xs'} disabled={!!busy || !data.can_save} onClick={() => activate(profile)} title="Kiểm tra và chuyển sang cấu hình này">
              {busy === profile.id ? <Loader2 size={13} className="animate-spin" /> : <ArrowRight size={13} />}Dùng</button>}
            <button className="p-2 text-slate-400 hover:text-emerald-600 disabled:opacity-30" disabled={!!busy} title={'Kiểm tra ' + profile.name} aria-label={'Kiểm tra ' + profile.name} onClick={() => checkRow(profile)}>
              {busy === 'check-' + profile.id ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}</button>
            <button className="p-2 text-slate-400 hover:text-secondary" title={profile.read_only ? 'Tạo bản cấu hình riêng' : 'Chỉnh sửa'} aria-label={'Chỉnh sửa ' + profile.name} disabled={!!busy} onClick={() => open(profile, profile.read_only)}>{profile.read_only ? <Copy size={15} /> : <Pencil size={15} />}</button>
            {!profile.read_only && <button className="p-2 text-slate-400 hover:text-secondary disabled:opacity-30" title="Nhân bản (dùng lại API key)" aria-label={'Nhân bản ' + profile.name} disabled={!!busy} onClick={() => open(profile, true)}><Copy size={15} /></button>}
            {!profile.read_only && <button className="p-2 text-slate-400 hover:text-red-600 disabled:opacity-25" title={active ? 'Chọn cấu hình khác trước khi xóa' : 'Xóa cấu hình'} aria-label={'Xóa ' + profile.name}
              disabled={active || !!busy || !data.can_save} onClick={() => setDeleting(profile)}><Trash2 size={15} /></button>}
          </div></td>
        </tr>;
      })}</tbody></table>
      {!rows.length && <p className="px-5 py-10 text-center text-slate-400 text-sm">Chưa có cấu hình {filter === 'all' ? '' : filter === 'local' ? 'Local' : 'Cloud'}. Chọn “Thêm cấu hình” để bắt đầu.</p>}
    </div>}
    <div className="px-5 py-3 border-t border-slate-100 text-xs text-slate-400">Mỗi kết nối lưu riêng model và API key. Kiểm tra LLM sử dụng một lượt gọi API.</div>

    {form && <dialog ref={dialog} aria-labelledby="llm-editor-title" className="w-[calc(100%-32px)] max-w-xl rounded-2xl border-0 p-0 bg-white shadow-2xl text-on-surface max-h-[90vh]" onCancel={event => { event.preventDefault(); close(); }}>
      <form onSubmit={save}>
        <div className="px-6 py-4 flex items-center justify-between border-b border-slate-100 sticky top-0 bg-white z-10">
          <div><h3 id="llm-editor-title" className="font-semibold text-base">{editing ? 'Chỉnh sửa cấu hình LLM' : 'Thêm cấu hình LLM'}</h3>
            <p className="text-xs text-slate-500 mt-0.5">Chọn nơi chạy, kết nối và model bạn muốn sử dụng.</p></div>
          <button type="button" className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100" aria-label="Đóng hộp thoại" onClick={close} disabled={busy === 'save'}><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <fieldset disabled={busy === 'save'}><legend className="text-sm font-medium mb-2">Nơi chạy model</legend>
            <div className="grid grid-cols-2 gap-3">{(['local', 'cloud'] as const).map(mode => { const Icon = mode === 'local' ? HardDrive : Cloud; return <button key={mode} type="button" aria-pressed={form.mode === mode}
              onClick={() => { if (form.mode === mode) return; setManualModel(false); update({ mode, provider: mode === 'local' ? 'local' : 'gemini', model: '', api_key: '', name: form.name || (mode === 'local' ? 'LLM local' : 'LLM cloud'),
                base_url: mode === 'local' ? 'http://127.0.0.1:11434/v1' : '', local_runtime: 'ollama', api_key_source: mode === 'local' ? 'none' : 'custom' }); }}
              className={'flex items-center gap-3 p-3 rounded-xl border text-left transition-colors ' + (form.mode === mode ? 'border-secondary bg-secondary/5 ring-1 ring-secondary' : 'border-slate-200 hover:border-slate-300')}>
              <Icon size={19} className={form.mode === mode ? 'text-secondary' : 'text-slate-400'} /><span><span className="block text-sm font-semibold">{mode === 'local' ? 'Local' : 'Cloud'}</span>
                <span className="block text-[11px] text-slate-500">{mode === 'local' ? 'Model trên máy chủ của bạn' : 'Gemini, OpenRouter, Groq, Qwen…'}</span></span>
              {form.mode === mode && <Check size={15} className="ml-auto text-secondary" />}</button>; })}</div>
          </fieldset>
          {form.mode && <fieldset disabled={busy === 'save'} className="space-y-4">
            <div className="grid grid-cols-2 gap-3"><label className="block text-sm font-medium">Tên cấu hình<input className={adminInput + ' mt-1.5'} required maxLength={100} value={form.name} onChange={e => update({ name: e.target.value })} placeholder="Ví dụ: Gemini cá nhân" /></label>
              {form.mode === 'cloud' ? <label className="block text-sm font-medium">Nhà cung cấp<select className={adminInput + ' mt-1.5'} value={form.provider}
                onChange={e => { const provider = e.target.value as LLMProvider; setManualModel(false); update({ provider, model: '', api_key: '', base_url: defaultEndpoint(provider) }); }}>
                {Object.entries(providers).filter(([id]) => id !== 'local').map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
                : <label className="block text-sm font-medium">Máy chủ local<select className={adminInput + ' mt-1.5'} value={form.local_runtime} onChange={e => update({ local_runtime: e.target.value as LLMProfileInput['local_runtime'], model: '',
                  base_url: e.target.value === 'ollama' ? 'http://127.0.0.1:11434/v1' : e.target.value === 'lmstudio' ? 'http://127.0.0.1:1234/v1' : '' })}>
                  <option value="ollama">Ollama</option><option value="lmstudio">LM Studio</option><option value="compatible">API tương thích OpenAI khác</option></select></label>}
            </div>
            {form.mode === 'local' && <label className="block text-sm font-medium">Địa chỉ máy chủ<input className={adminInput + ' mt-1.5'} required type="url" value={form.base_url} onChange={e => update({ base_url: e.target.value })} placeholder="http://127.0.0.1:11434/v1" />
              <span className="block mt-1 text-xs font-normal text-slate-400">Địa chỉ được truy cập từ máy chạy backend. Danh sách model tự cập nhật theo máy chủ.</span></label>}
            {form.mode === 'cloud' && needsEndpoint(form) && <label className="block text-sm font-medium">Địa chỉ API (Base URL)<input className={adminInput + ' mt-1.5'} required type="url" value={form.base_url} onChange={e => update({ base_url: e.target.value })}
              placeholder={form.provider === 'qwen' ? 'https://<workspace-id>.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1' : defaultEndpoint(form.provider)} />
              <span className="block mt-1 text-xs font-normal text-slate-400">{form.provider === 'qwen' ? 'Dán Base URL từ Alibaba Cloud Model Studio, cùng workspace và region với API key.' : 'Dùng địa chỉ API của nhà cung cấp, không thêm /chat/completions.'}</span></label>}
            <div className="grid grid-cols-2 gap-3"><label className="block text-sm font-medium">Xác thực<select className={adminInput + ' mt-1.5'} value={form.api_key_source} onChange={e => update({ api_key_source: e.target.value as LLMProfileInput['api_key_source'] })}>
              {form.mode === 'local' && <option value="none">Không cần API key</option>}<option value="custom">API key riêng</option><option value="environment">API key từ môi trường</option></select></label>
              {form.api_key_source === 'custom' && <label className="block text-sm font-medium">API key<input type="password" autoComplete="new-password" className={adminInput + ' mt-1.5'} value={form.api_key} onChange={e => update({ api_key: e.target.value })}
                placeholder={hasStoredKey ? (editing ? 'Để trống để giữ key đã lưu' : 'Để trống để dùng key của bản gốc') : 'Nhập API key'} /></label>}
            </div>
            <div><div className="flex items-center justify-between gap-2 mb-1.5"><label htmlFor="llm-profile-model" className="text-sm font-medium">{form.mode === 'local' ? 'Model trên máy chủ' : 'Model'}</label>
              <button type="button" className="inline-flex items-center gap-1 text-xs text-secondary hover:underline disabled:opacity-40" disabled={loadingModels || (form.api_key_source === 'custom' && !hasDraftKey) || (needsEndpoint(form) && !form.base_url.trim())} onClick={() => fetchModels()}>
                <RefreshCw size={12} className={loadingModels ? 'animate-spin' : ''} />{loadingModels ? 'Đang tải…' : 'Tải danh sách'}</button></div>
              {manualModel ? <input id="llm-profile-model" required className={adminInput} value={form.model} onChange={e => update({ model: e.target.value })} placeholder="Tên model chính xác" />
                : <select id="llm-profile-model" required className={adminInput} value={form.model} onChange={e => update({ model: e.target.value })} disabled={loadingModels}>
                  <option value="">{loadingModels ? 'Đang lấy model từ máy chủ…' : models.length ? 'Chọn model' : 'Chưa có danh sách model'}</option>
                  {form.model && !models.includes(form.model) && <option value={form.model}>{form.model} · đang lưu</option>}
                  {models.map(model => <option key={model} value={model}>{model}</option>)}
                </select>}
              <div className="flex justify-between items-start gap-3 mt-1.5"><span className="text-xs text-slate-400">{modelsError || (models.length ? `${models.length} model do máy chủ cung cấp` : form.mode === 'local' ? 'Chạy server local để xem các model có sẵn.' : 'Nhập key rồi tải danh sách model.')}</span>
                <button type="button" className="text-xs text-secondary hover:underline shrink-0" onClick={() => setManualModel(!manualModel)}>{manualModel ? 'Chọn từ danh sách' : 'Nhập thủ công'}</button></div>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={!!form.activate} onChange={e => update({ activate: e.target.checked })} className="accent-secondary" />Sử dụng cấu hình này sau khi lưu</label>
            {form.mode === 'cloud' && <p className="text-xs text-slate-400">Model chạy trên cloud; không cần tải về máy. Kiểm tra sử dụng một lượt gọi API. <a className="text-secondary hover:underline" target="_blank" rel="noreferrer" href={providerDocs[form.provider]}>Hướng dẫn nhà cung cấp</a></p>}
          </fieldset>}
          {(check || checking) && <p role="status" className={'flex items-center gap-2 rounded-xl px-3 py-2 text-sm ' + (check?.status === 'passed' ? 'bg-emerald-50 text-emerald-700' : checking ? 'bg-slate-50 text-slate-500' : 'bg-red-50 text-red-700')}>
            {checking ? <Loader2 size={15} className="animate-spin" /> : check?.status === 'passed' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}{checking ? 'Đang kiểm tra model…' : check?.message}</p>}
          {formError && <p role="alert" className="text-sm text-red-600">{formError}</p>}
          {!config.can_save && form.mode && <p className="text-xs text-slate-400">Bạn có thể kiểm tra kết nối. Cần PostgreSQL để lưu cấu hình.</p>}
          {!config.encryption_ready && form.api_key_source === 'custom' && form.mode && <p className="text-xs text-slate-400">Lưu key riêng cần khóa mã hóa CONFIG_ENCRYPTION_KEY trên backend.</p>}
        </div>
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between gap-2 sticky bottom-0 bg-white">
          <button type="button" className={adminButton} onClick={close} disabled={busy === 'save'}>Hủy</button>
          <div className="flex gap-2"><button type="button" className={adminButton} disabled={!canCheck || checking || !!busy} onClick={runCheck}>{checking ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}Kiểm tra</button>
            <button type="submit" className={adminPrimary} disabled={!canCheck || !form.name.trim() || !!busy || !config.can_save || (form.api_key_source === 'custom' && !config.encryption_ready)}>
              {busy === 'save' && <Loader2 size={15} className="animate-spin" />}{busy === 'save' ? 'Đang kiểm tra và lưu…' : form.activate ? 'Lưu và sử dụng' : 'Lưu cấu hình'}</button></div>
        </div>
      </form>
    </dialog>}
    {deleting && <div role="alertdialog" aria-modal="true" aria-labelledby="delete-llm-title" className="fixed inset-0 z-[60] bg-slate-900/40 grid place-items-center p-4">
      <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-xl"><h3 id="delete-llm-title" className="font-semibold">Xóa cấu hình LLM?</h3>
        <p className="text-sm text-slate-500 mt-2">{deleting.name}</p><div className="flex justify-end gap-2 mt-5"><button className={adminButton} disabled={!!busy} onClick={() => setDeleting(null)}>Hủy</button>
          <button className={adminPrimary + ' !bg-red-600'} disabled={!!busy} onClick={() => remove(deleting)}>Xóa cấu hình</button></div></div>
    </div>}
  </section>;
}
