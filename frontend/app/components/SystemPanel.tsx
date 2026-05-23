'use client';

import React, { useEffect, useState } from 'react';

import {
  apiFetch,
  DEFAULT_TENANT,
  getAccessToken,
  getApiBase,
  getTenantId,
  setAccessToken,
  setApiBase,
  setTenantId,
} from '../../src/lib/api';
import {
  SystemConfigRead,
  SystemStatus,
  WorkerMonitorRead,
} from '../../src/lib/types';

function normalizeError(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Unexpected error';
}

type SystemPanelProps = {
  systemStatus: SystemStatus | null;
  onStatus: (message: string | null) => void;
  onError: (message: string | null) => void;
  onTenantConnectionSaved: () => void;
  onSystemStatusRefresh: () => void;
};

type SecretField =
  | 'openai_api_key'
  | 'bedrock_aws_access_key_id'
  | 'bedrock_aws_secret_access_key'
  | 'bedrock_aws_session_token';

function buildConfigPayload(config: SystemConfigRead): Record<string, unknown> {
  return {
    llm_provider: config.llm_provider,
    openai_model: config.openai_model,
    openai_max_tokens: config.openai_max_tokens,
    openai_temperature: config.openai_temperature,
    openai_timeout_seconds: config.openai_timeout_seconds,
    bedrock_model_id: config.bedrock_model_id,
    bedrock_region: config.bedrock_region,
    review_inline: config.review_inline,
    redis_url: config.redis_url,
    review_queue_name: config.review_queue_name,
    doc_repo_enabled: config.doc_repo_enabled,
    doc_repo_root: config.doc_repo_root,
    cors_allow_origins: config.cors_allow_origins,
    cors_allow_origin_regex: config.cors_allow_origin_regex,
    cors_allow_credentials: config.cors_allow_credentials,
    cors_allow_methods: config.cors_allow_methods,
    cors_allow_headers: config.cors_allow_headers,
    cors_max_age: config.cors_max_age,
    meta_agent_name: config.meta_agent_name,
    meta_agent_description: config.meta_agent_description,
    meta_agent_system_prompt: config.meta_agent_system_prompt,
    meta_agent_focus_areas: config.meta_agent_focus_areas,
    meta_agent_tone: config.meta_agent_tone,
    meta_agent_reference_notes: config.meta_agent_reference_notes,
    meta_agent_output_format: config.meta_agent_output_format,
    meta_agent_output_max_bullets: config.meta_agent_output_max_bullets,
    meta_agent_output_require_quote_excerpt: config.meta_agent_output_require_quote_excerpt,
    meta_agent_output_require_actionable: config.meta_agent_output_require_actionable,
    meta_agent_output_include_severity: config.meta_agent_output_include_severity,
    meta_agent_examples: config.meta_agent_examples,
    meta_max_directives_per_group: config.meta_max_directives_per_group,
    meta_global_dedupe_threshold: config.meta_global_dedupe_threshold,
  };
}

