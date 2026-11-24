'use client';

import React, { useMemo } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { EvidenceItem } from '../../lib/types';
import { EVIDENCE_HREF, linkCitations } from '../../lib/citationLinks';

// Maps the Markdown the answer model writes onto the existing answer typography.
// Raw HTML in the answer is not rendered (react-markdown escapes it by default).
const baseComponents: Components = {
  p: ({ children }) => <p className="my-3 first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  h1: ({ children }) => <h3 className="mt-5 mb-2 first:mt-0 text-[17px] font-semibold text-ink">{children}</h3>,
  h2: ({ children }) => <h3 className="mt-5 mb-2 first:mt-0 text-[16.5px] font-semibold text-ink">{children}</h3>,
  h3: ({ children }) => <h4 className="mt-4 mb-1.5 first:mt-0 text-[15.5px] font-semibold text-ink">{children}</h4>,
  h4: ({ children }) => <h4 className="mt-4 mb-1.5 first:mt-0 text-[15.5px] font-semibold text-ink">{children}</h4>,
  ol: ({ children }) => <ol className="my-3 pl-6 list-decimal space-y-2 marker:text-ink-3 marker:font-medium">{children}</ol>,
  ul: ({ children }) => <ul className="my-2 pl-5 list-disc space-y-1 marker:text-ink-3">{children}</ul>,
  li: ({ children }) => <li className="pl-1 [&>p]:my-1">{children}</li>,
  // "> Căn cứ: ..." lines: the legal basis of the point above.
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-navy/30 pl-3 text-[14px] leading-relaxed text-ink-3 [&>p]:my-0.5">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-navy underline underline-offset-2">
      {children}
    </a>
  ),
  code: ({ children }) => <code className="rounded bg-stone px-1 py-0.5 font-mono text-[13px]">{children}</code>,
  hr: () => <hr className="my-4 border-ink/10" />,
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-[14px]">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-ink/10 bg-[#F4F2EC] px-2.5 py-1.5 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-ink/10 px-2.5 py-1.5 align-top">{children}</td>,
};

interface MarkdownAnswerProps {
  content: string;
  /** Evidence retrieved for this answer: citations naming one become links. */
  evidences?: EvidenceItem[];
  onCite?: (evidence: EvidenceItem) => void;
}

export const MarkdownAnswer: React.FC<MarkdownAnswerProps> = ({ content, evidences, onCite }) => {
  const linked = useMemo(() => (onCite ? linkCitations(content, evidences) : content), [content, evidences, onCite]);
  const components = useMemo<Components>(() => ({
    ...baseComponents,
    a: props => {
      const href = props.href || '';
      const evidence = href.startsWith(EVIDENCE_HREF) ? evidences?.[Number(href.slice(EVIDENCE_HREF.length))] : undefined;
      if (!evidence || !onCite) {
        // An unmatched #evidence link is the model's own text, not a navigation target.
        if (href.startsWith('#')) return <>{props.children}</>;
        return <a href={href} target="_blank" rel="noopener noreferrer" className="text-navy underline underline-offset-2">{props.children}</a>;
      }
      return (
        <button
          type="button"
          onClick={() => onCite(evidence)}
          title={`Mở ${evidence.citation} trong Cây phân cấp`}
          className="inline text-left font-medium text-navy underline decoration-navy/30 underline-offset-2 hover:decoration-navy"
        >
          {props.children}
        </button>
      );
    },
  }), [evidences, onCite]);
  return (
    <div className="text-[15.5px] leading-[1.7] text-[#262521] break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {linked}
      </ReactMarkdown>
    </div>
  );
};
