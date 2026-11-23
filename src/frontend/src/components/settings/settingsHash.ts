import type { SettingsSection } from './SettingsPanel';

const SECTIONS: readonly string[] = ['llm', 'postgres', 'embedding', 'qdrant', 'neo4j', 'r2', 'redis', 'ocr', 'info'];

/** `#settings` or `#settings/<section>` opens the settings dialog on any page. */
export function parseSettingsHash(hash: string): { open: boolean; section: SettingsSection } {
  const match = /^#settings(?:\/([a-z0-9]+))?$/.exec(hash);
  if (!match) return { open: false, section: 'llm' };
  const section = match[1] && SECTIONS.includes(match[1]) ? (match[1] as SettingsSection) : 'llm';
  return { open: true, section };
}

export function openSettings(section?: SettingsSection) {
  window.location.hash = section ? `settings/${section}` : 'settings';
}

export function closeSettings() {
  const { pathname, search } = window.location;
  window.history.replaceState(window.history.state, '', pathname + search);
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

export function setSettingsSection(section: SettingsSection) {
  const { pathname, search } = window.location;
  window.history.replaceState(window.history.state, '', `${pathname}${search}#settings/${section}`);
}
