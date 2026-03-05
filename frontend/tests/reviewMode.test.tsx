// @vitest-environment jsdom

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

let mockPathname = '/';
let mockSearchParams = new URLSearchParams();

const pushMock = vi.fn();
const replaceMock = vi.fn();

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams.get(key),
    has: (key: string) => mockSearchParams.has(key),
    toString: () => mockSearchParams.toString()
  })
}));

import HomePage from '../app/page';

type ReviewJobFixture = {
  id: number;
  tenant_id: string;
  document_version_id: number;
  status: string;
  trigger: string;
  provider: string;
  model: string;
  generation_index?: number;
  is_latest_for_version?: boolean;
  comment_count?: number;
  completed_at: string | null;
  created_at: string;
};

let reviewJobsFixture: ReviewJobFixture[] = [];
let commentsByRun: Record<number, string> = {};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

describe('review generation selector', () => {
  beforeEach(() => {
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101&mode=individual');
    pushMock.mockClear();
    replaceMock.mockClear();

    reviewJobsFixture = [
      {
        id: 700,
        tenant_id: 'local-dev',
        document_version_id: 401,
        status: 'completed',
        trigger: 'manual',
        provider: 'openai',
        model: 'gpt-4o-mini',
        generation_index: 1,
        is_latest_for_version: false,
        comment_count: 1,
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString()
      },
      {
        id: 701,
        tenant_id: 'local-dev',
        document_version_id: 401,
        status: 'completed',
        trigger: 'manual',
        provider: 'openai',
        model: 'gpt-4o-mini',
        generation_index: 2,
        is_latest_for_version: true,
        comment_count: 1,
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString()
      }
    ];

    commentsByRun = {
      700: 'Older generation feedback',
      701: 'Latest generation feedback',
      703: 'Middle generation feedback',
      705: 'Newest fallback generation feedback'
    };

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

      if (url.endsWith('/documents/library')) {
        return json([
          {
            id: 101,
            title: 'Design Notes',
            latest_version_number: 1,
            latest_version_created_at: new Date().toISOString(),
            latest_review_status: 'completed',
            latest_review_job_id: 701
          }
        ]);
      }

      if (url.endsWith('/documents')) return json([]);

      if (url.endsWith('/personas')) {
        return json([
          {
            id: 1,
            tenant_id: 'local-dev',
            name: 'Clarity Editor',
            description: 'Improves flow',
            system_prompt: 'Review for clarity',
            focus_areas: ['structure'],
            tone: 'direct',
            reference_notes: null,
            output_requirements: {
              format: 'bullet_list',
              max_bullets: 4,
              require_quote_excerpt: true,
              require_actionable: true,
              include_severity: false
            },
            examples: [],
            is_default: true,
            is_system_locked: true,
            sort_order: 10,
            color_theme: '#1d8a7a',
            group_id: null,
            is_active: true,
            created_at: new Date().toISOString()
          }
        ]);
      }

      if (url.endsWith('/status')) {
        return json({
          redis: { ok: true, error: null },
          llm: { provider: 'openai', ok: true, error: null, model: 'gpt-4o-mini' },
          openai: { ok: true },
          review_queue: 'review-jobs',
          doc_repo_enabled: true
        });
      }

      if (url.endsWith('/documents/101/history')) {
        return json([
          {
            sha: 'abcdef1234567',
            message: 'Update design notes',
            authored_at: new Date().toISOString()
          }
        ]);
      }

      if (url.endsWith('/documents/101/versions')) {
        return json([
          {
            id: 401,
            tenant_id: 'local-dev',
            document_id: 101,
            version_label: 'Initial upload',
            content: '# Design Notes',
            created_at: new Date().toISOString()
          }
        ]);
      }

      if (url.includes('/review-jobs?document_version_id=401')) {
        return json(reviewJobsFixture);
      }

      if (url.includes('/comments?document_version_id=401')) {
        const parsed = new URL(url, 'http://localhost');
        const reviewJobId = Number(parsed.searchParams.get('review_job_id') ?? '0');
        const commentText = commentsByRun[reviewJobId];
        if (!commentText) return json([]);

        return json([
          {
            id: 9000 + reviewJobId,
            tenant_id: 'local-dev',
            persona_id: 1,
            document_version_id: 401,
            review_job_id: reviewJobId,
            text: commentText,
            start_offset: 0,
            end_offset: 10,
            excerpt: 'Design',
            created_at: new Date().toISOString()
          }
        ]);
      }

      if (url.includes('/meta-reviews/latest?')) {
        return json({ detail: 'Meta review run not found' }, 404);
      }

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

  it('defaults to the latest review generation and renders deterministic generation labels', async () => {
    render(<HomePage />);

    expect(await screen.findByText('Latest generation feedback')).toBeTruthy();

    const selector = (await screen.findByLabelText('Review generation')) as HTMLSelectElement;
    expect(selector.value).toBe('701');

    const optionLabels = Array.from(selector.options).map((option) => option.textContent ?? '');
    expect(optionLabels).toEqual([
      'v2 (latest) · run #701 · completed · 1 comment',
      'v1 · run #700 · completed · 1 comment'
    ]);
  });

  it('switching generations scopes comments to the selected run only', async () => {
    render(<HomePage />);

    expect(await screen.findByText('Latest generation feedback')).toBeTruthy();

    const selector = (await screen.findByLabelText('Review generation')) as HTMLSelectElement;
    fireEvent.change(selector, { target: { value: '700' } });

    expect(await screen.findByText('Older generation feedback')).toBeTruthy();
    expect(screen.queryByText('Latest generation feedback')).toBeNull();

    await waitFor(() => {
      const calls = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((args) =>
        String(args[0])
      );
      expect(calls.some((url) => url.includes('/comments?document_version_id=401&review_job_id=700'))).toBe(true);
    });
  });

  it('falls back to deterministic generation ordering when metadata is not available yet', async () => {
    reviewJobsFixture = [
      {
        id: 703,
        tenant_id: 'local-dev',
        document_version_id: 401,
        status: 'completed',
        trigger: 'manual',
        provider: 'openai',
        model: 'gpt-4o-mini',
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString()
      },
      {
        id: 701,
        tenant_id: 'local-dev',
        document_version_id: 401,
        status: 'completed',
        trigger: 'manual',
        provider: 'openai',
        model: 'gpt-4o-mini',
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString()
      },
      {
        id: 705,
        tenant_id: 'local-dev',
        document_version_id: 401,
        status: 'completed',
        trigger: 'manual',
        provider: 'openai',
        model: 'gpt-4o-mini',
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString()
      }
    ];

    render(<HomePage />);

    expect(await screen.findByText('Newest fallback generation feedback')).toBeTruthy();

    const selector = (await screen.findByLabelText('Review generation')) as HTMLSelectElement;
    const optionLabels = Array.from(selector.options).map((option) => option.textContent ?? '');

    expect(selector.value).toBe('705');
    expect(optionLabels).toEqual([
      'v3 (latest) · run #705 · completed',
      'v2 · run #703 · completed',
      'v1 · run #701 · completed'
    ]);
  });
});
