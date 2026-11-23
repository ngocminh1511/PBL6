import { redirect } from 'next/navigation';

/** The catalog now lives in the documents workspace; keep old links working. */
export default function AppendicesPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  const search = new URLSearchParams({ tab: 'danh-muc' });
  for (const [key, value] of Object.entries(searchParams)) {
    if (typeof value === 'string' && key !== 'tab') search.set(key, value);
  }
  redirect('/documents?' + search.toString());
}
