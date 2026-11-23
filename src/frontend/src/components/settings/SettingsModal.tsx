'use client';

import React, { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { SettingsPanel, type SettingsSection } from './SettingsPanel';
import { closeSettings, parseSettingsHash, setSettingsSection } from './settingsHash';

/** Mounted once in the app shell; opens the settings dialog from the URL hash. */
export const SettingsModal: React.FC = () => {
  const pathname = usePathname();
  const [state, setState] = useState<{ open: boolean; section: SettingsSection }>({ open: false, section: 'llm' });

  useEffect(() => {
    const sync = () => setState(parseSettingsHash(window.location.hash));
    sync();
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  // The /admin route already shows the full settings page.
  const open = state.open && !pathname.startsWith('/admin');

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') closeSettings(); };
    window.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
    };
  }, [open]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[55] flex items-center justify-center bg-ink/35 backdrop-blur-[2px] p-3 sm:p-6"
      onMouseDown={(e) => { if (e.target === e.currentTarget) closeSettings(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="w-full max-w-[1120px] h-[min(760px,100%)] bg-white rounded-2xl border border-ink/10 shadow-2xl overflow-hidden"
      >
        <SettingsPanel
          variant="modal"
          initialSection={state.section}
          onSectionChange={setSettingsSection}
          onClose={closeSettings}
        />
      </div>
    </div>
  );
};
