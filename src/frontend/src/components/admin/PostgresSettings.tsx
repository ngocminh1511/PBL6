'use client';

import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Loader2, Save, Eye, EyeOff, AlertCircle, Info } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import type { PostgresConfig, PostgresConfigInput, PostgresCheckResult } from '../../lib/types';
import { adminInput, adminButton, adminPrimary } from './ui';

export function PostgresSettings({ onApplied, onVerificationChange }: { onApplied?: () => Promise<void>; onVerificationChange?: (verified: boolean) => void }) {
  const [config, setConfig] = useState<PostgresConfig | null>(null);
  const [mode, setMode] = useState<'url' | 'fields'>('url');
  const [url, setUrl] = useState('');
  const [fields, setFields] = useState({ host: '', port: 5432, database: '', username: '', password: '', sslmode: 'require' as PostgresConfigInput['sslmode'] });
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [result, setResult] = useState<PostgresCheckResult | null>(null);
  const [busy, setBusy] = useState<'check' | 'save' | 'apply' | null>(null);
  const [verified, setVerified] = useState(false);
  const revision = useRef(0);

  useEffect(() => { onVerificationChange?.(verified); }, [verified, onVerificationChange]);

  useEffect(() => {
    let alive = true;
    const initialRevision = revision.current;
    api.getPostgresConfig().then(value => {
      if (!alive) return;
      setConfig(value);
      if (revision.current === initialRevision) setVerified(value.connection_status === 'connected' && !value.pending_apply && !value.pending_restart);
      setFields(previous => ({ ...previous, host: value.host, port: value.port, database: value.database, username: value.username, sslmode: value.sslmode }));
    }).catch(e => { if (alive) setError(errorMessage(e)); });
    return () => { alive = false; revision.current++; };
  }, []);

  function invalidate() { revision.current++; setVerified(false); setResult(null); setError(''); setNotice(''); if (busy === 'check') setBusy(null); }
  function payload(): PostgresConfigInput {
    if (mode === 'url') return { mode, url: url.trim() || undefined, sslmode: fields.sslmode };
    return { mode, ...fields, password: fields.password || undefined };
  }
  async function check() {
    const current = ++revision.current;
    setBusy('check'); setVerified(false); setError(''); setResult(null); setNotice('');
    try { const checked = await api.checkPostgresConfig(payload()); if (current === revision.current) { setResult(checked); setVerified(checked.status === 'passed'); } }
    catch (e) { if (current === revision.current) setError(errorMessage(e)); }
    finally { if (current === revision.current) setBusy(null); }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    const current = ++revision.current;
    setBusy('save'); setVerified(false); setError(''); setNotice(''); setResult(null);
    try {
      const saved = await api.savePostgresConfig(payload());
      if (current !== revision.current) return;
      setConfig(saved); setNotice(saved.message); setUrl(''); setVisible(false);
      setVerified(true);
      setFields(previous => ({ ...previous, host: saved.host, port: saved.port, database: saved.database, username: saved.username, password: '', sslmode: saved.sslmode }));
    } catch (e) { if (current === revision.current) setError(errorMessage(e)); }
    finally { if (current === revision.current) setBusy(null); }
  }
  async function apply() {
    const current = ++revision.current;
    setBusy('apply'); setVerified(false); setError(''); setNotice(''); setResult(null);
    try {
      const applied = await api.applyPostgresConfig();
      if (current !== revision.current) return;
      setConfig(applied); setNotice(applied.message);
      setVerified(applied.connection_status === 'connected');
      await onApplied?.();
    } catch (e) { if (current === revision.current) setError(errorMessage(e)); }
    finally { if (current === revision.current) setBusy(null); }
  }
  const canSubmit = mode === 'url' ? !!url.trim() || !!config?.configured : !!fields.host.trim() && !!fields.database.trim() && !!fields.username.trim() && fields.port >= 1 && fields.port <= 65535;
  const dirty = mode === 'url' ? !!url.trim() : !!fields.password || (['host', 'port', 'database', 'username', 'sslmode'] as const).some(key => fields[key] !== config?.[key]);
  const locked = busy === 'save' || busy === 'apply';

  return <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden" aria-labelledby="postgres-title">
    <div className="px-5 py-4 border-b border-slate-100"><h2 id="postgres-title" className="text-base font-semibold">Kết nối PostgreSQL</h2>
      <p className="text-sm text-slate-500 mt-1">Lưu lịch sử tra cứu, tài liệu và cấu hình hệ thống.</p></div>
    <form onSubmit={save}>
      <div className="p-5 space-y-5">
        <div className="flex items-center justify-between gap-3 text-xs"><span className={'inline-flex items-center gap-1.5 ' + (config?.pending_apply ? 'text-amber-700' : config?.connection_status === 'connected' ? 'text-emerald-600' : 'text-slate-400')}>
          <span className={'w-1.5 h-1.5 rounded-full ' + (config?.pending_apply ? 'bg-amber-500' : config?.connection_status === 'connected' ? 'bg-emerald-500' : 'bg-slate-300')} />
          {config?.pending_apply ? config.can_apply ? 'Đã lưu · chưa áp dụng' : 'Đã lưu · cần khởi động lại backend' : config?.connection_status === 'connected' ? 'Đang dùng kết nối đã lưu' : config?.saved ? 'Đã lưu cấu hình kết nối' : config?.configured ? 'Đã có cấu hình kết nối' : 'Chưa cấu hình'}</span>
          {config?.host && <span className="text-slate-400 truncate" title={config.host + '/' + config.database}>{config.host}:{config.port} / {config.database}</span>}</div>
        {config?.pending_apply && <div className="rounded-xl border border-amber-200 bg-amber-50/60 px-3 py-3 text-sm text-amber-900">
          <p className="font-medium">Thông tin đã được lưu, bạn không cần nhập lại.</p>
          <p className="text-xs leading-5 mt-1">{config.can_apply ? 'Backend chưa sử dụng kết nối này. Bấm Áp dụng để kết nối và chuẩn bị các bảng ứng dụng.' : 'Để đổi database đang dùng hoặc thay override môi trường, hãy khởi động lại backend.'}</p>
          {config.can_apply && <button type="button" className={adminPrimary + ' mt-3'} disabled={!!busy || dirty} onClick={apply}>
            {busy === 'apply' ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}{busy === 'apply' ? 'Đang áp dụng…' : 'Áp dụng kết nối đã lưu'}</button>}
          {dirty && config.can_apply && <p className="text-xs mt-1">Lưu thay đổi trên form trước khi áp dụng.</p>}
        </div>}
        <div className="inline-flex gap-1 bg-slate-100 p-1 rounded-xl">{(['url', 'fields'] as const).map(option => <button key={option} type="button" disabled={locked} onClick={() => { invalidate(); setMode(option); setVisible(false); }}
          className={'text-xs font-medium px-3 py-1.5 rounded-lg ' + (mode === option ? 'bg-white text-on-surface shadow-sm' : 'text-slate-500 hover:text-slate-800')}>{option === 'url' ? 'Dán chuỗi kết nối' : 'Nhập từng trường'}</button>)}</div>
        {mode === 'url' ? <div><label htmlFor="postgres-url" className="block text-sm font-medium text-slate-700 mb-1.5">Chuỗi kết nối PostgreSQL</label>
          <div className="relative"><input id="postgres-url" type={visible ? 'text' : 'password'} className={adminInput + ' pr-11'} autoComplete="new-password" value={url} disabled={locked}
            onChange={e => { invalidate(); setUrl(e.target.value); }} placeholder={config?.configured ? 'Chuỗi kết nối đã lưu · để trống để giữ nguyên' : 'postgresql://user:password@host:5432/database?sslmode=require'} />
            <button type="button" className="absolute right-3 top-3 text-slate-400 hover:text-secondary" aria-label={visible ? 'Ẩn chuỗi kết nối' : 'Hiện chuỗi kết nối'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={16} /> : <Eye size={16} />}</button></div>
          <p className="text-xs text-slate-400 mt-1.5">{config?.saved && !url ? 'Kết nối đã lưu trong .env. Ô này chỉ dùng để nhập kết nối thay thế; mật khẩu được giữ kín.' : 'Dán connection string do nhà cung cấp PostgreSQL cung cấp. Mật khẩu đã lưu sẽ không được trả về trình duyệt.'}</p></div>
          : <div className="grid sm:grid-cols-2 gap-4">
            {([
              ['host', 'Host', 'db.example.com'], ['port', 'Port', '5432'], ['database', 'Tên database', 'Tên database'],
              ['username', 'Tên người dùng', 'Tên tài khoản'], ['password', 'Mật khẩu', config?.password_configured ? 'Để trống để giữ mật khẩu cho cùng máy chủ/tài khoản' : 'Nhập mật khẩu'],
            ] as const).map(([key, label, placeholder]) => <label key={key} className="block text-sm font-medium text-slate-700">{label}<input className={adminInput + ' mt-1.5'} type={key === 'port' ? 'number' : key === 'password' ? 'password' : 'text'}
              value={fields[key]} required={key !== 'password'} min={key === 'port' ? 1 : undefined} max={key === 'port' ? 65535 : undefined} autoComplete={key === 'password' ? 'new-password' : 'off'} disabled={locked} placeholder={placeholder}
              onChange={e => { invalidate(); setFields(previous => ({ ...previous, [key]: key === 'port' ? Number(e.target.value) : e.target.value })); }} /></label>)}
            <label className="block text-sm font-medium text-slate-700">SSL<select className={adminInput + ' mt-1.5'} value={fields.sslmode} disabled={locked} onChange={e => { invalidate(); setFields(previous => ({ ...previous, sslmode: e.target.value as PostgresConfigInput['sslmode'] })); }}>
              <option value="require">Require · yêu cầu SSL</option><option value="verify-full">Verify full · xác thực chứng chỉ và host</option><option value="verify-ca">Verify CA · xác thực chứng chỉ</option><option value="prefer">Prefer · ưu tiên SSL</option><option value="allow">Allow · cho phép SSL</option><option value="disable">Disable · không dùng SSL</option></select></label>
          </div>}
        <div className="rounded-xl bg-slate-50 px-3 py-2.5 text-xs text-slate-500 leading-5 flex items-start gap-2"><Info size={14} className="shrink-0 mt-0.5 text-slate-400" />
          <p>Kiểm tra chỉ đọc dữ liệu. Lưu cập nhật <strong className="font-medium">DATABASE_URL</strong> trong <strong className="font-medium">.env</strong>. Sau đó bấm <strong className="font-medium">Áp dụng</strong> để thiết lập kết nối ban đầu; database cần được tạo sẵn.</p></div>
        {config?.environment_override && <p className="text-xs text-amber-700">DATABASE_URL của tiến trình khác giá trị trong .env và đang được ưu tiên. Cập nhật hoặc bỏ biến DATABASE_URL ở terminal/IDE, rồi khởi động lại backend để áp dụng .env.</p>}
        {notice && <div role="status" className="px-3 py-2.5 rounded-xl bg-emerald-50 text-emerald-700 text-sm"><p className="flex gap-2 items-start"><CheckCircle2 size={16} className="shrink-0 mt-0.5" />{notice}</p>
          {config?.pending_restart && <p className="mt-2 text-xs text-emerald-800">Trong terminal backend: Ctrl+C, rồi chạy lại <strong className="font-medium">python run_backend.py</strong>.</p>}</div>}
        {error && <p role="alert" className="text-sm text-red-600 flex gap-2 items-start"><AlertCircle size={15} className="shrink-0 mt-0.5" />{error}</p>}
      </div>
      <div className="px-5 py-4 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div aria-live="polite" className={'text-xs ' + (result?.status === 'passed' ? 'text-emerald-600' : result?.status === 'failed' ? 'text-red-600' : 'text-slate-400')}>
          <p className="flex items-center gap-1.5">{busy === 'check' ? <Loader2 size={14} className="animate-spin" /> : result?.status === 'passed' ? <CheckCircle2 size={14} /> : null}
            {busy === 'check' ? 'Đang kiểm tra kết nối…' : result?.message || (!dirty && config?.saved ? config.pending_apply ? 'Cấu hình đã lưu. Chưa áp dụng cho backend.' : 'Cấu hình đã lưu và đang được sử dụng.' : 'Chưa kiểm tra thay đổi trên form')}</p>
          {result && <p className="mt-1 text-[11px] text-slate-400">{new Date(result.checked_at).toLocaleString('vi-VN')} · {result.latency_ms} ms</p>}
        </div>
        <div className="flex gap-2 shrink-0"><button type="button" className={adminButton} disabled={!canSubmit || !!busy} onClick={check}><CheckCircle2 size={15} />Kiểm tra</button>
          <button type="submit" className={adminPrimary} disabled={!canSubmit || !!busy || (!dirty && !!config?.saved)}>{busy === 'save' ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}{busy === 'save' ? 'Đang kiểm tra và lưu…' : !dirty && config?.saved ? 'Đã lưu' : 'Lưu vào .env'}</button></div>
      </div>
    </form>
  </section>;
}
