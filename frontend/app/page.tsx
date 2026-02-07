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
  DocumentLibraryEntry,
  DocumentRead,
  DocumentVersionRead,
  PersonaRead,
  ReviewJobRead,
  SystemStatus
} from '../src/lib/types';

const POLL_INTERVAL_MS = 1200;
const AGENT_COLORS = ['#1d8a7a', '#2d6eea', '#b7482f', '#7a4bd3', '#c57a1b', '#0f6e88'];

type DocSegment = { text: string; comment?: CommentRead };
type ConnectorPath = { id: number; path: string; color: string };

export default function HomePage() {
  const [apiBase, setApiBaseState] = useState('');
  const [tenantId, setTenantIdState] = useState('');

  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [libraryEntries, setLibraryEntries] = useState<DocumentLibraryEntry[]>([]);
  const [versions, setVersions] = useState<DocumentVersionRead[]>([]);
  const [comments, setComments] = useState<CommentRead[]>([]);
  const [reviewJobs, setReviewJobs] = useState<ReviewJobRead[]>([]);
  const [personas, setPersonas] = useState<PersonaRead[]>([]);
  const [history, setHistory] = useState<DocumentCommitRead[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);

  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [selectedReviewJobId, setSelectedReviewJobId] = useState<number | null>(null);
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
  const [libraryFilter, setLibraryFilter] = useState<'all' | 'needs' | 'reviewed'>('all');
  const [librarySearch, setLibrarySearch] = useState('');
  const [connectorPaths, setConnectorPaths] = useState<ConnectorPath[]>([]);
  const lastPollRef = useRef<number>(Date.now());
  const workspaceRef = useRef<HTMLElement | null>(null);
  const docPanelRef = useRef<HTMLDivElement | null>(null);
  const feedListRef = useRef<HTMLDivElement | null>(null);
  const markRefs = useRef<Record<number, HTMLElement | null>>({});
  const cardRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const selectedDocument = useMemo(() => {
    const fromLibrary = libraryEntries.find((doc) => doc.id === selectedDocumentId);
    if (fromLibrary) return fromLibrary;
    return documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  }, [documents, libraryEntries, selectedDocumentId]);

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
      void loadComments(selectedVersionId, true, selectedReviewJobId);
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [selectedVersionId, selectedReviewJobId]);

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
      const [docList, personaList, libraryList] = await Promise.all([
        apiFetch<DocumentRead[]>('/documents'),
        apiFetch<PersonaRead[]>('/personas'),
        apiFetch<DocumentLibraryEntry[]>('/documents/library')
      ]);
      setDocuments(docList);
      setPersonas(personaList);
      setLibraryEntries(libraryList);
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
      const latestVersion = data.length > 0 ? data[data.length - 1] : null;
      setSelectedVersionId(latestVersion?.id ?? null);
      await loadHistory(documentId);
      if (latestVersion) {
        await loadReviewJobsForVersion(latestVersion.id);
      } else {
        setComments([]);
        setReviewJobs([]);
        setSelectedReviewJobId(null);
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

  async function loadReviewJobsForVersion(versionId: number) {
    try {
      const jobs = await apiFetch<ReviewJobRead[]>(`/review-jobs?document_version_id=${versionId}`);
      setReviewJobs(jobs);
      const latest = jobs.length > 0 ? jobs[jobs.length - 1] : null;
      setSelectedReviewJobId(latest?.id ?? null);
      if (latest) {
        const data = await loadComments(versionId, false, latest.id);
        if (data.length === 0) {
          await loadComments(versionId, false, null);
        }
      } else {
        await loadComments(versionId, false, null);
      }
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function loadComments(
    versionId: number,
    markRecent: boolean,
    reviewJobId?: number | null
  ): Promise<CommentRead[]> {
    setErrorMessage(null);
    try {
      const query = reviewJobId ? `&review_job_id=${reviewJobId}` : '';
      const data = await apiFetch<CommentRead[]>(`/comments?document_version_id=${versionId}${query}`);
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
      return data;
    } catch (error) {
      setErrorMessage(normalizeError(error));
      return [];
    }
  }

  async function handleRunReview(versionId: number) {
    setErrorMessage(null);
    try {
      const job = await apiFetch<ReviewJobRead>('/review-jobs', {
        method: 'POST',
        body: JSON.stringify({ document_version_id: versionId, trigger: 'manual' })
      });
      setReviewJobs((prev) => [...prev, job]);
      setSelectedReviewJobId(job.id);
      setStatusMessage('Review started. Comments will arrive shortly.');
      await loadComments(versionId, false, job.id);
      void refreshAll();
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
    let lastReviewJobId: number | null = null;
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
        setSelectedDocumentId(doc.id);
        setSelectedVersionId(version.id);
        setVersions((prev) => {
          const filtered = prev.filter((item) => item.document_id !== doc.id);
          return [...filtered, version];
        });
        setComments([]);
        setStatusMessage(`Loaded "${title}". Reviewers are joining now.`);

        const job = await apiFetch<ReviewJobRead>('/review-jobs', {
          method: 'POST',
          body: JSON.stringify({ document_version_id: version.id, trigger: 'auto' })
        });
        setDocuments((prev) => [doc, ...prev]);
        lastDocId = doc.id;
        lastVersionId = version.id;
        setSelectedReviewJobId(job.id);
        setReviewJobs((prev) => [...prev, job]);
        lastReviewJobId = job.id;
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
      await loadComments(lastVersionId, false, lastReviewJobId);
    }
    setIsUploading(false);
    void refreshAll();
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
    return comments
      .filter((comment) => enabledPersonas.has(comment.persona_id))
      .sort((a, b) => {
        const aAnchored =
          Boolean(a.excerpt) && a.start_offset >= 0 && a.end_offset > a.start_offset;
        const bAnchored =
          Boolean(b.excerpt) && b.start_offset >= 0 && b.end_offset > b.start_offset;
        if (aAnchored !== bAnchored) {
          return aAnchored ? -1 : 1;
        }
        if (aAnchored && bAnchored && a.start_offset !== b.start_offset) {
          return a.start_offset - b.start_offset;
        }
        if (aAnchored && bAnchored && a.end_offset !== b.end_offset) {
          return a.end_offset - b.end_offset;
        }
        return a.id - b.id;
      });
  }, [comments, enabledPersonas]);

  const anchoredComments = useMemo(
    () =>
      visibleComments.filter(
        (comment) =>
          Boolean(comment.excerpt) &&
          comment.start_offset >= 0 &&
          comment.end_offset > comment.start_offset
      ),
    [visibleComments]
  );

  const personaMap = useMemo(() => {
    const map = new Map<number, PersonaRead>();
    for (const persona of personas) {
      map.set(persona.id, persona);
    }
    return map;
  }, [personas]);

  const filteredLibrary = useMemo(() => {
    if (libraryFilter === 'all') return libraryEntries;
    if (libraryFilter === 'needs') {
      return libraryEntries.filter((entry) => entry.needs_review);
    }
    return libraryEntries.filter((entry) => !entry.needs_review);
  }, [libraryEntries, libraryFilter]);

  const filteredLibraryWithSearch = useMemo(() => {
    if (!librarySearch.trim()) return filteredLibrary;
    const query = librarySearch.trim().toLowerCase();
    return filteredLibrary.filter((entry) => entry.title.toLowerCase().includes(query));
  }, [filteredLibrary, librarySearch]);

  const docSegments = useMemo(() => {
    if (!selectedVersion) return [];
    const content = selectedVersion.content;
    const sorted = [...anchoredComments].sort((a, b) => a.start_offset - b.start_offset);
    const segments: DocSegment[] = [];
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
  }, [selectedVersion, anchoredComments]);

  useEffect(() => {
    if (!selectedVersion) {
      setConnectorPaths([]);
      return;
    }
    const recalc = () => {
      const workspace = workspaceRef.current;
      const docPanel = docPanelRef.current;
      const feedList = feedListRef.current;
      if (!workspace || !docPanel || !feedList) return;

      const workspaceRect = workspace.getBoundingClientRect();
      const nextPaths: ConnectorPath[] = [];

      for (const comment of anchoredComments) {
        const mark = markRefs.current[comment.id];
        const card = cardRefs.current[comment.id];
        if (!mark || !card) continue;

        const from = mark.getBoundingClientRect();
        const to = card.getBoundingClientRect();
        const startX = from.right - workspaceRect.left + 6;
        const startY = from.top + from.height / 2 - workspaceRect.top;
        const endX = to.left - workspaceRect.left - 8;
        const endY = to.top + to.height / 2 - workspaceRect.top;
        const delta = Math.max(42, (endX - startX) * 0.45);
        const path = `M ${startX} ${startY} C ${startX + delta} ${startY}, ${endX - delta} ${endY}, ${endX} ${endY}`;
        const persona = personaMap.get(comment.persona_id);
        const color = persona
          ? getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id))
          : AGENT_COLORS[0];
        nextPaths.push({ id: comment.id, path, color });
      }
      setConnectorPaths(nextPaths);
    };
    const frame = requestAnimationFrame(recalc);

    const onResize = () => {
      requestAnimationFrame(recalc);
    };
    window.addEventListener('resize', onResize);
    const feed = feedListRef.current;
    const doc = docPanelRef.current;
    feed?.addEventListener('scroll', onResize);
    doc?.addEventListener('scroll', onResize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', onResize);
      feed?.removeEventListener('scroll', onResize);
      doc?.removeEventListener('scroll', onResize);
    };
  }, [anchoredComments, selectedVersion, personaMap, agentThemes]);

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
        <section className="workspace" ref={workspaceRef}>
          <svg className="link-layer" aria-hidden="true">
            {connectorPaths.map((item) => (
              <path
                key={item.id}
                d={item.path}
                stroke={item.color}
                className="link-path"
                strokeWidth={1.8}
                fill="none"
              />
            ))}
          </svg>
          <div className="doc-panel" ref={docPanelRef}>
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
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => handleRunReview(selectedVersion.id)}
                >
                  Run Review
                </button>
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
                      <mark
                        key={idx}
                        ref={(element) => {
                          markRefs.current[segment.comment!.id] = element;
                        }}
                        className="doc-highlight"
                        style={{ backgroundColor: `${color}22`, borderBottomColor: color }}
                      >
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
              <button
                className="ghost-button"
                type="button"
                onClick={() => void loadComments(selectedVersion.id, false, selectedReviewJobId)}
              >
                Refresh
              </button>
            </div>
            <div className="feed-list" ref={feedListRef}>
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
                    ref={(element) => {
                      cardRefs.current[comment.id] = element;
                    }}
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
        <div className="library-overlay">
          <div className="library-shell">
            <div className="library-header">
              <div>
                <div className="library-title">Review Ledger</div>
                <div className="library-sub">
                  Saved reviews stay with each version. Run a new review only when you ask.
                </div>
              </div>
              <div className="library-actions">
                <div className="library-filters">
                  <button
                    className={`filter-chip ${libraryFilter === 'all' ? 'active' : ''}`}
                    type="button"
                    onClick={() => setLibraryFilter('all')}
                  >
                    All
                  </button>
                  <button
                    className={`filter-chip ${libraryFilter === 'needs' ? 'active' : ''}`}
                    type="button"
                    onClick={() => setLibraryFilter('needs')}
                  >
                    Needs Review
                  </button>
                  <button
                    className={`filter-chip ${libraryFilter === 'reviewed' ? 'active' : ''}`}
                    type="button"
                    onClick={() => setLibraryFilter('reviewed')}
                  >
                    Reviewed
                  </button>
                </div>
                <input
                  className="library-search"
                  placeholder="Search documents"
                  value={librarySearch}
                  onChange={(event) => setLibrarySearch(event.target.value)}
                />
              </div>
            </div>

            <div className="library-grid">
              {filteredLibraryWithSearch.length === 0 && (
                <div className="subtle">No documents yet.</div>
              )}
              {filteredLibraryWithSearch.map((entry) => {
                const statusLabel = entry.needs_review ? 'Needs Review' : 'Reviewed';
                const versionLabel = entry.latest_version_label ?? 'No versions yet';
                const lastEdited = entry.latest_version_created_at
                  ? new Date(entry.latest_version_created_at).toLocaleString()
                  : '—';
                const lastReviewed = entry.latest_review_completed_at
                  ? new Date(entry.latest_review_completed_at).toLocaleString()
                  : '—';
                return (
                  <div key={entry.id} className={`library-card ${entry.needs_review ? 'needs' : 'ready'}`}>
                    <div className="review-ribbon" />
                    <div className="library-card-body">
                      <div className="library-card-title">{entry.title}</div>
                      <div className="library-card-meta">
                        <span className="meta-pill">{versionLabel}</span>
                        <span className={`status-pill ${entry.needs_review ? 'warn' : 'ok'}`}>
                          {statusLabel}
                        </span>
                      </div>
                      <div className="library-timeline">
                        <div>
                          <div className="timeline-label">Last edit</div>
                          <div className="timeline-value">{lastEdited}</div>
                        </div>
                        <div>
                          <div className="timeline-label">Last review</div>
                          <div className="timeline-value">{lastReviewed}</div>
                        </div>
                      </div>
                      <div className="library-card-actions">
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={() => {
                            setSelectedDocumentId(entry.id);
                            void loadVersions(entry.id);
                            setShowLibrary(false);
                          }}
                        >
                          Open
                        </button>
                        <button
                          className="primary-button"
                          type="button"
                          disabled={!entry.latest_version_id}
                          onClick={() => {
                            if (!entry.latest_version_id) return;
                            setSelectedDocumentId(entry.id);
                            setShowLibrary(false);
                            void loadVersions(entry.id).then(() =>
                              handleRunReview(entry.latest_version_id as number)
                            );
                          }}
                        >
                          Run Review
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
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
