'use client';

import { SettingsPanel } from '../../components/settings/SettingsPanel';

/** Full-page settings for direct links; the same panel opens as a dialog elsewhere. */
export default function AdminPage() {
  return <SettingsPanel variant="page" />;
}
