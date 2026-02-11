// @vitest-environment jsdom

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import HomePage from '../app/page';

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

describe('page controls', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
        removeItem: (key: string) => {
          store.delete(key);
        },
        clear: () => {
          store.clear();
        }
      }
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/documents/library')) return json([]);
      if (url.endsWith('/documents')) return json([]);
      if (url.endsWith('/personas')) return json([]);
      if (url.endsWith('/status')) {
        return json({
          redis: { ok: true, error: null },
          llm: { provider: 'openai', ok: true, error: null, model: 'gpt-4o-mini' },
          openai: { ok: true },
          review_queue: 'review-jobs',
          doc_repo_enabled: true
        });
      }
      if (url.endsWith('/health')) return json({ status: 'ok' });
      if (init?.method === 'POST' || init?.method === 'PATCH' || init?.method === 'DELETE') {
        return json({}, 204);
      }
      return json({});
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('opens library overlay from top nav', async () => {
    render(<HomePage />);
    fireEvent.click(screen.getByRole('button', { name: 'Library' }));
    expect(await screen.findByText('Review Ledger')).toBeTruthy();
  });

  it('saves system settings to localStorage', async () => {
    render(<HomePage />);
    fireEvent.click(screen.getByRole('button', { name: 'System' }));
    const apiInput = await screen.findByPlaceholderText('http://localhost:8006/api');
    const tenantInput = await screen.findByPlaceholderText('local-dev');

    fireEvent.change(apiInput, { target: { value: 'https://opinion.zlyxy.me/api' } });
    fireEvent.change(tenantInput, { target: { value: 'beta-tenant' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(window.localStorage.getItem('odr_api_base')).toBe('https://opinion.zlyxy.me/api');
      expect(window.localStorage.getItem('odr_tenant_id')).toBe('beta-tenant');
    });
  });
});
