'use client';

import React, { useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { AdminConfig, SystemStats } from '../../lib/types';

export default function AdminPage() {
  const [error, setError] = useState('');
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [flushMessage, setFlushMessage] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [cfg, st] = await Promise.all([api.getAdminConfig(), api.getSystemStats().catch(() => null)]);
      setConfig(cfg);
      setStats(st);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;
    setIsSaving(true);
    setSaveSuccess(false);
    setError('');
    try {
      const updated = await api.updateAdminConfig(config);
      setConfig(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setIsSaving(false);
    }
  };

  const handleFlushCache = async () => {
    try {
      const res = await api.flushCache();
      setFlushMessage(res.message);
      setTimeout(() => setFlushMessage(null), 4000);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  if (!config && error) return <div className="p-gutter max-w-5xl mx-auto"><p role="alert" className="p-space-md rounded-xl bg-error-container text-on-error-container">{error}</p></div>;
  if (!config) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-2 text-on-surface-variant font-body-md">
          <span className="w-5 h-5 border-2 border-secondary border-t-transparent rounded-full animate-spin"></span>
          <span>Đang tải thông số quản trị hệ thống...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-gutter max-w-5xl mx-auto flex flex-col gap-space-lg">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-space-md border-b border-outline-variant/30 pb-space-md">
        <div>
          <h1 className="font-display-lg text-headline-lg font-bold text-on-surface">
            Cấu hình Hệ thống - Pháp luật Việt Nam
          </h1>
          <p className="font-body-md text-body-sm text-on-surface-variant">
            Tùy biến mô hình Embedding, Vector Database, hạ tầng GPU Modal, và LLM Provider
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleFlushCache}
            type="button"
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-container-high hover:bg-surface-variant text-on-surface font-headline-sm text-body-sm transition-all border border-outline-variant/40"
          >
            <span className="material-symbols-outlined text-[18px]">cached</span>
            <span>Xóa Redis Cache</span>
          </button>
        </div>
      </div>

      {error && <p role="alert" className="p-space-md rounded-xl bg-error-container text-on-error-container font-body-sm text-body-sm">{error}</p>}
      {flushMessage && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-800 text-sm font-medium animate-fadeIn">
          {flushMessage}
        </div>
      )}

      {saveSuccess && (
        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-300 text-emerald-800 text-sm font-medium animate-fadeIn">
          ✓ Đã lưu cấu hình hệ thống thành công! Các request tiếp theo sẽ dùng cấu hình mới.
        </div>
      )}

      {/* Live Infrastructure Status */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-space-md">
          <div className="p-3.5 rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-xs">
            <span className="font-label-statute text-[11px] text-on-surface-variant uppercase">CSDL Vector (Qdrant)</span>
            <div className="font-headline-sm text-emerald-600 font-bold mt-1 flex items-center gap-1.5">
              <span className={`w-2 h-2 rounded-full ${stats.vector_db_status === 'connected' ? 'bg-emerald-500' : 'bg-outline'}`}></span>
              {stats.vector_db_status}
            </div>
            <span className="text-[11px] font-mono text-outline">{stats.total_chunks ?? '—'} Đoạn đã lập chỉ mục</span>
          </div>

          <div className="p-3.5 rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-xs">
            <span className="font-label-statute text-[11px] text-on-surface-variant uppercase">Đồ thị Tri thức (Neo4j)</span>
            <div className="font-headline-sm text-secondary font-bold mt-1 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-secondary"></span>
              {stats.graph_db_status}
            </div>
            <span className="text-[11px] font-mono text-outline">{stats.total_nodes ?? '—'} Đỉnh • {stats.total_edges ?? '—'} Cạnh</span>
          </div>

          <div className="p-3.5 rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-xs">
            <span className="font-label-statute text-[11px] text-on-surface-variant uppercase">Bộ nhớ đệm (Redis)</span>
            <div className="font-headline-sm text-on-surface font-bold mt-1">
              {stats.redis_status}
            </div>
            <span className="text-[11px] font-mono text-outline">Đệm phiên & Vector nhúng</span>
          </div>

          <div className="p-3.5 rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-xs">
            <span className="font-label-statute text-[11px] text-on-surface-variant uppercase">Phiên tra cứu</span>
            <div className="font-headline-sm text-on-surface font-bold mt-1">
              {stats.active_sessions_count ?? '—'} Phiên
            </div>
            <span className="text-[11px] font-mono text-outline">Lịch sử đa lượt lưu trữ</span>
          </div>
        </div>
      )}

      {/* Main Settings Form */}
      <form onSubmit={handleSave} className="flex flex-col gap-space-lg">
        {/* 1. Embedding Model & Modal GPU */}
        <div className="p-space-lg bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/30 flex flex-col gap-4">
          <div className="flex items-center gap-2 border-b border-outline-variant/20 pb-3">
            <span className="material-symbols-outlined text-secondary text-[22px]">hub</span>
            <h2 className="font-headline-md text-headline-sm text-on-surface">
              1. Cấu hình Mô hình Embedding & Nguồn tính toán
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Model Selection */}
            <div className="flex flex-col gap-1.5">
              <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Mô hình Embedding
              </label>
              <select
                value={config.embedding_model}
                onChange={(e) => { const pair = Object.entries(config.available_collections).find(([, model]) => model === e.target.value);
                  if (pair) setConfig({ ...config, embedding_model: e.target.value, qdrant_collection: pair[0] }); }}
                className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 text-on-surface font-body-sm focus:outline-none focus:border-secondary"
              >
                {Array.from(new Set([config.embedding_model, 'BAAI/bge-m3', 'data/model/bge-m3-legal-vietnamese', 'bkai-foundation-models/vietnamese-bi-encoder', ...Object.values(config.available_collections)])).map(model =>
                  <option key={model} value={model} disabled={!Object.values(config.available_collections).includes(model)}>{model}{!Object.values(config.available_collections).includes(model) ? ' · chưa đăng ký collection' : ''}</option>)}
              </select>
              <span className="text-[11px] text-on-surface-variant">
                Chọn model cùng collection đã index tương ứng; đăng ký thêm qua COLLECTION_MODELS.
              </span>
            </div>

            {/* Backend Selection */}
            <div className="flex flex-col gap-1.5">
              <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Nguồn tính toán Vector (Embedding Backend)
              </label>
              <select
                value={config.embedding_backend}
                onChange={(e) => setConfig({ ...config, embedding_backend: e.target.value as any })}
                className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 text-on-surface font-body-sm focus:outline-none focus:border-secondary"
              >
                <option value="local">Máy cục bộ (CPU / GPU CUDA nội bộ)</option>
                <option value="modal">Đám mây Modal GPU (scripts/modal_embed.py trên T4/A10G)</option>
              </select>
              <span className="text-[11px] text-on-surface-variant">
                Modal cho phép tính toán GPU siêu tốc mà không gửi thông tin xác thực của Qdrant/Neo4j lên đám mây.
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">Nguồn tính toán khi truy vấn</label>
            <select value={config.query_embedding_backend} onChange={e => setConfig({ ...config, query_embedding_backend: e.target.value as 'modal' | 'local' })}
              className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 text-on-surface font-body-sm">
              <option value="modal">Modal cloud</option><option value="local">Máy cục bộ</option>
            </select>
          </div>
          {config.embedding_backend === 'modal' && (
            <div className="p-3 rounded-xl bg-surface-container-low border border-secondary/30 flex flex-col gap-1">
              <label className="font-label-statute text-label-statute text-secondary font-bold">
                Tên ứng dụng Modal đã triển khai
              </label>
              <input
                type="text"
                value={config.modal_app_name}
                onChange={(e) => setConfig({ ...config, modal_app_name: e.target.value })}
                className="bg-surface-container-lowest border border-outline-variant/40 rounded-lg p-2 font-mono text-sm text-on-surface"
              />
            </div>
          )}
        </div>

        {/* 2. Vector DB (Qdrant) & Graph DB */}
        <div className="p-space-lg bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/30 flex flex-col gap-4">
          <div className="flex items-center gap-2 border-b border-outline-variant/20 pb-3">
            <span className="material-symbols-outlined text-secondary text-[22px]">database</span>
            <h2 className="font-headline-md text-headline-sm text-on-surface">
              2. Cơ sở dữ liệu Vector & Đồ thị Tri thức
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Chọn CSDL Vector
              </label>
              <select
                value={config.vector_db}
                disabled
                className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 text-on-surface font-body-sm"
              >
                <option value="qdrant">Qdrant (Đã cấu hình & Kiểm định trong PBL6)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Đường dẫn Qdrant URL
              </label>
              <input
                type="text"
                value={config.qdrant_url}
                onChange={(e) => setConfig({ ...config, qdrant_url: e.target.value })}
                className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 font-mono text-sm text-on-surface"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Tập hợp (Collection) Qdrant
              </label>
              <input
                type="text"
                value={config.qdrant_collection}
                onChange={(e) => setConfig({ ...config, qdrant_collection: e.target.value, embedding_model: config.available_collections[e.target.value] || config.embedding_model })}
                className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 font-mono text-sm text-on-surface"
              />
            </div>
          </div>
        </div>

        <div className="p-space-lg bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/30 flex flex-col gap-1.5">
          <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">Kết nối đồ thị Neo4j</label>
          <input value={config.neo4j_uri} onChange={e => setConfig({ ...config, neo4j_uri: e.target.value })}
            className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 font-mono text-sm text-on-surface" />
        </div>
        {/* 3. LLM Provider */}
        <div className="p-space-lg bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/30 flex flex-col gap-4">
          <div className="flex items-center gap-2 border-b border-outline-variant/20 pb-3">
            <span className="material-symbols-outlined text-secondary text-[22px]">neurology</span>
            <h2 className="font-headline-md text-headline-sm text-on-surface">
              3. Nhà cung cấp Mô hình Ngôn ngữ Lớn (LLM Provider)
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Nhà cung cấp LLM
              </label>
              <select
                value={config.llm_provider}
                onChange={(e) => setConfig({ ...config, llm_provider: e.target.value as any })}
                className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 text-on-surface font-body-sm focus:outline-none focus:border-secondary"
              >
                <option value="gemini">Google Gemini</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-label-statute text-label-statute uppercase text-on-surface-variant font-bold">
                Mô hình chỉ định
              </label>
              <input
                type="text"
                value={config[(config.llm_provider + '_model') as 'gemini_model' | 'anthropic_model' | 'openai_model']}
                onChange={(e) => setConfig({ ...config, [(config.llm_provider + '_model') as 'gemini_model' | 'anthropic_model' | 'openai_model']: e.target.value })}
                className="bg-surface-container-low border border-outline-variant/40 rounded-xl p-2.5 font-mono text-sm text-on-surface"
                placeholder="Tên model của provider đã chọn"
              />
            </div>
          </div>
        </div>

        <label className="flex items-center gap-space-sm font-body-sm text-body-sm"><input type="checkbox" checked={config.redis_enabled} onChange={e => setConfig({ ...config, redis_enabled: e.target.checked })} className="accent-secondary" />Bật Redis cache</label>
        {/* Submit Bar */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="submit"
            disabled={isSaving}
            className="px-6 py-2.5 rounded-xl bg-secondary text-white font-headline-sm text-body-sm shadow-sm hover:opacity-95 active:scale-95 transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {isSaving ? (
              <>
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                <span>Đang lưu cấu hình...</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[18px]">save</span>
                <span>Lưu Thay đổi Cấu hình</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

