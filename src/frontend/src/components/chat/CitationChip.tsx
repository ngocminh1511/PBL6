'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { useChatStore } from '../../stores/chatStore';

interface CitationChipProps {
  citation: string;
  href?: string;
  index?: number;
  /** Opens the appendix preview in the inspector instead of navigating away. */
  appendix?: { id: string; chunkId?: string };
}

export const CitationChip: React.FC<CitationChipProps> = ({ citation, href, index, appendix }) => {
  const router = useRouter();
  const { setSelectedCitation, setInspectorTab, openAppendix } = useChatStore();

  const handleClick = () => {
    if (appendix) {
      openAppendix(appendix.id, appendix.chunkId);
      return;
    }
    if (href) {
      router.push(href);
      return;
    }
    setSelectedCitation(citation);
    // Every legal citation, graph-reached or not, carries its document, Dieu and
    // khoan, so the tree opens and highlights it; the graph tab is for browsing.
    setInspectorTab('tab-hierarchy');
  };

  return (
    <button
      onClick={handleClick}
      type="button"
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-paper border border-ink/10 hover:border-navy/35 text-[12px] text-navy font-medium transition-colors text-left"
      title={appendix ? 'Xem trước và tải biểu mẫu' : 'Nhấp để đối soát Điều/Khoản/Điểm trên Cột Thanh tra Pháp lý'}
    >
      {index != null && <span className="font-mono text-[11px]">[{index}]</span>}
      <span>{citation}</span>
      {appendix && <span className="text-[10.5px] font-normal text-muted">· xem trước</span>}
    </button>
  );
};
