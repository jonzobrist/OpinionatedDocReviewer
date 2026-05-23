// @vitest-environment jsdom

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

let mockPathname = '/';
let mockSearchParams = new URLSearchParams();

function applyMockRoute(next: string) {
  const parsed = new URL(next, 'http://localhost');
  mockPathname = parsed.pathname;
  mockSearchParams = new URLSearchParams(parsed.search);
}

const pushMock = vi.fn((next: string) => {
  applyMockRoute(next);
});
const replaceMock = vi.fn((next: string) => {
  applyMockRoute(next);
});

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams.get(key),
    has: (key: string) => mockSearchParams.has(key),
    toString: () => mockSearchParams.toString(),
  }),
}));

import HomePage from '../app/page';

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeDirective(id: number, priority = 'medium') {
  return {
    id,
    content: `Directive ${id} content goes here.`,
    category: 'clarity',
    priority,
    impact: 'medium',
    effort: 'medium',
    confidence: 0.7,
    why_now: null,
    recommended_change: null,
    verification_step: null,
    status: 'open',
    assignee: null,
    due_at: null,
    rank_score: 9 - id * 0.01,
    start_offset: id * 10,
    end_offset: id * 10 + 5,
    order_index: id,
    is_unsynthesized: false,
    sources: [],
  };
}

describe('meta directive disclosure', () => {
  beforeEach(() => {
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    pushMock.mockClear();
    replaceMock.mockClear();
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
        },
      },
    });

    const directives = Array.from({ length: 8 }, (_, i) => makeDirective(9500 + i));
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      if (url.endsWith('/documents/library'))
        return json([
          {
            id: 101,
            title: 'Design Notes',
            latest_version_id: 401,
            latest_version_number: 1,
            latest_version_created_at: new Date().toISOString(),
            latest_review_status: 'completed',
            latest_review_job_id: 501,
          },
        ]);
      if (url.endsWith('/documents')) return json([]);
      if (url.includes('/documents/101/versions')) {
        return json([
          {
            id: 401,
            document_id: 101,
            version_label: 'v1',
            content: 'Alpha beta gamma',
            created_at: new Date().toISOString(),
          },
        ]);
      }
      if (url.includes('/documents/versions/401')) {
        return json({
          id: 401,
          document_id: 101,
          version_label: 'v1',
          content: 'Alpha beta gamma',
          created_at: new Date().toISOString(),
        });
      }
      if (url.includes('/documents/101/history')) return json([]);
      if (url.includes('/review-jobs') && method === 'GET') {
        return json([
          {
            id: 501,
            tenant_id: 'local-dev',
            document_version_id: 401,
            status: 'completed',
            trigger: 'upload',
            provider: 'openai',
            model: 'gpt-4o-mini',
            completed_at: new Date().toISOString(),
            created_at: new Date().toISOString(),
          },
        ]);
      }
      if (url.includes('/comments')) return json([]);
      if (url.includes('/personas')) return json([]);
      if (url.includes('/status')) return json({ redis: { ok: true }, openai: { ok: true }, llm: { ok: true } });
      if (url.includes('/meta-reviews/latest')) {
        return json({
          id: 900,
          tenant_id: 'local-dev',
          document_version_id: 401,
          review_job_id: 501,
          input_hash: 'hash',
          status: 'completed',
          is_synthesized: true,
          provider: 'openai',
          model: 'gpt-4o-mini',
          error_message: null,
          created_at: new Date().toISOString(),
          summary: {
            verdict: 'problems',
            attention_points: directives.slice(0, 5).map((d) => ({
              meta_comment_id: d.id,
              location: 'Section',
              reason: d.content,
              priority: d.priority,
              start_offset: d.start_offset,
              end_offset: d.end_offset,
              source_comment_ids: [],
            })),
            clean_sections: [],
            clean_statement: 'No section is clean enough to skip yet.',
          },
          comments: directives,
        });
      }
      return json({});
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders at most 5 directive cards by default and reveals the rest behind a toggle', async () => {
    render(<HomePage />);

    // Wait for meta mode to settle with directives loaded.
    expect(
      await screen.findByText('Verdict, top attention points, and clean sections.', {}, { timeout: 3000 }),
    ).toBeTruthy();

    // First 5 directive cards should be in the DOM.
    await waitFor(() => {
      expect(document.querySelectorAll('.comment-card[data-meta-id]').length).toBe(5);
    });

    // A disclosure button should advertise how many more there are.
    const expandButton = await screen.findByRole('button', {
      name: /Show 3 more directives/i,
    });
    expect(expandButton).toBeTruthy();

    // Clicking expands the full list.
    fireEvent.click(expandButton);
    await waitFor(() => {
      expect(document.querySelectorAll('.comment-card[data-meta-id]').length).toBe(8);
    });

    // And the button now says "Hide".
    expect(
      await screen.findByRole('button', { name: /Hide secondary directives/i }),
    ).toBeTruthy();
  });
});
