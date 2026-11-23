'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { useChatStore } from '../../stores/chatStore';

interface CitationChipProps {
  citation: string;
  isGraphRef?: boolean;
  href?: string;
  index?: number;
}

export const CitationChip: React.FC<CitationChipProps> = ({ citation, isGraphRef, href, index }) => {
  const router = useRouter();
  const { setSelectedCitation, setInspectorTab } = useChatStore();

  const handleClick = () => {
    if (href) {
      router.push(href);
      return;
    }
    setSelectedCitation(citation);
    setInspectorTab(isGraphRef ? 'tab-graph' : 'tab-hierarchy');
  };

  return (
    <button
      onClick={handleClick}
      type="button"
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-paper border border-ink/10 hover:border-navy/35 text-[12px] text-navy font-medium transition-colors text-left"
      title="Nhấp để đối soát Điều/Khoản/Điểm trên Cột Thanh tra Pháp lý"
    >
      {index != null && <span className="font-mono text-[11px]">[{index}]</span>}
      <span>{citation}</span>
      {isGraphRef && <span className="text-[10.5px] font-normal text-muted">· đồ thị</span>}
    </button>
  );
};
