'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  apiFetch,
  DEFAULT_TENANT,
  getApiBase,
  getTenantId,
  setApiBase,
  setTenantId
} from '../src/lib/api';
import { deriveTitle } from '../src/lib/deriveTitle';
import {
  AgentTheme,
  getThemeForPersona,
  loadAgentThemes,
  saveAgentThemes
} from '../src/lib/agentThemes';
import {
  CommentRead,
  DocumentCommitRead,
  DocumentRead,
  DocumentVersionRead,
  PersonaRead,
  ReviewJobRead,
  SystemStatus
} from '../src/lib/types';

const POLL_INTERVAL_MS = 3500;
const AGENT_COLORS = ['#1d8a7a', '#2d6eea', '#b7482f', '#7a4bd3', '#c57a1b', '#0f6e88'];

export default function HomePage() {
  const [apiBase, setApiBaseState] = useState('');
  const [tenantId, setTenantIdState] = useState('');

  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [versions, setVersions] = useState<DocumentVersionRead[]>([]);
  const [comments, setComments] = useState<CommentRead[]>([]);
  const [personas, setPersonas] = useState<PersonaRead[]>([]);
  const [history, setHistory] = useState<DocumentCommitRead[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);

  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [showAgents, setShowAgents] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showLibrary, setShowLibrary] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [enabledPersonas, setEnabledPersonas] = useState<Set<number>>(new Set());
  const [recentCommentIds, setRecentCommentIds] = useState<Set<number>>(new Set());
  const [agentThemes, setAgentThemes] = useState<Record<string, AgentTheme>>({});
  const lastPollRef = useRef<number>(Date.now());

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId]
  );

  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) ?? null,
    [versions, selectedVersionId]
  );

  useEffect(() => {
    setApiBaseState(getApiBase());
    setTenantIdState(getTenantId());
    setAgentThemes(loadAgentThemes());
  }, []);

  useEffect(() => {
    void refreshAll();
  }, [tenantId]);

  useEffect(() => {
    if (!selectedVersionId) return;
    const interval = setInterval(() => {
      void loadComments(selectedVersionId, true);
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [selectedVersionId]);

  useEffect(() => {
    const interval = setInterval(() => {
      void loadSystemStatus();
    }, 8000);
    void loadSystemStatus();
    return () => clearInterval(interval);
  }, []);

  async function refreshAll() {
    setErrorMessage(null);
    try {
      const [docList, personaList] = await Promise.all([
        apiFetch<DocumentRead[]>('/documents'),
        apiFetch<PersonaRead[]>('/personas')
      ]);
      setDocuments(docList);
      setPersonas(personaList);
      if (enabledPersonas.size === 0 && personaList.length > 0) {
        setEnabledPersonas(new Set(personaList.filter((p) => p.is_active).map((p) => p.id)));
      }
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function loadSystemStatus() {
    try {
      const status = await apiFetch<SystemStatus>('/status');
      setSystemStatus(status);
    } catch {
      setSystemStatus(null);
    }
  }

  async function loadVersions(documentId: number) {
    setErrorMessage(null);
    try {
      const data = await apiFetch<DocumentVersionRead[]>(`/documents/${documentId}/versions`);
      setVersions(data);
      setSelectedVersionId(data[0]?.id ?? null);
      await loadHistory(documentId);
      if (data[0]) {
        await loadComments(data[0].id, false);
      } else {
        setComments([]);
      }
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function loadHistory(documentId: number) {
    try {
      const commits = await apiFetch<DocumentCommitRead[]>(`/documents/${documentId}/history`);
      setHistory(commits);
    } catch (error) {
      setHistory([]);
    }
  }

  async function loadComments(versionId: number, markRecent: boolean) {
    setErrorMessage(null);
    try {
      const data = await apiFetch<CommentRead[]>(`/comments?document_version_id=${versionId}`);
      if (markRecent) {
        const now = Date.now();
        const fresh = new Set<number>();
        for (const comment of data) {
          const created = new Date(comment.created_at).getTime();
          if (created > lastPollRef.current - 500) {
            fresh.add(comment.id);
          }
        }
        lastPollRef.current = now;
        setRecentCommentIds(fresh);
      }
      setComments(data);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleUploadFiles(files: FileList | File[]) {
    if (!files || files.length === 0) return;
    setIsUploading(true);
    setErrorMessage(null);
    const fileArray = Array.from(files);

    let lastDocId: number | null = null;
    let lastVersionId: number | null = null;
    for (const file of fileArray) {
      try {
        const content = await file.text();
        const title = deriveTitle(file.name, content);
        const doc = await apiFetch<DocumentRead>('/documents', {
          method: 'POST',
          body: JSON.stringify({ title })
        });
        const version = await apiFetch<DocumentVersionRead>(
          `/documents/${doc.id}/versions`,
          {
            method: 'POST',
            body: JSON.stringify({
              version_label: 'Initial upload',
              content
            })
          }
        );
        await apiFetch<ReviewJobRead>('/review-jobs', {
          method: 'POST',
          body: JSON.stringify({ document_version_id: version.id })
        });
        setDocuments((prev) => [doc, ...prev]);
        lastDocId = doc.id;
        lastVersionId = version.id;
        setVersions((prev) => [version, ...prev]);
        setComments([]);
        setStatusMessage(`Uploading "${title}"... reviews are starting.`);
      } catch (error) {
        setErrorMessage(normalizeError(error));
      }
    }
    if (lastDocId) {
      setSelectedDocumentId(lastDocId);
      await loadVersions(lastDocId);
    }
    if (lastVersionId) {
      setSelectedVersionId(lastVersionId);
      await loadComments(lastVersionId, false);
    }
    setIsUploading(false);
  }

  function handleTenantSave() {
    setTenantId(tenantId || DEFAULT_TENANT);
    setApiBase(apiBase || 'http://localhost:8006/api');
    setStatusMessage('Connection settings saved.');
    void refreshAll();
  }
  function togglePersona(id: number) {
    setEnabledPersonas((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  const visibleComments = useMemo(() => {
    return comments.filter((comment) => enabledPersonas.has(comment.persona_id));
  }, [comments, enabledPersonas]);

  const personaMap = useMemo(() => {
    const map = new Map<number, PersonaRead>();
    for (const persona of personas) {
      map.set(persona.id, persona);
    }
    return map;
  }, [personas]);

  const docSegments = useMemo(() => {
    if (!selectedVersion) return [];
    const content = selectedVersion.content;
    const sorted = visibleComments
      .filter((c) => c.start_offset >= 0 && c.end_offset >= c.start_offset)
      .sort((a, b) => a.start_offset - b.start_offset);
    const segments: Array<{ text: string; comment?: CommentRead }> = [];
    let cursor = 0;
    for (const comment of sorted) {
      if (comment.start_offset < cursor) continue;
      const safeEnd =
        comment.end_offset && comment.end_offset > comment.start_offset
          ? comment.end_offset
          : comment.start_offset + 1;
      if (comment.start_offset > cursor) {
        segments.push({ text: content.slice(cursor, comment.start_offset) });
      }
      segments.push({
        text: content.slice(comment.start_offset, safeEnd),
        comment
      });
      cursor = safeEnd;
    }
    if (cursor < content.length) {
      segments.push({ text: content.slice(cursor) });
    }
    return segments;
  }, [selectedVersion, visibleComments]);

  function updateAgentTheme(id: number, color: string, label?: string) {
    setAgentThemes((prev) => {
      const next = { ...prev, [String(id)]: { color, label } };
      saveAgentThemes(next);
      return next;
    });
  }

  return (
    <main>
      <div className="topbar">
        <div className="brand">
          <div className="logo">ODR</div>
          <div>
            <div className="brand-title">Opinionated Doc Reviewer</div>
            <div className="brand-sub">Live multi‑persona review console</div>
          </div>
        </div>
        <div className="top-actions">
          <button className="ghost-button" type="button" onClick={() => setShowLibrary((prev) => !prev)}>
            Library
          </button>
          <button className="ghost-button" type="button" onClick={() => setShowAgents((prev) => !prev)}>
            Agents
          </button>
          <button className="ghost-button" type="button" onClick={() => setShowHistory((prev) => !prev)}>
            History
          </button>
          <button className="ghost-button" type="button" onClick={() => setShowSettings((prev) => !prev)}>
            System
          </button>
        </div>
      </div>

      {(statusMessage || errorMessage) && (
        <div className={`status ${errorMessage ? 'warn' : ''}`}>
          {errorMessage ?? statusMessage}
        </div>
      )}

      {systemStatus && (!systemStatus.redis.ok || !systemStatus.openai.ok) && (
        <div className="status warn">
          {!systemStatus.redis.ok && (
            <div>Redis is offline. Start Redis to enable reviews.</div>
          )}
          {!systemStatus.openai.ok && (
            <div>OpenAI key missing. Set OPENAI_API_KEY in config or env.</div>
          )}
        </div>
      )}

      {!selectedVersion && (
        <section className="hero">
          <div
            className={`hero-drop ${isDragging ? 'drag' : ''}`}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              void handleUploadFiles(event.dataTransfer.files);
            }}
          >
            <div className="hero-title">Drop files to start a review</div>
            <div className="hero-sub">
              Markdown or text files. We auto‑create the doc, versions, and start all reviewers.
            </div>
            <label className="primary-button" style={{ cursor: 'pointer' }}>
              + Upload
              <input
                type="file"
                multiple
                accept=".md,.markdown,.txt,text/markdown,text/plain"
                onChange={(event) => {
                  if (event.target.files) {
                    void handleUploadFiles(event.target.files);
                    event.target.value = '';
                  }
                }}
              />
            </label>
            {isUploading && <div className="hero-status">Uploading and starting reviews…</div>}
          </div>
        </section>
      )}

      {selectedVersion && (
        <section className="workspace">
          <div className="doc-panel">
            <div className="doc-header">
              <div>
                <div className="doc-title">{selectedDocument?.title ?? 'Untitled document'}</div>
                <div className="doc-meta">
                  {visibleComments.length} comments · {enabledPersonas.size} active agents
                </div>
              </div>
              <div className="doc-badges">
                <span className="pill">{systemStatus?.redis.ok ? 'Live' : 'Paused'}</span>
                <span className="pill">{selectedVersion.version_label}</span>
              </div>
            </div>
            <article className="doc-body">
              {docSegments.length === 0 && <pre>{selectedVersion.content}</pre>}
              {docSegments.length > 0 && (
                <p>
                  {docSegments.map((segment, idx) => {
                    if (!segment.comment) return <span key={idx}>{segment.text}</span>;
                    const persona = personaMap.get(segment.comment.persona_id);
                    const color = persona
                      ? getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id))
                      : AGENT_COLORS[0];
                    return (
                      <mark key={idx} style={{ backgroundColor: `${color}22`, borderBottomColor: color }}>
                        {segment.text || segment.comment.excerpt || ''}
                      </mark>
                    );
                  })}
                </p>
              )}
            </article>
          </div>

          <aside className="feed-panel">
            <div className="feed-header">
              <div>
                <div className="feed-title">Live Review Feed</div>
                <div className="feed-sub">Comments appear as agents finish their passes.</div>
              </div>
              <button className="ghost-button" type="button" onClick={() => void loadComments(selectedVersion.id, false)}>
                Refresh
              </button>
            </div>
            <div className="feed-list">
              {visibleComments.length === 0 && (
                <div className="empty-feed">Waiting for agents to post comments…</div>
              )}
              {visibleComments.map((comment) => {
                const persona = personaMap.get(comment.persona_id);
                const color = persona
                  ? getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id))
                  : AGENT_COLORS[0];
                return (
                  <div
                    key={comment.id}
                    className={`comment-card ${recentCommentIds.has(comment.id) ? 'new' : ''}`}
                    style={{ borderLeftColor: color }}
                  >
                    <div className="comment-head">
                      <div className="comment-agent">
                        <span className="agent-dot" style={{ backgroundColor: color }} />
                        {persona?.name ?? `Agent ${comment.persona_id}`}
                      </div>
                      <span className="comment-time">
                        {new Date(comment.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    {comment.excerpt && <div className="comment-excerpt">“{comment.excerpt}”</div>}
                    <div className="comment-text">{comment.text}</div>
                  </div>
                );
              })}
            </div>
            {showAgents && (
              <div className="drawer">
                <div className="drawer-title">Agents</div>
                <div className="agent-list">
                  {personas.map((persona) => {
                    const color = getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id));
                    const enabled = enabledPersonas.has(persona.id);
                    return (
                      <div key={persona.id} className="agent-row">
                        <button
                          type="button"
                          className={`agent-chip ${enabled ? 'active' : ''}`}
                          style={{ borderColor: color }}
                          onClick={() => togglePersona(persona.id)}
                        >
                          <span className="agent-dot" style={{ backgroundColor: color }} />
                          <span>{persona.name}</span>
                        </button>
                        <input
                          className="agent-color"
                          type="color"
                          value={color}
                          onChange={(event) => updateAgentTheme(persona.id, event.target.value)}
                          aria-label={`${persona.name} color`}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            {showHistory && (
              <div className="drawer">
                <div className="drawer-title">History</div>
                <div className="history-list">
                  {history.length === 0 && <div className="subtle">No commits yet.</div>}
                  {history.map((commit) => (
                    <div key={commit.sha} className="history-item">
                      <div>
                        <div className="history-msg">{commit.message}</div>
                        <div className="history-time">{new Date(commit.authored_at).toLocaleString()}</div>
                      </div>
                      <span className="pill">{commit.sha.slice(0, 7)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </aside>
        </section>
      )}

      {showLibrary && (
        <div className="floating-panel">
          <div className="drawer-title">Library</div>
          <div className="history-list">
            {documents.length === 0 && <div className="subtle">No documents yet.</div>}
            {documents.map((doc) => (
              <button
                key={doc.id}
                type="button"
                className="library-item"
                onClick={() => {
                  setSelectedDocumentId(doc.id);
                  void loadVersions(doc.id);
                  setShowLibrary(false);
                }}
              >
                <div>
                  <div className="history-msg">{doc.title}</div>
                  <div className="history-time">{new Date(doc.created_at).toLocaleString()}</div>
                </div>
                <span className="pill">#{doc.id}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {showSettings && (
        <div className="floating-panel">
          <div className="drawer-title">System</div>
          <label className="subtle">API Base</label>
          <input
            className="input"
            value={apiBase}
            onChange={(event) => setApiBaseState(event.target.value)}
            placeholder="http://localhost:8006/api"
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
          <button className="primary-button" type="button" onClick={handleTenantSave}>
            Save
          </button>
        </div>
      )}
    </main>
  );
}

function normalizeError(error: unknown) {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Something went wrong.';
}

function colorForPersona(id: number) {
  return AGENT_COLORS[id % AGENT_COLORS.length];
}
