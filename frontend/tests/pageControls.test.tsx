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
      if (url.endsWith('/settings') && (!init || init.method === 'GET')) {
        return json({
          llm_provider: 'openai',
          openai_model: 'gpt-4o-mini',
          openai_max_tokens: 700,
          openai_temperature: 0.2,
          openai_timeout_seconds: 30,
          bedrock_model_id: 'anthropic.claude-3-5-haiku-20241022-v1:0',
          bedrock_region: 'us-east-1',
          review_inline: false,
          openai_api_key_set: false,
          bedrock_access_key_set: false,
          bedrock_secret_key_set: false,
          bedrock_session_token_set: false
        });
      }
      if (url.endsWith('/settings') && init?.method === 'PUT') {
        const body = JSON.parse(String(init.body || '{}'));
        return json({
          llm_provider: body.llm_provider ?? 'openai',
          openai_model: body.openai_model ?? 'gpt-4o-mini',
          openai_max_tokens: body.openai_max_tokens ?? 700,
          openai_temperature: body.openai_temperature ?? 0.2,
          openai_timeout_seconds: body.openai_timeout_seconds ?? 30,
          bedrock_model_id: body.bedrock_model_id ?? 'anthropic.claude-3-5-haiku-20241022-v1:0',
          bedrock_region: body.bedrock_region ?? 'us-east-1',
          review_inline: body.review_inline ?? false,
          openai_api_key_set: false,
          bedrock_access_key_set: false,
          bedrock_secret_key_set: false,
          bedrock_session_token_set: false
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
    fireEvent.click(screen.getByRole('button', { name: 'Save Connection' }));

    await waitFor(() => {
      expect(window.localStorage.getItem('odr_api_base')).toBe('https://opinion.zlyxy.me/api');
      expect(window.localStorage.getItem('odr_tenant_id')).toBe('beta-tenant');
    });
  });
});
