'use client';

import React, { useEffect, useRef, useState } from 'react';

interface PanelResizerProps {
  side: 'left' | 'right';
  currentWidth: number;
  minWidth: number;
  maxWidth: number;
  snapCollapseBelow: number;
  onResize: (nextWidth: number) => void;
  onCollapse: () => void;
  onResetWidth: () => void;
}

export const PanelResizer: React.FC<PanelResizerProps> = ({
  side,
  currentWidth,
  minWidth,
  maxWidth,
  snapCollapseBelow,
  onResize,
  onCollapse,
  onResetWidth,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(currentWidth);

  useEffect(() => {
    if (!isDragging) return;

    const handlePointerMove = (e: PointerEvent) => {
      const delta = e.clientX - startXRef.current;
      const rawWidth =
        side === 'left'
          ? startWidthRef.current + delta
          : startWidthRef.current - delta;

      if (rawWidth < snapCollapseBelow) {
        setIsDragging(false);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        onCollapse();
        return;
      }

      const clamped = Math.min(maxWidth, Math.max(minWidth, rawWidth));
      onResize(Math.round(clamped));
    };

    const handlePointerUp = () => {
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);

    return () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [
    isDragging,
    side,
    minWidth,
    maxWidth,
    snapCollapseBelow,
    onResize,
    onCollapse,
  ]);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    startXRef.current = e.clientX;
    startWidthRef.current = currentWidth;
    setIsDragging(true);
  };

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={
        side === 'left'
          ? 'Kéo để thay đổi độ rộng thanh lịch sử'
          : 'Kéo để thay đổi độ rộng thanh tra cứu'
      }
      title="Kéo sang trái/phải để chỉnh độ rộng · Nhấp đúp để đặt lại"
      onPointerDown={handlePointerDown}
      onDoubleClick={onResetWidth}
      className="relative w-3 shrink-0 flex items-center justify-center cursor-col-resize group select-none z-10"
    >
      {/* Subtle vertical grip indicator */}
      <div
        className={`w-1 rounded-full transition-all duration-150 ${
          isDragging
            ? 'h-16 bg-navy'
            : 'h-10 bg-[#1C1B18]/15 group-hover:h-14 group-hover:bg-navy/65'
        }`}
      />

      {/* Live width indicator while dragging */}
      {isDragging && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-md bg-navy text-white font-mono text-[11px] tabular-nums whitespace-nowrap shadow-sm pointer-events-none">
          {currentWidth}px
        </div>
      )}
    </div>
  );
};
