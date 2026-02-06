import { describe, expect, it, vi } from 'vitest';
import { apiFetch } from '../src/lib/api';


describe('upload flow', () => {
  it('creates doc, version, and review job in order', async () => {
    const calls: string[] = [];
    const mockFetch = vi.fn(async (url: string) => {
      calls.push(url);
      if (url.endsWith('/documents')) {
        return new Response(JSON.stringify({ id: 1 }), { status: 201 });
      }
      if (url.includes('/documents/1/versions')) {
        return new Response(JSON.stringify({ id: 10 }), { status: 201 });
      }
      if (url.endsWith('/review-jobs')) {
        return new Response(JSON.stringify({ id: 100, status: 'queued' }), { status: 201 });
      }
      return new Response('{}', { status: 200 });
    }) as unknown as typeof fetch;

    // @ts-expect-error test override
    global.fetch = mockFetch;

    await apiFetch('/documents', { method: 'POST', body: JSON.stringify({ title: 'Doc' }) });
    await apiFetch('/documents/1/versions', { method: 'POST', body: JSON.stringify({ version_label: 'Initial upload', content: 'x' }) });
    await apiFetch('/review-jobs', { method: 'POST', body: JSON.stringify({ document_version_id: 10 }) });

    expect(calls[0]).toContain('/documents');
    expect(calls[1]).toContain('/documents/1/versions');
    expect(calls[2]).toContain('/review-jobs');
  });
});
