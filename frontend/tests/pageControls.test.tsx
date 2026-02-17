// @vitest-environment jsdom

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

let mockPathname = '/';
const pushMock = vi.fn((next: string) => {
  mockPathname = next;
});

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
  useSearchParams: () => ({ get: () => null })
}));

import HomePage from '../app/page';

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

describe('page controls', () => {
  beforeEach(() => {
    mockPathname = '/';
    pushMock.mockClear();
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
    const personasPayload = [
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
    ];
    const documentLibraryPayload = [
      {
        id: 101,
        title: 'Design Notes',
        latest_version_number: 1,
        latest_version_created_at: new Date().toISOString(),
        latest_review_status: 'completed',
        latest_review_job_id: 501
      }
    ];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/personas/bundle/export')) {
        return json({
          schema_version: 'v1',
          exported_at: new Date().toISOString(),
          personas: []
        });
      }
      if (url.endsWith('/personas/bundle/import') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body || '{}'));
        if (body.dry_run) {
          return json({ created: 1, updated: 0, renamed: 0, skipped: 0, errors: [] });
        }
        return json({ created: 1, updated: 0, renamed: 0, skipped: 0, errors: [] });
      }
      if (url.endsWith('/documents/library')) return json(documentLibraryPayload);
      if (url.endsWith('/documents')) return json([]);
      if (url.endsWith('/documents/101/history')) {
        return json([
          {
            sha: 'abcdef1234567',
            message: 'Update design notes',
            authored_at: new Date().toISOString()
          }
        ]);
      }
      if (url.endsWith('/review-jobs')) {
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
            created_at: new Date().toISOString()
          }
        ]);
      }
      if (url.endsWith('/personas') && (!init || init.method === 'GET')) return json(personasPayload);
      if (url.endsWith('/personas') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body || '{}'));
        return json({
          ...personasPayload[0],
          id: 2,
          name: body.name,
          system_prompt: body.system_prompt
        }, 201);
      }
      if (url.endsWith('/reset-defaults') && init?.method === 'POST') return json(personasPayload);
      if (url.includes('/personas/') && init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body || '{}'));
        return json({ ...personasPayload[0], ...body });
      }
      if (url.includes('/personas/') && init?.method === 'DELETE') {
        return new Response(null, { status: 204 });
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
          redis_url: 'redis://localhost:6379/0',
          review_queue_name: 'review-jobs',
          doc_repo_enabled: true,
          doc_repo_root: '.run/doc-repos',
          cors_allow_origins: 'http://localhost:3000,https://opinion.zlyxy.me',
          cors_allow_origin_regex: null,
          cors_allow_credentials: false,
          cors_allow_methods: '*',
          cors_allow_headers: '*',
          cors_max_age: 600,
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
          redis_url: body.redis_url ?? 'redis://localhost:6379/0',
          review_queue_name: body.review_queue_name ?? 'review-jobs',
          doc_repo_enabled: body.doc_repo_enabled ?? true,
          doc_repo_root: body.doc_repo_root ?? '.run/doc-repos',
          cors_allow_origins: body.cors_allow_origins ?? 'http://localhost:3000,https://opinion.zlyxy.me',
          cors_allow_origin_regex: body.cors_allow_origin_regex ?? null,
          cors_allow_credentials: body.cors_allow_credentials ?? false,
          cors_allow_methods: body.cors_allow_methods ?? '*',
          cors_allow_headers: body.cors_allow_headers ?? '*',
          cors_max_age: body.cors_max_age ?? 600,
          openai_api_key_set: false,
          bedrock_access_key_set: false,
          bedrock_secret_key_set: false,
          bedrock_session_token_set: false
        });
      }
      if (url.endsWith('/health')) return json({ status: 'ok' });
      if (url.endsWith('/admin/overview')) {
        return json({
          tenant_id: 'local-dev',
          repository: {
            enabled: true,
            root: '.run/doc-repos',
            tenant_root: '.run/doc-repos/local-dev',
            repository_count: 1
          },
          users: { total: 1, admins: 1, active: 1 },
          documents: { total: 1, archived: 0, active: 1 },
          jobs: { in_progress: 0, completed: 1, failed: 0, recent_total: 1 },
          in_progress_jobs: [],
          recent_jobs: [
            {
              id: 501,
              document_version_id: 401,
              document_id: 101,
              document_title: 'Design Notes',
              status: 'completed',
              trigger: 'upload',
              provider: 'openai',
              model: 'gpt-4o-mini',
              created_at: new Date().toISOString(),
              completed_at: new Date().toISOString()
            }
          ],
          recent_actions: [
            {
              id: 1,
              actor_user_id: 1,
              actor_email: 'admin@local',
              action: 'permission.update',
              target_type: 'permission',
              target_id: 1,
              details: 'level=viewer',
              created_at: new Date().toISOString()
            }
          ]
        });
      }
      if (url.includes('/admin/users')) {
        if (!init?.method || init.method === 'GET') {
          return json([
            {
              id: 1,
              tenant_id: 'local-dev',
              name: 'Local Admin',
              email: 'admin@local',
              role: 'admin',
              is_active: true,
              created_at: new Date().toISOString()
            }
          ]);
        }
        if (init.method === 'POST') {
          const body = JSON.parse(String(init.body || '{}'));
          return json(
            {
              id: 2,
              tenant_id: 'local-dev',
              name: body.name,
              email: body.email,
              role: body.role,
              is_active: true,
              created_at: new Date().toISOString()
            },
            201
          );
        }
      }
      if (url.includes('/admin/permissions')) {
        if (!init?.method || init.method === 'GET')
          return json([
            {
              id: 1,
              tenant_id: 'local-dev',
              document_id: 101,
              user_id: 1,
              permission_level: 'viewer',
              created_at: new Date().toISOString(),
              user_name: 'Local Admin',
              user_email: 'admin@local'
            }
          ]);
        if (init.method === 'POST') {
          const body = JSON.parse(String(init.body || '{}'));
          return json(
            {
              id: 1,
              tenant_id: 'local-dev',
              document_id: body.document_id,
              user_id: body.user_id,
              permission_level: body.permission_level,
              created_at: new Date().toISOString(),
              user_name: 'Local Admin',
              user_email: 'admin@local'
            },
            201
          );
        }
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

  it('opens library overlay from top nav', async () => {
    mockPathname = '/library';
    render(<HomePage />);
    expect(await screen.findByText('Review Ledger')).toBeTruthy();
  });

  it('saves system settings to localStorage', async () => {
    mockPathname = '/system';
    render(<HomePage />);
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

  it('creates a new agent from agents page', async () => {
    mockPathname = '/agents';
    render(<HomePage />);

    fireEvent.click(await screen.findByRole('button', { name: 'New Agent' }));
    fireEvent.change(screen.getByPlaceholderText('Reviewer name'), {
      target: { value: 'Security Hawk' }
    });
    fireEvent.change(screen.getByPlaceholderText('How this agent should review and respond...'), {
      target: { value: 'Find security issues' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Agent' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save Agent' })).toBeTruthy();
    });
  });

  it('opens admin overlay from route', async () => {
    mockPathname = '/admin';
    render(<HomePage />);
    expect(await screen.findByText('Administrator')).toBeTruthy();
    expect(await screen.findByText('Repository')).toBeTruthy();
    expect(await screen.findByText('Permission Matrix')).toBeTruthy();
    expect(await screen.findByText('Recent Admin Actions')).toBeTruthy();
    expect((await screen.findAllByText('Design Notes')).length).toBeGreaterThan(0);
    expect(await screen.findByText('level=viewer')).toBeTruthy();
    expect(await screen.findByText('permission.update · permission #1')).toBeTruthy();
  });

  it('opens history overlay from route', async () => {
    mockPathname = '/history';
    render(<HomePage />);
    expect(await screen.findByText('Review Runs')).toBeTruthy();
    expect(await screen.findByText('Document Commits')).toBeTruthy();
    expect(await screen.findByText('Update design notes')).toBeTruthy();
  });

  it('previews and applies agent import bundle', async () => {
    mockPathname = '/agents';
    render(<HomePage />);

    const fileInput = document.querySelector('input[type="file"][accept="application/json,.json"]');
    expect(fileInput).toBeTruthy();
    const bundle = {
      name: 'agents.json',
      text: async () =>
        JSON.stringify({
          schema_version: 'v1',
          personas: []
        })
    };
    fireEvent.change(fileInput as HTMLInputElement, { target: { files: [bundle] } });

    expect(await screen.findByText(/Import Preview: agents.json/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Apply Import' }));
    expect(await screen.findByText(/Import complete:/i)).toBeTruthy();
  });
});
