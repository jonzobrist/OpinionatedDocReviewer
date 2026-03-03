// @vitest-environment jsdom

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

let mockPathname = '/';
let mockSearchParams = new URLSearchParams();
let metaLatestScenario: 'missing' | 'available' | 'pending' | 'failed' = 'missing';
let metaStatusPollSequence: Array<'running' | 'completed' | 'failed' | 'not_found'> = [];
let metaStatusPollRequestCount = 0;
let metaStatusReachedCompletion = false;

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
    toString: () => mockSearchParams.toString()
  })
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
    mockSearchParams = new URLSearchParams();
    metaLatestScenario = 'missing';
    metaStatusPollSequence = [];
    metaStatusPollRequestCount = 0;
    metaStatusReachedCompletion = false;
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
      if (url.includes('/review-jobs') && (!init?.method || init.method === 'GET')) {
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
      if (url.endsWith('/review-jobs') && init?.method === 'POST') {
        return json(
          {
            id: 777,
            tenant_id: 'local-dev',
            document_version_id: 401,
            status: 'queued',
            trigger: 'manual',
            provider: 'openai',
            model: 'gpt-4o-mini',
            completed_at: null,
            created_at: new Date().toISOString()
          },
          201
        );
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
      if (url.endsWith('/documents/202/versions')) {
        return json([
          {
            id: 402,
            tenant_id: 'local-dev',
            document_id: 202,
            version_label: 'Imported',
            content: '# Imported Bundle',
            created_at: new Date().toISOString()
          }
        ]);
      }
      if (url.includes('/comments?document_version_id=401&review_job_id=501')) {
        return json([]);
      }
      if (url.includes('/comments?document_version_id=401') && !url.includes('review_job_id=')) {
        return json([
          {
            id: 601,
            tenant_id: 'local-dev',
            persona_id: 1,
            document_version_id: 401,
            review_job_id: 500,
            text: 'Clarify this section.',
            start_offset: 0,
            end_offset: 10,
            excerpt: 'Design',
            created_at: new Date().toISOString()
          }
        ]);
      }
      if (url.includes('/meta-reviews/latest?')) {
        const parsed = new URL(url, 'http://localhost');
        const targetsPrimaryVersion = parsed.searchParams.get('document_version_id') === '401';
        const includeComments = parsed.searchParams.get('include_comments') !== 'false';
        const asAvailable = () =>
          json({
            id: 901,
            tenant_id: 'local-dev',
            document_version_id: 401,
            review_job_id: 501,
            input_hash: 'meta-hash',
            status: 'completed',
            is_synthesized: true,
            provider: 'openai',
            model: 'gpt-4o-mini',
            error_message: null,
            created_at: new Date().toISOString(),
            comments: [
              {
                id: 9501,
                content: 'Clarify the opening section to reduce ambiguity.',
                category: 'clarity',
                priority: 'high',
                impact: 'high',
                effort: 'low',
                confidence: 0.88,
                why_now: 'Readers may misinterpret scope.',
                recommended_change: 'Add a one-sentence framing statement.',
                verification_step: 'Re-run clarity reviewer and confirm no repeat issue.',
                status: 'open',
                assignee: null,
                due_at: null,
                rank_score: 8.4,
                start_offset: 0,
                end_offset: 10,
                order_index: 0,
                is_unsynthesized: false,
                sources: [
                  {
                    id: 9701,
                    comment_id: 601,
                    reviewer_name: 'Clarity Editor',
                    reviewer_id: 1,
                    original_comment_text: 'Clarify this section.'
                  }
                ]
              }
            ]
          });
        const asPending = () =>
          json({
            id: 902,
            tenant_id: 'local-dev',
            document_version_id: 401,
            review_job_id: 501,
            input_hash: 'meta-pending',
            status: 'running',
            is_synthesized: false,
            provider: 'openai',
            model: 'gpt-4o-mini',
            error_message: null,
            created_at: new Date().toISOString(),
            comments: []
          });
        const asFailed = () =>
          json({
            id: 904,
            tenant_id: 'local-dev',
            document_version_id: 401,
            review_job_id: 501,
            input_hash: 'meta-failed',
            status: 'failed',
            is_synthesized: false,
            provider: 'openai',
            model: 'gpt-4o-mini',
            error_message: 'Provider timeout',
            created_at: new Date().toISOString(),
            comments: []
          });

        if (!targetsPrimaryVersion) {
          return json({ detail: 'Meta review run not found' }, 404);
        }

        if (!includeComments) {
          metaStatusPollRequestCount += 1;
          const nextPollState = metaStatusPollSequence.shift() ?? null;
          if (nextPollState === 'running') {
            return asPending();
          }
          if (nextPollState === 'completed') {
            metaStatusReachedCompletion = true;
            return json({
              id: 901,
              tenant_id: 'local-dev',
              document_version_id: 401,
              review_job_id: 501,
              input_hash: 'meta-hash',
              status: 'completed',
              is_synthesized: true,
              provider: 'openai',
              model: 'gpt-4o-mini',
              error_message: null,
              created_at: new Date().toISOString(),
              comments: []
            });
          }
          if (nextPollState === 'failed') {
            return asFailed();
          }
          if (nextPollState === 'not_found') {
            return json({ detail: 'Meta review run not found' }, 404);
          }

          if (metaStatusReachedCompletion || metaLatestScenario === 'available') return asAvailable();
          if (metaLatestScenario === 'pending') return asPending();
          if (metaLatestScenario === 'failed') return asFailed();
          return json({ detail: 'Meta review run not found' }, 404);
        }

        if (metaStatusReachedCompletion || metaLatestScenario === 'available') return asAvailable();
        if (metaLatestScenario === 'pending') return asPending();
        if (metaLatestScenario === 'failed') return asFailed();
        return json({ detail: 'Meta review run not found' }, 404);
      }
      if (url.endsWith('/meta-reviews') && init?.method === 'POST') {
        return json(
          {
            id: 903,
            tenant_id: 'local-dev',
            document_version_id: 401,
            review_job_id: 501,
            input_hash: 'meta-created',
            status: 'completed',
            is_synthesized: true,
            provider: 'openai',
            model: 'gpt-4o-mini',
            error_message: null,
            created_at: new Date().toISOString(),
            comments: []
          },
          201
        );
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
          meta_agent_name: 'Meta Reviewer',
          meta_agent_description: 'Synthesizes reviewer comments into ranked directives.',
          meta_agent_system_prompt: 'Synthesize reviewer comments into concise actions.',
          meta_agent_focus_areas: 'deduplication,conflict resolution,actionability',
          meta_agent_tone: 'decisive, practical',
          meta_agent_reference_notes: null,
          meta_agent_output_format: 'bullet_list',
          meta_agent_output_max_bullets: 5,
          meta_agent_output_require_quote_excerpt: false,
          meta_agent_output_require_actionable: true,
          meta_agent_output_include_severity: true,
          meta_agent_examples: '',
          meta_max_directives_per_group: 5,
          meta_global_dedupe_threshold: 0.72,
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
          meta_agent_name: body.meta_agent_name ?? 'Meta Reviewer',
          meta_agent_description:
            body.meta_agent_description ?? 'Synthesizes reviewer comments into ranked directives.',
          meta_agent_system_prompt:
            body.meta_agent_system_prompt ?? 'Synthesize reviewer comments into concise actions.',
          meta_agent_focus_areas:
            body.meta_agent_focus_areas ?? 'deduplication,conflict resolution,actionability',
          meta_agent_tone: body.meta_agent_tone ?? 'decisive, practical',
          meta_agent_reference_notes: body.meta_agent_reference_notes ?? null,
          meta_agent_output_format: body.meta_agent_output_format ?? 'bullet_list',
          meta_agent_output_max_bullets: body.meta_agent_output_max_bullets ?? 5,
          meta_agent_output_require_quote_excerpt:
            body.meta_agent_output_require_quote_excerpt ?? false,
          meta_agent_output_require_actionable:
            body.meta_agent_output_require_actionable ?? true,
          meta_agent_output_include_severity:
            body.meta_agent_output_include_severity ?? true,
          meta_agent_examples: body.meta_agent_examples ?? '',
          meta_max_directives_per_group: body.meta_max_directives_per_group ?? 5,
          meta_global_dedupe_threshold: body.meta_global_dedupe_threshold ?? 0.72,
          openai_api_key_set: false,
          bedrock_access_key_set: false,
          bedrock_secret_key_set: false,
          bedrock_session_token_set: false
        });
      }
      if (url.endsWith('/documents/import-bundle') && init?.method === 'POST') {
        return json(
          {
            document_id: 202,
            version_id: 402,
            review_job_id: null,
            comments_imported: 1,
            personas_created: 0,
            meta_comments_imported: 0
          },
          201
        );
      }
      if (url.endsWith('/health')) return json({ status: 'ok' });
      if (url.endsWith('/admin/worker-monitor')) {
        return json({
          redis_ok: true,
          redis_error: null,
          queue: {
            name: 'review-jobs',
            queued: 1,
            started: 1,
            scheduled: 0,
            deferred: 0,
            failed: 0,
            finished: 3
          },
          workers: [
            {
              name: 'worker-a',
              state: 'busy',
              queues: ['review-jobs'],
              current_job_id: 'rq-123',
              last_heartbeat: new Date().toISOString()
            }
          ],
          logs: [
            {
              id: 'log-1',
              timestamp: new Date().toISOString(),
              level: 'info',
              source: 'review',
              message: 'Review job #501 is completed',
              detail: null,
              review_job_id: 501,
              rq_job_id: null,
              document_title: 'Design Notes'
            }
          ]
        });
      }
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

  it('routes brand logo to library', async () => {
    render(<HomePage />);
    const brand = await screen.findByRole('link', { name: /opinionated doc reviewer/i });
    expect(brand.getAttribute('href')).toBe('/library');
  });

  it('defaults to meta mode when latest meta directives are available', async () => {
    metaLatestScenario = 'available';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(await screen.findByText('Clarify the opening section to reduce ambiguity.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull();
  });

  it('keeps meta mode and shows explicit error state when latest meta synthesis failed', async () => {
    metaLatestScenario = 'failed';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(await screen.findByText('Unable to load meta directives right now.')).toBeTruthy();
    expect(await screen.findByText('Meta synthesis failed: Provider timeout')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull();
  });

  it('shows explicit pending state while meta synthesis is still running', async () => {
    metaLatestScenario = 'pending';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(await screen.findByText('Meta directives are still being synthesized…')).toBeTruthy();
    expect(await screen.findByText('Meta directives are still being synthesized.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull();
  });

  it('polls lightweight meta status while pending and hydrates full directives on completion', async () => {
    metaLatestScenario = 'pending';
    metaStatusPollSequence = ['running', 'completed'];
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(await screen.findByText('Meta directives are still being synthesized.')).toBeTruthy();
    expect(await screen.findByText('Meta review loaded (1 directives).')).toBeTruthy();
    expect(await screen.findByText('Clarify the opening section to reduce ambiguity.')).toBeTruthy();

    const calls = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((args) =>
      String(args[0])
    );
    const statusPollCalls = calls.filter(
      (url) => url.includes('/meta-reviews/latest?') && url.includes('include_comments=false')
    );
    expect(statusPollCalls.length).toBeGreaterThan(0);
    expect(statusPollCalls.some((url) => url.includes('review_job_id=501'))).toBe(true);

    const hydratedCalls = calls.filter(
      (url) => url.includes('/meta-reviews/latest?') && !url.includes('include_comments=false')
    );
    expect(hydratedCalls.length).toBeGreaterThan(1);
  });

  it('bounds pending meta polling and pauses auto-refresh after max attempts', async () => {
    metaLatestScenario = 'pending';
    metaStatusPollSequence = Array.from({ length: 16 }, () => 'running');
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    await waitFor(
      () => {
        expect(
          screen.getByText(
            'Meta directives are still being synthesized. Auto-refresh paused to avoid noisy polling.'
          )
        ).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(metaStatusPollRequestCount).toBe(8);
  });

  it('recompute retries meta synthesis from failed state and keeps meta mode active', async () => {
    metaLatestScenario = 'failed';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(await screen.findByText('Unable to load meta directives right now.')).toBeTruthy();
    const recompute = await screen.findByRole('button', { name: 'Recompute' });
    fireEvent.click(recompute);

    expect(await screen.findByText('No meta directives produced for this version.')).toBeTruthy();
    expect(await screen.findByText('No significant issues found.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull();

    const postCall = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls
      .slice()
      .reverse()
      .find((args) => String(args[0]).endsWith('/meta-reviews') && args[1]?.method === 'POST');
    expect(postCall).toBeTruthy();
    const body = JSON.parse(String(postCall?.[1]?.body ?? '{}'));
    expect(body).toMatchObject({
      document_version_id: 401,
      review_job_id: 501,
      force: true
    });
  });

  it('recompute from missing meta run after manual toggle does not regress to individual mode', async () => {
    metaLatestScenario = 'missing';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(
      await screen.findByText('Anchored reviewer comments for this document version.')
    ).toBeTruthy();
    expect(
      await screen.findByText('No meta directives found for this run yet. Showing individual reviewer comments.')
    ).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Meta' }));
    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(
      await screen.findAllByText('No meta directives available for this run yet. Recompute to synthesize now.')
    ).toHaveLength(2);

    fireEvent.click(await screen.findByRole('button', { name: 'Recompute' }));
    expect(await screen.findByText('No meta directives produced for this version.')).toBeTruthy();
    expect(await screen.findByText('No significant issues found.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull();
  });

  it('falls back to individual mode when meta is missing, while preserving manual mode toggle', async () => {
    metaLatestScenario = 'missing';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(
      await screen.findByText('Anchored reviewer comments for this document version.')
    ).toBeTruthy();
    expect(
      await screen.findByText('No meta directives found for this run yet. Showing individual reviewer comments.')
    ).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Meta' }));
    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(
      (
        await screen.findAllByText(
          'No meta directives available for this run yet. Recompute to synthesize now.'
        )
      ).length
    ).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: 'Individual' }));
    expect(await screen.findByRole('button', { name: 'Refresh' })).toBeTruthy();
  });

  it('restores individual mode from URL query state', async () => {
    metaLatestScenario = 'available';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101&mode=individual');
    render(<HomePage />);

    expect(
      await screen.findByText('Anchored reviewer comments for this document version.')
    ).toBeTruthy();
    expect(await screen.findByRole('button', { name: 'Refresh' })).toBeTruthy();
  });

  it('persists and restores selected meta directive via URL query state', async () => {
    metaLatestScenario = 'available';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101&mode=meta&directive=9501');
    render(<HomePage />);

    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector('.comment-card[data-meta-id="9501"].selected')).toBeTruthy();
    });

    replaceMock.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'Individual' }));
    await waitFor(() => {
      const urls = replaceMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes('mode=individual') && !url.includes('directive='))).toBe(true);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Meta' }));
    let directiveCard: Element | null = null;
    await waitFor(() => {
      directiveCard = document.querySelector('.comment-card[data-meta-id="9501"]');
      expect(directiveCard).toBeTruthy();
    });
    fireEvent.click(directiveCard as HTMLElement);
    await waitFor(() => {
      const urls = replaceMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes('mode=meta') && url.includes('directive=9501'))).toBe(true);
    });
  });

  it('clears invalid directive IDs from URL state gracefully', async () => {
    metaLatestScenario = 'available';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101&mode=meta&directive=9999');
    render(<HomePage />);

    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(await screen.findByText('Requested directive #9999 is not available for this run.')).toBeTruthy();

    await waitFor(() => {
      const urls = replaceMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes('mode=meta') && !url.includes('directive='))).toBe(true);
    });
  });

  it('drills down from a meta directive source into the linked reviewer comment', async () => {
    metaLatestScenario = 'available';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101&mode=meta&directive=9501');
    render(<HomePage />);

    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    fireEvent.click((await screen.findAllByText('Show sources (1)'))[0]);
    expect(await screen.findByText('Anchor excerpt: “Design”')).toBeTruthy();

    replaceMock.mockClear();
    fireEvent.click(await screen.findByRole('button', { name: 'Jump to source #601' }));

    expect(
      await screen.findByText('Anchored reviewer comments for this document version.')
    ).toBeTruthy();
    expect(await screen.findByRole('button', { name: 'Refresh' })).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelector('.comment-card[data-comment-id="601"].selected')).toBeTruthy();
    });
    await waitFor(() => {
      const urls = replaceMock.mock.calls.map((call) => String(call[0]));
      expect(urls.some((url) => url.includes('mode=individual') && !url.includes('directive='))).toBe(true);
    });
  });

  it('supports drill-down roundtrip back to meta mode without breaking meta-first flow', async () => {
    metaLatestScenario = 'available';
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);

    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Refresh' })).toBeNull();

    fireEvent.click((await screen.findAllByText('Show sources (1)'))[0]);
    fireEvent.click(await screen.findByRole('button', { name: 'Jump to source #601' }));
    expect(await screen.findByRole('button', { name: 'Refresh' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Meta' }));
    expect(await screen.findByText('Meta-synthesized directives with source attribution.')).toBeTruthy();
    expect(await screen.findByText('Clarify the opening section to reduce ambiguity.')).toBeTruthy();
  });

  it('refresh falls back to latest available comments when selected run is empty', async () => {
    mockPathname = '/';
    mockSearchParams = new URLSearchParams('doc=101');
    render(<HomePage />);
    const refresh = await screen.findByRole('button', { name: 'Refresh' });
    fireEvent.click(refresh);
    await screen.findByText(/Loaded 1 comments from latest available run\./i);

    const calls = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((args) =>
      String(args[0])
    );
    expect(calls.some((url) => url.includes('/comments?document_version_id=401&review_job_id=501'))).toBe(true);
    expect(
      calls.some(
        (url) => url.includes('/comments?document_version_id=401') && !url.includes('review_job_id=')
      )
    ).toBe(true);
  });

  it('saves system settings to localStorage', async () => {
    mockPathname = '/system';
    render(<HomePage />);
    const apiInput = await screen.findByPlaceholderText('https://odr.zlyxy.me/api');
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

  it('imports review bundle from library', async () => {
    mockPathname = '/library';
    render(<HomePage />);

    const importInput = document.querySelector(
      'input[type="file"][accept="application/json,.json,application/zip,.zip"]'
    );
    expect(importInput).toBeTruthy();
    const bundle = {
      name: 'review_bundle.json',
      text: async () =>
        JSON.stringify({
          schema_version: 'odr.review-bundle.v2',
          document: { title: 'Imported doc' },
          version: { version_label: 'Imported', content: 'hello world' },
          comments: [
            {
              persona_name: 'Clarity Editor',
              text: 'Clarify',
              start_offset: 0,
              end_offset: 5
            }
          ]
        })
    };
    fireEvent.change(importInput as HTMLInputElement, { target: { files: [bundle] } });

    await screen.findByText(/Imported 1 review bundle/i);
  });
});
