'use client';

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import type { ASTNode, DocumentRecord } from '../../lib/types';
import { articleLabel, articleLines, articleTitle } from '../../lib/articleOutline';

/** Full text of one article, clause by clause, with the raw AST on demand. */
export function ArticleView({ doc, article, tree }: {
  doc: DocumentRecord | undefined;
  article: ASTNode | null;
  tree: ASTNode | null;
}) {
  const [json, setJson] = useState(false);
  const body = useMemo(() => (article ? articleLines(article) : []), [article]);
  const source = article?.document_number || doc?.document_number;

  return (
    <div className="h-full min-h-0 bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/30 flex flex-col overflow-hidden">
      <div className="px-space-md py-space-sm flex items-start gap-3 border-b border-outline-variant/20">
        <div className="flex-1 min-w-0 flex flex-col gap-0.5">
          <span className="text-[12px] text-ink-3">{json ? 'Cấu trúc AST của văn bản' : [doc?.title, source].filter(Boolean).join(' · ')}</span>
          {!json && (
            <h3 className="text-[16px] font-semibold text-ink leading-snug">
              {article ? <>{articleLabel(article)}. {articleTitle(article)}</> : 'Chọn một Điều trong mục lục'}
            </h3>
          )}
        </div>
        <div className="shrink-0 flex items-center gap-1 bg-stone p-0.5 rounded-lg">
          {[['Nội dung', false], ['JSON', true]].map(([label, value]) => (
            <button key={String(label)} type="button" onClick={() => setJson(value as boolean)} disabled={!tree}
              className={'px-2 py-0.5 rounded-md text-[12px] font-medium transition-colors disabled:opacity-40 ' + (json === value
                ? 'bg-white text-ink shadow-[0_1px_2px_rgba(28,27,24,0.06)]' : 'text-ink-3 hover:text-ink')}>
              {label as string}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto legal-scroll px-space-md py-space-md">
        {json ? (
          tree ? <pre className="font-mono text-[11.5px] text-ink-2 whitespace-pre-wrap break-words">{JSON.stringify(tree, null, 2)}</pre> : null
        ) : !article ? (
          <p className="py-10 text-center text-[12.5px] text-muted">Nội dung Điều sẽ hiện ở đây.</p>
        ) : body.length === 0 ? (
          <p className="py-10 text-center text-[12.5px] text-muted">Điều này chưa có nội dung trong kho.</p>
        ) : (
          <div className="flex flex-col gap-2 text-[14px] leading-relaxed text-ink">
            {body.map((line, index) => (
              <p key={index} className={line.kind === 'point' ? 'pl-6 flex gap-1.5' : line.kind === 'clause' ? 'flex gap-1.5' : ''}>
                {line.label && <span className="shrink-0 font-semibold text-navy">{line.label}</span>}
                <span>{line.text}</span>
              </p>
            ))}
          </div>
        )}
      </div>

      {doc && (
        <div className="p-space-sm border-t border-outline-variant/20">
          <Link href={`/chat?doc=${encodeURIComponent(doc.id)}`}
            className="w-full flex items-center justify-center gap-2 px-space-md py-2 rounded-xl bg-secondary text-white hover:bg-opacity-95 shadow-sm transition-all text-[13px] font-medium">
            <span className="material-symbols-outlined text-[18px]">chat</span>
            Hỏi Trợ lý về văn bản này
          </Link>
        </div>
      )}
    </div>
  );
}