export function SystemPanel({
  systemStatus,
  onStatus,
  onError,
  onTenantConnectionSaved,
  onSystemStatusRefresh,
}: SystemPanelProps) {
  const [systemConfig, setSystemConfig] = useState<SystemConfigRead | null>(null);
  const [workerMonitor, setWorkerMonitor] = useState<WorkerMonitorRead | null>(null);
  const [isWorkerMonitorLoading, setIsWorkerMonitorLoading] = useState(false);
  const [apiBase, setApiBaseState] = useState('');
  const [tenantId, setTenantIdState] = useState('');
  const [accessToken, setAccessTokenState] = useState('');

  useEffect(() => {
    setApiBaseState(getApiBase());
    setTenantIdState(getTenantId());
    setAccessTokenState(getAccessToken());
  }, []);

  async function loadSystemConfig() {
    try {
      const cfg = await apiFetch<SystemConfigRead>('/settings');
      setSystemConfig(cfg);
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function loadWorkerMonitor() {
    setIsWorkerMonitorLoading(true);
    try {
      const monitor = await apiFetch<WorkerMonitorRead>('/admin/worker-monitor');
      setWorkerMonitor(monitor);
    } catch (error) {
      onError(normalizeError(error));
      setWorkerMonitor(null);
    } finally {
      setIsWorkerMonitorLoading(false);
    }
  }

  useEffect(() => {
    void loadSystemConfig();
    void loadWorkerMonitor();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      void loadWorkerMonitor();
    }, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSystemConfigSave() {
    if (!systemConfig) return;
    try {
      const payload = buildConfigPayload(systemConfig);
      const next = await apiFetch<SystemConfigRead>('/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      setSystemConfig(next);
      onStatus('Backend review settings saved.');
      onSystemStatusRefresh();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  async function handleSaveSecret(field: SecretField, value: string) {
    if (!systemConfig) return;
    try {
      const payload = { ...buildConfigPayload(systemConfig), [field]: value };
      const next = await apiFetch<SystemConfigRead>('/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      setSystemConfig(next);
      onStatus('Secret updated.');
      onSystemStatusRefresh();
    } catch (error) {
      onError(normalizeError(error));
    }
  }

  function handleTenantSave() {
    const resolvedApiBase =
      apiBase.trim() || (typeof window !== 'undefined' ? `${window.location.origin}/api` : getApiBase());
    setTenantId(tenantId || DEFAULT_TENANT);
    setApiBase(resolvedApiBase);
    setAccessToken(accessToken);
    onStatus('Connection settings saved.');
    onTenantConnectionSaved();
  }

  return (
        <div className="system-overlay">
          <div className="system-shell">
            <div className="system-header">
              <div>
                <div className="library-title">System Configuration</div>
                <div className="library-sub">
                  Manage provider, queue, storage, CORS, and local client connection settings.
                </div>
              </div>
              <div className="system-status-pills">
                <span className={`status-pill ${systemStatus?.redis.ok ? 'ok' : 'warn'}`}>
                  Redis {systemStatus?.redis.ok ? 'OK' : 'Down'}
                </span>
                <span
                  className={`status-pill ${
                    systemStatus && (systemStatus.llm?.ok ?? systemStatus.openai.ok) ? 'ok' : 'warn'
                  }`}
                >
                  LLM {systemStatus && (systemStatus.llm?.ok ?? systemStatus.openai.ok) ? 'OK' : 'Issue'}
                </span>
                <span className={`status-pill ${workerMonitor?.redis_ok ? 'ok' : 'warn'}`}>
                  Workers {workerMonitor?.redis_ok ? 'Online' : 'Unavailable'}
                </span>
              </div>
            </div>

            {systemConfig && (
              <div className="system-grid">
                <section className="system-card">
                  <div className="drawer-title">LLM Provider</div>
                  <label className="subtle">Provider</label>
                  <select
                    className="input"
                    value={systemConfig.llm_provider}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev
                          ? { ...prev, llm_provider: event.target.value as 'openai' | 'bedrock' }
                          : prev
                      )
                    }
                  >
                    <option value="openai">OpenAI</option>
                    <option value="bedrock">AWS Bedrock</option>
                  </select>
                  <div className="spacer" />
                  <label className="subtle">OpenAI Model</label>
                  <input
                    className="input"
                    value={systemConfig.openai_model}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, openai_model: event.target.value } : prev
                      )
                    }
                    placeholder="gpt-4o-mini"
                  />
                  <div className="grid-two">
                    <div>
                      <label className="subtle">Max Tokens</label>
                      <input
                        className="input"
                        type="number"
                        value={systemConfig.openai_max_tokens}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  openai_max_tokens: Math.max(1, Number(event.target.value) || 1)
                                }
                              : prev
                          )
                        }
                      />
                    </div>
                    <div>
                      <label className="subtle">Timeout (sec)</label>
                      <input
                        className="input"
                        type="number"
                        value={systemConfig.openai_timeout_seconds}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  openai_timeout_seconds: Math.max(1, Number(event.target.value) || 1)
                                }
                              : prev
                          )
                        }
                      />
                    </div>
                  </div>
                  <div className="spacer" />
                  <label className="subtle">Bedrock Model ID</label>
                  <input
                    className="input"
                    value={systemConfig.bedrock_model_id}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, bedrock_model_id: event.target.value } : prev
                      )
                    }
                    placeholder="anthropic.claude-3-5-haiku-20241022-v1:0"
                  />
                  <div className="spacer" />
                  <label className="subtle">Bedrock Region</label>
                  <input
                    className="input"
                    value={systemConfig.bedrock_region}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, bedrock_region: event.target.value } : prev
                      )
                    }
                    placeholder="us-east-1"
                  />
                  <div className="spacer" />
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={systemConfig.review_inline}
                      onChange={(event) =>
                        setSystemConfig((prev) =>
                          prev ? { ...prev, review_inline: event.target.checked } : prev
                        )
                      }
                    />
                    Run reviews inline (skip worker queue)
                  </label>
                </section>

                <section className="system-card">
                  <div className="drawer-title">Secrets</div>
                  <div className="system-secret-row">
                    <div className="subtle">OpenAI API Key</div>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => {
                        const value = window.prompt(
                          `OpenAI API key (${systemConfig.openai_api_key_set ? 'set' : 'not set'})`,
                          ''
                        );
                        if (value !== null) {
                          void handleSaveSecret('openai_api_key', value);
                        }
                      }}
                    >
                      {systemConfig.openai_api_key_set ? 'Update' : 'Set'}
                    </button>
                  </div>
                  <div className="system-secret-row">
                    <div className="subtle">Bedrock Access Key ID</div>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => {
                        const value = window.prompt(
                          `Bedrock access key (${systemConfig.bedrock_access_key_set ? 'set' : 'not set'})`,
                          ''
                        );
                        if (value !== null) {
                          void handleSaveSecret('bedrock_aws_access_key_id', value);
                        }
                      }}
                    >
                      {systemConfig.bedrock_access_key_set ? 'Update' : 'Set'}
                    </button>
                  </div>
                  <div className="system-secret-row">
                    <div className="subtle">Bedrock Secret Access Key</div>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => {
                        const value = window.prompt(
                          `Bedrock secret key (${systemConfig.bedrock_secret_key_set ? 'set' : 'not set'})`,
                          ''
                        );
                        if (value !== null) {
                          void handleSaveSecret('bedrock_aws_secret_access_key', value);
                        }
                      }}
                    >
                      {systemConfig.bedrock_secret_key_set ? 'Update' : 'Set'}
                    </button>
                  </div>
                  <div className="system-secret-row">
                    <div className="subtle">Bedrock Session Token (optional)</div>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => {
                        const value = window.prompt(
                          `Bedrock session token (${systemConfig.bedrock_session_token_set ? 'set' : 'not set'})`,
                          ''
                        );
                        if (value !== null) {
                          void handleSaveSecret('bedrock_aws_session_token', value);
                        }
                      }}
                    >
                      {systemConfig.bedrock_session_token_set ? 'Update' : 'Set'}
                    </button>
                  </div>
                </section>

                <section className="system-card">
                  <div className="drawer-title">Queue Monitor</div>
                  <div className="queue-stats-grid">
                    <div className="queue-stat">
                      <div className="subtle">Queue</div>
                      <div className="queue-stat-value">{workerMonitor?.queue?.name ?? 'review-jobs'}</div>
                    </div>
                    <div className="queue-stat">
                      <div className="subtle">Queued</div>
                      <div className="queue-stat-value">{workerMonitor?.queue?.queued ?? 0}</div>
                    </div>
                    <div className="queue-stat">
                      <div className="subtle">Running</div>
                      <div className="queue-stat-value">{workerMonitor?.queue?.started ?? 0}</div>
                    </div>
                    <div className="queue-stat">
                      <div className="subtle">Failed</div>
                      <div className="queue-stat-value">{workerMonitor?.queue?.failed ?? 0}</div>
                    </div>
                    <div className="queue-stat">
                      <div className="subtle">Deferred</div>
                      <div className="queue-stat-value">{workerMonitor?.queue?.deferred ?? 0}</div>
                    </div>
                    <div className="queue-stat">
                      <div className="subtle">Scheduled</div>
                      <div className="queue-stat-value">{workerMonitor?.queue?.scheduled ?? 0}</div>
                    </div>
                  </div>
                  <div className="spacer" />
                  <div className="drawer-title">Workers</div>
                  <div className="worker-list">
                    {(workerMonitor?.workers ?? []).length === 0 && (
                      <div className="subtle">
                        {isWorkerMonitorLoading ? 'Loading workers…' : 'No worker heartbeat detected.'}
                      </div>
                    )}
                    {(workerMonitor?.workers ?? []).map((worker) => (
                      <div className="worker-row" key={worker.name}>
                        <div>
                          <div className="history-msg">{worker.name}</div>
                          <div className="history-time">
                            state={worker.state}
                            {worker.current_job_id ? ` · job=${worker.current_job_id}` : ''}
                          </div>
                        </div>
                        <span className="pill">
                          {worker.last_heartbeat
                            ? new Date(worker.last_heartbeat).toLocaleTimeString()
                            : 'no heartbeat'}
                        </span>
                      </div>
                    ))}
                  </div>
                  {workerMonitor?.redis_error && (
                    <div className="subtle">Redis error: {workerMonitor.redis_error}</div>
                  )}
                </section>

                <section className="system-card system-card-span">
                  <div className="system-card-head">
                    <div className="drawer-title">Worker Logs</div>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => void loadWorkerMonitor()}
                      disabled={isWorkerMonitorLoading}
                    >
                      {isWorkerMonitorLoading ? 'Refreshing…' : 'Refresh Logs'}
                    </button>
                  </div>
                  <div className="worker-log-list">
                    {(workerMonitor?.logs ?? []).length === 0 && (
                      <div className="subtle">
                        {isWorkerMonitorLoading ? 'Loading logs…' : 'No worker events yet.'}
                      </div>
                    )}
                    {(workerMonitor?.logs ?? []).map((event) => (
                      <div className={`worker-log-row ${event.level}`} key={event.id}>
                        <div>
                          <div className="history-msg">
                            {event.message}
                            {event.document_title ? ` · ${event.document_title}` : ''}
                          </div>
                          <div className="history-time">
                            {new Date(event.timestamp).toLocaleString()} · {event.source}
                            {event.review_job_id ? ` · review #${event.review_job_id}` : ''}
                            {event.rq_job_id ? ` · rq ${event.rq_job_id}` : ''}
                          </div>
                          {event.detail && <div className="subtle worker-log-detail">{event.detail}</div>}
                        </div>
                        <span className={`status-pill ${event.level === 'error' ? 'warn' : 'neutral'}`}>
                          {event.level}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="system-card">
                  <div className="drawer-title">Queue & Storage</div>
                  <label className="subtle">Redis URL</label>
                  <input
                    className="input"
                    value={systemConfig.redis_url}
                    onChange={(event) =>
                      setSystemConfig((prev) => (prev ? { ...prev, redis_url: event.target.value } : prev))
                    }
                  />
                  <div className="spacer" />
                  <label className="subtle">Review Queue Name</label>
                  <input
                    className="input"
                    value={systemConfig.review_queue_name}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, review_queue_name: event.target.value } : prev
                      )
                    }
                  />
                  <div className="spacer" />
                  <label className="subtle">Document Repo Root</label>
                  <input
                    className="input"
                    value={systemConfig.doc_repo_root}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, doc_repo_root: event.target.value } : prev
                      )
                    }
                  />
                  <div className="spacer" />
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={systemConfig.doc_repo_enabled}
                      onChange={(event) =>
                        setSystemConfig((prev) =>
                          prev ? { ...prev, doc_repo_enabled: event.target.checked } : prev
                        )
                      }
                    />
                    Enable document git repository persistence
                  </label>
                </section>

                <section className="system-card">
                  <div className="drawer-title">CORS</div>
                  <label className="subtle">Allowed Origins (comma separated)</label>
                  <input
                    className="input"
                    value={systemConfig.cors_allow_origins}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, cors_allow_origins: event.target.value } : prev
                      )
                    }
                    placeholder="http://localhost:3000,https://opinion.zlyxy.me"
                  />
                  <div className="spacer" />
                  <label className="subtle">Allowed Origin Regex (optional)</label>
                  <input
                    className="input"
                    value={systemConfig.cors_allow_origin_regex ?? ''}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev
                          ? {
                              ...prev,
                              cors_allow_origin_regex: event.target.value.trim() || null
                            }
                          : prev
                      )
                    }
                    placeholder="https://.*\\.zlyxy\\.me"
                  />
                  <div className="grid-two">
                    <div>
                      <label className="subtle">Allow Methods</label>
                      <input
                        className="input"
                        value={systemConfig.cors_allow_methods}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev ? { ...prev, cors_allow_methods: event.target.value } : prev
                          )
                        }
                        placeholder="*"
                      />
                    </div>
                    <div>
                      <label className="subtle">Allow Headers</label>
                      <input
                        className="input"
                        value={systemConfig.cors_allow_headers}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev ? { ...prev, cors_allow_headers: event.target.value } : prev
                          )
                        }
                        placeholder="*"
                      />
                    </div>
                  </div>
                  <div className="grid-two">
                    <label className="toggle-row">
                      <input
                        type="checkbox"
                        checked={systemConfig.cors_allow_credentials}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev ? { ...prev, cors_allow_credentials: event.target.checked } : prev
                          )
                        }
                      />
                      Allow credentials
                    </label>
                    <div>
                      <label className="subtle">Max Age (sec)</label>
                      <input
                        className="input"
                        type="number"
                        value={systemConfig.cors_max_age}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev
                              ? { ...prev, cors_max_age: Math.max(0, Number(event.target.value) || 0) }
                              : prev
                          )
                        }
                      />
                    </div>
                  </div>
                </section>

                <section className="system-card">
                  <div className="drawer-title">Meta Agent</div>
                  <label className="subtle">Name</label>
                  <input
                    className="input"
                    value={systemConfig.meta_agent_name}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, meta_agent_name: event.target.value } : prev
                      )
                    }
                    placeholder="Meta Reviewer"
                  />
                  <div className="spacer" />
                  <label className="subtle">Description</label>
                  <input
                    className="input"
                    value={systemConfig.meta_agent_description}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, meta_agent_description: event.target.value } : prev
                      )
                    }
                    placeholder="Synthesizes reviewer comments into ranked directives."
                  />
                  <div className="spacer" />
                  <label className="subtle">System Prompt</label>
                  <textarea
                    className="input textarea"
                    rows={4}
                    value={systemConfig.meta_agent_system_prompt}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, meta_agent_system_prompt: event.target.value } : prev
                      )
                    }
                  />
                  <div className="spacer" />
                  <label className="subtle">Focus Areas (comma separated)</label>
                  <input
                    className="input"
                    value={systemConfig.meta_agent_focus_areas}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, meta_agent_focus_areas: event.target.value } : prev
                      )
                    }
                    placeholder="deduplication,conflict resolution,actionability"
                  />
                  <div className="grid-two">
                    <div>
                      <label className="subtle">Tone</label>
                      <input
                        className="input"
                        value={systemConfig.meta_agent_tone}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev ? { ...prev, meta_agent_tone: event.target.value } : prev
                          )
                        }
                        placeholder="decisive, practical"
                      />
                    </div>
                    <div>
                      <label className="subtle">Output Format</label>
                      <input
                        className="input"
                        value={systemConfig.meta_agent_output_format}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev ? { ...prev, meta_agent_output_format: event.target.value } : prev
                          )
                        }
                        placeholder="bullet_list"
                      />
                    </div>
                  </div>
                  <div className="spacer" />
                  <label className="subtle">Reference Notes (optional)</label>
                  <textarea
                    className="input textarea"
                    rows={3}
                    value={systemConfig.meta_agent_reference_notes ?? ''}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev
                          ? {
                              ...prev,
                              meta_agent_reference_notes: event.target.value.trim() || null
                            }
                          : prev
                      )
                    }
                  />
                  <div className="spacer" />
                  <label className="subtle">Examples (comma separated)</label>
                  <input
                    className="input"
                    value={systemConfig.meta_agent_examples}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev ? { ...prev, meta_agent_examples: event.target.value } : prev
                      )
                    }
                    placeholder="Use active voice,Always include next action"
                  />
                  <div className="grid-two">
                    <div>
                      <label className="subtle">Max bullets</label>
                      <input
                        className="input"
                        type="number"
                        value={systemConfig.meta_agent_output_max_bullets}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  meta_agent_output_max_bullets: Math.max(
                                    1,
                                    Number(event.target.value) || 1
                                  )
                                }
                              : prev
                          )
                        }
                      />
                    </div>
                    <div>
                      <label className="subtle">Max directives per group</label>
                      <input
                        className="input"
                        type="number"
                        value={systemConfig.meta_max_directives_per_group}
                        onChange={(event) =>
                          setSystemConfig((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  meta_max_directives_per_group: Math.max(
                                    1,
                                    Number(event.target.value) || 1
                                  )
                                }
                              : prev
                          )
                        }
                      />
                    </div>
                  </div>
                  <div className="spacer" />
                  <label className="subtle">Global dedupe threshold (0-1)</label>
                  <input
                    className="input"
                    type="number"
                    step="0.01"
                    min={0}
                    max={1}
                    value={systemConfig.meta_global_dedupe_threshold}
                    onChange={(event) =>
                      setSystemConfig((prev) =>
                        prev
                          ? {
                              ...prev,
                              meta_global_dedupe_threshold: Math.min(
                                1,
                                Math.max(0, Number(event.target.value) || 0)
                              )
                            }
                          : prev
                      )
                    }
                  />
                  <div className="spacer" />
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={systemConfig.meta_agent_output_require_actionable}
                      onChange={(event) =>
                        setSystemConfig((prev) =>
                          prev
                            ? {
                                ...prev,
                                meta_agent_output_require_actionable: event.target.checked
                              }
                            : prev
                        )
                      }
                    />
                    Require actionable directives
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={systemConfig.meta_agent_output_require_quote_excerpt}
                      onChange={(event) =>
                        setSystemConfig((prev) =>
                          prev
                            ? {
                                ...prev,
                                meta_agent_output_require_quote_excerpt: event.target.checked
                              }
                            : prev
                        )
                      }
                    />
                    Require quote excerpts
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={systemConfig.meta_agent_output_include_severity}
                      onChange={(event) =>
                        setSystemConfig((prev) =>
                          prev
                            ? {
                                ...prev,
                                meta_agent_output_include_severity: event.target.checked
                              }
                            : prev
                        )
                      }
                    />
                    Include severity/priority guidance
                  </label>
                </section>

                <section className="system-card">
                  <div className="drawer-title">Client Connection</div>
                  <label className="subtle">API Base</label>
                  <input
                    className="input"
                    value={apiBase}
                    onChange={(event) => setApiBaseState(event.target.value)}
                    placeholder="https://odr.zlyxy.me/api"
                  />
                  <div className="spacer" />
                  <label className="subtle">Tenant ID</label>
                  <input
                    className="input"
                    value={tenantId}
                    onChange={(event) => setTenantIdState(event.target.value)}
                    placeholder={DEFAULT_TENANT}
                  />
                  <div className="spacer" />
                  <label className="subtle">OIDC/JWT Access Token</label>
                  <input
                    className="input"
                    value={accessToken}
                    onChange={(event) => setAccessTokenState(event.target.value)}
                    placeholder="Paste bearer token (stored in localStorage)"
                  />
                  <div className="spacer" />
                  <button className="ghost-button" type="button" onClick={handleTenantSave}>
                    Save Connection
                  </button>
                </section>
              </div>
            )}

            <div className="system-footer">
              <button className="primary-button" type="button" onClick={() => void handleSystemConfigSave()}>
                Save Backend Settings
              </button>
            </div>
          </div>
        </div>
  );
}

export default SystemPanel;
