'use client';

import React from 'react';
import { useChatStore } from '../../stores/chatStore';

interface CitationChipProps {
  citation: string;
  isGraphRef?: boolean;
}

export const CitationChip: React.FC<CitationChipProps> = ({ citation, isGraphRef }) => {
  const { setSelectedCitation, setInspectorTab } = useChatStore();

  const handleClick = () => {
    setSelectedCitation(citation);
    setInspectorTab(isGraphRef ? 'tab-graph' : 'tab-hierarchy');
  };

  return (
    <button
      onClick={handleClick}
      type="button"
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container-high hover:bg-secondary-fixed text-on-surface font-label-statute text-label-statute transition-all group shadow-xs border border-outline-variant/40 hover:border-secondary"
      title="Nhấp để đối soát Điều/Khoản/Điểm trên Cột Thanh tra Pháp lý"
    >
      <span className="material-symbols-outlined text-[15px] text-secondary group-hover:scale-110 transition-transform">
        {isGraphRef ? 'link' : 'gavel'}
      </span>
      <span className="font-medium">{citation}</span>
      <span className="w-1.5 h-1.5 rounded-full bg-on-tertiary-container animate-pulse"></span>
    </button>
  );
};

