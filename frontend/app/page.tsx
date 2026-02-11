'use client';

import {
  default as React,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent
} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import JSZip from 'jszip';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
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
  SystemConfigRead,
  SystemStatus
} from '../src/lib/types';

const POLL_INTERVAL_MS = 1200;
const AGENT_COLORS = ['#1d8a7a', '#2d6eea', '#b7482f', '#7a4bd3', '#c57a1b', '#0f6e88'];

type DocSegment = { text: string; comment?: CommentRead };
type ConnectorPath = { id: number; path: string; color: string };

function MermaidDiagram({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const chartIdRef = useRef(`mermaid-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const run = async () => {
      const target = containerRef.current;
      if (!target) return;
      try {
        const mod = await import('mermaid');
        const mermaid = mod.default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'neutral',
          suppressErrorRendering: true
        });
        const result = await mermaid.render(chartIdRef.current, chart);
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = result.svg;
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Mermaid rendering failed');
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <div className="mermaid-fallback">
        Mermaid render error: {error}
        <pre>{chart}</pre>
      </div>
    );
  }

  return <div className="mermaid-diagram" ref={containerRef} />;
}

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
  const [systemConfig, setSystemConfig] = useState<SystemConfigRead | null>(null);

  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [selectedReviewJobId, setSelectedReviewJobId] = useState<number | null>(null);
  const [docMode, setDocMode] = useState<'view' | 'source'>('view');
  const [focusedCommentId, setFocusedCommentId] = useState<number | null>(null);
  const [hoveredCommentId, setHoveredCommentId] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [enabledPersonas, setEnabledPersonas] = useState<Set<number>>(new Set());
  const [recentCommentIds, setRecentCommentIds] = useState<Set<number>>(new Set());
  const [agentThemes, setAgentThemes] = useState<Record<string, AgentTheme>>({});
  const [libraryFilter, setLibraryFilter] = useState<
    'all' | 'needs' | 'reviewed' | 'archived'
  >('all');
  const [librarySearch, setLibrarySearch] = useState('');
  const [selectedLibraryIds, setSelectedLibraryIds] = useState<Set<number>>(new Set());
  const [isLibraryHovering, setIsLibraryHovering] = useState(false);
  const [bulkProgress, setBulkProgress] = useState<{
    label: string;
    done: number;
    total: number;
  } | null>(null);
  const [isReviewStarting, setIsReviewStarting] = useState(false);
  const [connectorPaths, setConnectorPaths] = useState<ConnectorPath[]>([]);
  const [highlightTick, setHighlightTick] = useState(0);
  const lastPollRef = useRef<number>(Date.now());
  const workspaceRef = useRef<HTMLElement | null>(null);
  const docPanelRef = useRef<HTMLDivElement | null>(null);
  const docBodyRef = useRef<HTMLElement | null>(null);
  const feedListRef = useRef<HTMLDivElement | null>(null);
  const markRefs = useRef<Record<number, HTMLElement | null>>({});
  const cardRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const hoveredCommentIdRef = useRef<number | null>(null);
  const handledRouteIntentRef = useRef<string | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const normalizedPath = (pathname || '/').toLowerCase();
  const showLibrary = normalizedPath === '/library';
  const showAgents = normalizedPath === '/agents';
  const showHistory = normalizedPath === '/history';
  const showSettings = normalizedPath === '/system';

  const selectedDocument = useMemo(() => {
    const fromLibrary = libraryEntries.find((doc) => doc.id === selectedDocumentId);
    if (fromLibrary) return fromLibrary;
    return documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  }, [documents, libraryEntries, selectedDocumentId]);

  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) ?? null,
    [versions, selectedVersionId]
  );
  const selectedReviewJob = useMemo(
    () => reviewJobs.find((job) => job.id === selectedReviewJobId) ?? null,
    [reviewJobs, selectedReviewJobId]
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
    if (!selectedVersionId) return;
    const interval = setInterval(() => {
      void loadReviewJobsSnapshot(selectedVersionId);
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [selectedVersionId, selectedReviewJobId]);

  useEffect(() => {
    if (!focusedCommentId) return;
    const card = cardRefs.current[focusedCommentId];
    const mark = markRefs.current[focusedCommentId];
    card?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    mark?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
  }, [focusedCommentId]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!focusedCommentId) return;
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const inComment = target.closest('.comment-card');
      const inHighlight = target.closest('.doc-highlight');
      if (!inComment && !inHighlight) {
        setFocusedCommentId(null);
      }
    };
    window.addEventListener('pointerdown', onPointerDown);
    return () => {
      window.removeEventListener('pointerdown', onPointerDown);
    };
  }, [focusedCommentId]);

  useEffect(() => {
    const interval = setInterval(() => {
      void loadSystemStatus();
    }, 8000);
    void loadSystemStatus();
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (showSettings) {
      void loadSystemConfig();
    }
  }, [showSettings]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    if (showLibrary) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = previous || '';
    }
    return () => {
      document.body.style.overflow = previous || '';
    };
  }, [showLibrary]);

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

  async function loadSystemConfig() {
    try {
      const cfg = await apiFetch<SystemConfigRead>('/settings');
      setSystemConfig(cfg);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function loadVersions(documentId: number): Promise<DocumentVersionRead[]> {
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
      return data;
    } catch (error) {
      setErrorMessage(normalizeError(error));
      return [];
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
      const latestCompleted = [...jobs]
        .reverse()
        .find((job) => job.status === 'completed' && Boolean(job.completed_at));
      const preferred = latestCompleted ?? (jobs.length > 0 ? jobs[jobs.length - 1] : null);
      setSelectedReviewJobId(preferred?.id ?? null);
      if (preferred) {
        const data = await loadComments(versionId, false, preferred.id);
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

  async function loadReviewJobsSnapshot(versionId: number) {
    try {
      const jobs = await apiFetch<ReviewJobRead[]>(`/review-jobs?document_version_id=${versionId}`);
      setReviewJobs(jobs);
      if (jobs.length === 0) {
        setSelectedReviewJobId(null);
        return;
      }
      const selectedExists =
        selectedReviewJobId !== null && jobs.some((job) => job.id === selectedReviewJobId);
      if (!selectedExists) {
        const latest = jobs[jobs.length - 1];
        setSelectedReviewJobId(latest?.id ?? null);
      }
      const running = jobs.some((job) => job.status === 'queued' || job.status === 'running');
      if (!running) {
        setIsReviewStarting(false);
      }
    } catch {
      // Snapshot polling should not surface transient errors in the primary UI flow.
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

  async function handleRunReview(versionId: number, options?: { requireConfirm?: boolean }) {
    if (options?.requireConfirm ?? true) {
      const proceed = window.confirm(
        'Start a new review run? Existing comments are preserved; this adds a new run.'
      );
      if (!proceed) return;
    }
    setErrorMessage(null);
    setIsReviewStarting(true);
    try {
      const job = await apiFetch<ReviewJobRead>('/review-jobs', {
        method: 'POST',
        body: JSON.stringify({ document_version_id: versionId, trigger: 'manual' })
      });
      setReviewJobs((prev) => [...prev.filter((item) => item.id !== job.id), job]);
      setSelectedReviewJobId(job.id);
      setStatusMessage('Review started. Comments will arrive shortly.');
      await loadComments(versionId, false, job.id);
      await loadReviewJobsSnapshot(versionId);
      void refreshAll();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setIsReviewStarting(false);
    }
  }

  async function handleSetArchived(documentId: number, archived: boolean) {
    setErrorMessage(null);
    try {
      await apiFetch<DocumentRead>(`/documents/${documentId}/archive`, {
        method: 'POST',
        body: JSON.stringify({ archived })
      });
      if (archived && selectedDocumentId === documentId) {
        setSelectedDocumentId(null);
        setSelectedVersionId(null);
        setSelectedReviewJobId(null);
        setVersions([]);
        setComments([]);
      }
      setStatusMessage(archived ? 'Document archived.' : 'Document restored.');
      await refreshAll();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleDeleteDocument(documentId: number, title: string) {
    const confirmed = window.confirm(`Delete "${title}" permanently?`);
    if (!confirmed) return;
    setErrorMessage(null);
    try {
      await apiFetch<null>(`/documents/${documentId}`, {
        method: 'DELETE'
      });
      if (selectedDocumentId === documentId) {
        setSelectedDocumentId(null);
        setSelectedVersionId(null);
        setSelectedReviewJobId(null);
        setVersions([]);
        setComments([]);
      }
      setStatusMessage('Document deleted.');
      await refreshAll();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleBulkArchive(archived: boolean) {
    const ids = Array.from(selectedLibraryIds);
    if (ids.length === 0) return;
    setErrorMessage(null);
    try {
      setBulkProgress({ label: archived ? 'Archiving' : 'Restoring', done: 0, total: ids.length });
      for (let idx = 0; idx < ids.length; idx += 1) {
        const id = ids[idx];
        await apiFetch<DocumentRead>(`/documents/${id}/archive`, {
          method: 'POST',
          body: JSON.stringify({ archived })
        });
        setBulkProgress({
          label: archived ? 'Archiving' : 'Restoring',
          done: idx + 1,
          total: ids.length
        });
      }
      setSelectedLibraryIds(new Set());
      setStatusMessage(archived ? 'Selected documents archived.' : 'Selected documents restored.');
      await refreshAll();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setBulkProgress(null);
    }
  }

  async function handleBulkDelete() {
    const ids = Array.from(selectedLibraryIds);
    if (ids.length === 0) return;
    const confirmed = window.confirm(`Delete ${ids.length} selected documents permanently?`);
    if (!confirmed) return;
    setErrorMessage(null);
    try {
      setBulkProgress({ label: 'Deleting', done: 0, total: ids.length });
      for (let idx = 0; idx < ids.length; idx += 1) {
        const id = ids[idx];
        await apiFetch<null>(`/documents/${id}`, {
          method: 'DELETE'
        });
        setBulkProgress({ label: 'Deleting', done: idx + 1, total: ids.length });
      }
      if (selectedDocumentId && ids.includes(selectedDocumentId)) {
        setSelectedDocumentId(null);
        setSelectedVersionId(null);
        setSelectedReviewJobId(null);
        setVersions([]);
        setComments([]);
      }
      setSelectedLibraryIds(new Set());
      setStatusMessage('Selected documents deleted.');
      await refreshAll();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setBulkProgress(null);
    }
  }

  async function handleBulkRerun() {
    const targets = filteredLibraryWithSearch.filter(
      (entry) => selectedLibraryIds.has(entry.id) && Boolean(entry.latest_version_id)
    );
    if (targets.length === 0) return;
    const confirmed = window.confirm(`Queue re-review for ${targets.length} selected document(s)?`);
    if (!confirmed) return;
    setErrorMessage(null);
    try {
      setBulkProgress({ label: 'Queueing re-review', done: 0, total: targets.length });
      for (let idx = 0; idx < targets.length; idx += 1) {
        const entry = targets[idx];
        await apiFetch<ReviewJobRead>('/review-jobs', {
          method: 'POST',
          body: JSON.stringify({
            document_version_id: entry.latest_version_id as number,
            trigger: 'manual'
          })
        });
        setBulkProgress({ label: 'Queueing re-review', done: idx + 1, total: targets.length });
      }
      setSelectedLibraryIds(new Set());
      setStatusMessage(`Queued re-review for ${targets.length} document(s).`);
      await refreshAll();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setBulkProgress(null);
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

  async function handleOpenDocument(documentId: number, options?: { navigateHome?: boolean }) {
    setErrorMessage(null);
    setSelectedDocumentId(documentId);
    await loadVersions(documentId);
    if (options?.navigateHome ?? false) {
      router.push(`/?doc=${documentId}`);
    }
    setStatusMessage('Loaded saved review for selected document.');
  }

  function handleTenantSave() {
    setTenantId(tenantId || DEFAULT_TENANT);
    setApiBase(apiBase || 'http://localhost:8006/api');
    setStatusMessage('Connection settings saved.');
    void refreshAll();
  }

  async function handleSystemConfigSave() {
    if (!systemConfig) return;
    try {
      const payload = {
        llm_provider: systemConfig.llm_provider,
        openai_model: systemConfig.openai_model,
        openai_max_tokens: systemConfig.openai_max_tokens,
        openai_temperature: systemConfig.openai_temperature,
        openai_timeout_seconds: systemConfig.openai_timeout_seconds,
        bedrock_model_id: systemConfig.bedrock_model_id,
        bedrock_region: systemConfig.bedrock_region,
        review_inline: systemConfig.review_inline
      };
      const next = await apiFetch<SystemConfigRead>('/settings', {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      setSystemConfig(next);
      setStatusMessage('Backend review settings saved.');
      void loadSystemStatus();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleSaveSecret(
    field:
      | 'openai_api_key'
      | 'bedrock_aws_access_key_id'
      | 'bedrock_aws_secret_access_key'
      | 'bedrock_aws_session_token',
    value: string
  ) {
    if (!systemConfig) return;
    try {
      const payload = {
        llm_provider: systemConfig.llm_provider,
        openai_model: systemConfig.openai_model,
        openai_max_tokens: systemConfig.openai_max_tokens,
        openai_temperature: systemConfig.openai_temperature,
        openai_timeout_seconds: systemConfig.openai_timeout_seconds,
        bedrock_model_id: systemConfig.bedrock_model_id,
        bedrock_region: systemConfig.bedrock_region,
        review_inline: systemConfig.review_inline,
        [field]: value
      };
      const next = await apiFetch<SystemConfigRead>('/settings', {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      setSystemConfig(next);
      setStatusMessage('Secret updated.');
      void loadSystemStatus();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
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
    if (libraryFilter === 'archived') {
      return libraryEntries.filter((entry) => entry.is_archived);
    }
    const active = libraryEntries.filter((entry) => !entry.is_archived);
    if (libraryFilter === 'all') return active;
    if (libraryFilter === 'needs') {
      return active.filter((entry) => entry.needs_review);
    }
    return active.filter((entry) => !entry.needs_review);
  }, [libraryEntries, libraryFilter]);

  const filteredLibraryWithSearch = useMemo(() => {
    if (!librarySearch.trim()) return filteredLibrary;
    const query = librarySearch.trim().toLowerCase();
    return filteredLibrary.filter((entry) => entry.title.toLowerCase().includes(query));
  }, [filteredLibrary, librarySearch]);

  const activeCommentId = focusedCommentId ?? hoveredCommentId;

  useEffect(() => {
    hoveredCommentIdRef.current = hoveredCommentId;
  }, [hoveredCommentId]);

  useEffect(() => {
    const root = docBodyRef.current;
    if (!root) return;

    const clearViewHighlights = () => {
      const existing = root.querySelectorAll('span[data-odr-view-highlight="1"]');
      existing.forEach((node) => {
        const parent = node.parentNode;
        if (!parent) return;
        while (node.firstChild) {
          parent.insertBefore(node.firstChild, node);
        }
        parent.removeChild(node);
        parent.normalize();
      });
      for (const comment of anchoredComments) {
        markRefs.current[comment.id] = null;
      }
    };

    clearViewHighlights();
    if (docMode !== 'view' || anchoredComments.length === 0) {
      setHighlightTick((prev) => prev + 1);
      return;
    }

    const frame = requestAnimationFrame(() => {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let full = '';
      let current = walker.nextNode();
      while (current) {
        const textNode = current as Text;
        const parent = textNode.parentElement;
        const skip = Boolean(parent?.closest('code, pre, svg'));
        const text = textNode.textContent ?? '';
        if (!skip && text.trim().length > 0) {
          full += text;
        } else {
          full += text;
        }
        current = walker.nextNode();
      }

      const fullLower = full.toLowerCase();
      const matches: Array<{ comment: CommentRead; start: number; end: number; color: string }> = [];
      let searchFrom = 0;
      for (const comment of anchoredComments) {
        const excerptCandidate =
          comment.excerpt?.trim() ||
          selectedVersion?.content.slice(comment.start_offset, comment.end_offset).trim() ||
          '';
        if (!excerptCandidate) continue;
        const excerptLower = excerptCandidate.toLowerCase();
        if (!excerptLower) continue;

        let idx = fullLower.indexOf(excerptLower, searchFrom);
        if (idx < 0) {
          idx = fullLower.indexOf(excerptLower);
        }
        if (idx < 0) continue;

        const end = idx + excerptLower.length;
        const persona = personaMap.get(comment.persona_id);
        const color = persona
          ? getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id))
          : AGENT_COLORS[0];
        matches.push({ comment, start: idx, end, color });
        searchFrom = end;
      }

      const locateBoundary = (targetIndex: number) => {
        const nodeWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        let seen = 0;
        let node = nodeWalker.nextNode();
        while (node) {
          const textNode = node as Text;
          const parent = textNode.parentElement;
          const skip = Boolean(parent?.closest('code, pre, svg'));
          const text = textNode.textContent ?? '';
          const length = text.length;
          if (!skip && length > 0) {
            const nextSeen = seen + length;
            if (targetIndex >= seen && targetIndex <= nextSeen) {
              return { node: textNode, offset: Math.max(0, targetIndex - seen) };
            }
            seen = nextSeen;
          } else {
            seen += length;
          }
          node = nodeWalker.nextNode();
        }
        return null;
      };

      for (let idx = matches.length - 1; idx >= 0; idx -= 1) {
        const match = matches[idx];
        const startBoundary = locateBoundary(match.start);
        const endBoundary = locateBoundary(match.end);
        if (!startBoundary || !endBoundary) {
          markRefs.current[match.comment.id] = null;
          continue;
        }

        const range = document.createRange();
        range.setStart(startBoundary.node, startBoundary.offset);
        range.setEnd(endBoundary.node, endBoundary.offset);

        const span = document.createElement('span');
        span.dataset.odrViewHighlight = '1';
        span.className = `doc-highlight view-highlight ${
          activeCommentId === match.comment.id ? 'selected' : ''
        }`;
        span.style.backgroundColor = `${match.color}22`;
        span.style.borderBottomColor = match.color;
        span.addEventListener('click', () => focusComment(match.comment.id));
        span.addEventListener('mouseenter', () => setHoveredCommentId(match.comment.id));
        span.addEventListener('mouseleave', () => setHoveredCommentId(null));

        try {
          const fragment = range.extractContents();
          span.appendChild(fragment);
          range.insertNode(span);
          markRefs.current[match.comment.id] = span;
        } catch {
          markRefs.current[match.comment.id] = null;
        }
      }
      setHighlightTick((prev) => prev + 1);
    });

    return () => {
      cancelAnimationFrame(frame);
      clearViewHighlights();
    };
  }, [
    docMode,
    anchoredComments,
    selectedVersion,
    personaMap,
    agentThemes,
    activeCommentId
  ]);

  const allFilteredSelected = useMemo(() => {
    if (filteredLibraryWithSearch.length === 0) return false;
    return filteredLibraryWithSearch.every((entry) => selectedLibraryIds.has(entry.id));
  }, [filteredLibraryWithSearch, selectedLibraryIds]);

  const showSelectionControls = isLibraryHovering || selectedLibraryIds.size > 0;
  const hoverCenterIndex = useMemo(
    () => visibleComments.findIndex((comment) => comment.id === hoveredCommentId),
    [visibleComments, hoveredCommentId]
  );
  const focusCenterIndex = useMemo(
    () => visibleComments.findIndex((comment) => comment.id === focusedCommentId),
    [visibleComments, focusedCommentId]
  );
  const dockCenterIndex = focusedCommentId ? focusCenterIndex : hoverCenterIndex;

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
  }, [anchoredComments, selectedVersion, personaMap, agentThemes, docMode, activeCommentId, highlightTick]);

  function updateAgentTheme(id: number, color: string, label?: string) {
    setAgentThemes((prev) => {
      const next = { ...prev, [String(id)]: { color, label } };
      saveAgentThemes(next);
      return next;
    });
  }

  function focusComment(commentId: number) {
    setFocusedCommentId((prev) => (prev === commentId ? null : commentId));
    setDocMode('source');
  }

  function handleFeedPointerMove(event: ReactMouseEvent<HTMLDivElement>) {
    if (focusedCommentId) return;
    const target = event.target as HTMLElement | null;
    const card = target?.closest<HTMLElement>('.comment-card[data-comment-id]');
    if (!card) {
      if (hoveredCommentIdRef.current !== null) {
        setHoveredCommentId(null);
      }
      return;
    }
    const rawId = card.dataset.commentId;
    if (!rawId) return;
    const nextId = Number(rawId);
    if (!Number.isFinite(nextId)) return;
    if (hoveredCommentIdRef.current !== nextId) {
      setHoveredCommentId(nextId);
    }
  }

  useEffect(() => {
    if (normalizedPath !== '/') return;
    const docRaw = searchParams.get('doc');
    if (!docRaw) return;
    const docId = Number(docRaw);
    if (!Number.isFinite(docId) || docId <= 0) return;
    const runRequested = searchParams.get('run') === '1';
    const intentKey = `${docId}:${runRequested ? 'run' : 'open'}`;
    if (handledRouteIntentRef.current === intentKey) return;
    handledRouteIntentRef.current = intentKey;

    void (async () => {
      const versionsForDoc = await loadVersions(docId);
      setSelectedDocumentId(docId);
      if (runRequested && versionsForDoc.length > 0) {
        const latest = versionsForDoc[versionsForDoc.length - 1];
        await handleRunReview(latest.id, { requireConfirm: false });
        router.replace(`/?doc=${docId}`);
      }
    })();
  }, [normalizedPath, searchParams]);

  function navigatePanel(path: '/library' | '/agents' | '/history' | '/system') {
    if (normalizedPath === path) {
      router.push('/');
      return;
    }
    router.push(path);
  }

  function downloadFile(filename: string, content: string, mime = 'text/plain;charset=utf-8') {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function handleDownloadReviewedMarkdown() {
    if (!selectedVersion) return;
    const context = buildCommentExportContext();
    if (!context) return;
    const header = [
      `# ${context.title}`,
      '',
      `Version: ${selectedVersion.version_label}`,
      `Review job: ${selectedReviewJob?.id ?? 'n/a'}`,
      `Provider/model: ${selectedReviewJob ? `${selectedReviewJob.provider}/${selectedReviewJob.model}` : 'n/a'}`,
      ''
    ].join('\n');
    downloadFile(`${context.safeTitle}_reviewed.md`, `${header}${selectedVersion.content}`);
  }

  function buildCommentExportContext() {
    if (!selectedVersion) return null;
    const title = selectedDocument?.title ?? `document-${selectedVersion.document_id}`;
    const safeTitle = title.replace(/[^a-zA-Z0-9-_]+/g, '_');
    const sorted = [...visibleComments].sort((a, b) => a.start_offset - b.start_offset);
    const reviewMeta = {
      review_job_id: selectedReviewJob?.id ?? null,
      provider: selectedReviewJob?.provider ?? null,
      model: selectedReviewJob?.model ?? null
    };
    return { title, safeTitle, sorted, reviewMeta };
  }

  function buildCommentsJson() {
    if (!selectedVersion) return null;
    const context = buildCommentExportContext();
    if (!context) return null;
    return {
      document_id: selectedVersion.document_id,
      document_title: context.title,
      version_id: selectedVersion.id,
      version_label: selectedVersion.version_label,
      review_job_id: context.reviewMeta.review_job_id,
      provider: context.reviewMeta.provider,
      model: context.reviewMeta.model,
      comments: context.sorted
    };
  }

  function buildCommentsMarkdown() {
    if (!selectedVersion) return null;
    const context = buildCommentExportContext();
    if (!context) return null;
    const lines = [
      `# Comments for ${context.title}`,
      '',
      `Version: ${selectedVersion.version_label}`,
      `Review job: ${context.reviewMeta.review_job_id ?? 'n/a'}`,
      `Provider/model: ${
        context.reviewMeta.provider && context.reviewMeta.model
          ? `${context.reviewMeta.provider}/${context.reviewMeta.model}`
          : 'n/a'
      }`,
      ''
    ];
    for (const comment of context.sorted) {
      const persona = personaMap.get(comment.persona_id);
      lines.push(`- [${persona?.name ?? `Agent ${comment.persona_id}`}] ${comment.text}`);
      if (comment.excerpt) {
        lines.push(`  - Excerpt: "${comment.excerpt}"`);
      }
    }
    return { safeTitle: context.safeTitle, markdown: lines.join('\n') };
  }

  async function handleDownloadBundleZip() {
    if (!selectedVersion) return;
    const context = buildCommentExportContext();
    const commentsJson = buildCommentsJson();
    const commentsMd = buildCommentsMarkdown();
    if (!context || !commentsJson || !commentsMd) return;

    const zip = new JSZip();
    const docHeader = [
      `# ${context.title}`,
      '',
      `Version: ${selectedVersion.version_label}`,
      `Review job: ${context.reviewMeta.review_job_id ?? 'n/a'}`,
      `Provider/model: ${
        context.reviewMeta.provider && context.reviewMeta.model
          ? `${context.reviewMeta.provider}/${context.reviewMeta.model}`
          : 'n/a'
      }`,
      ''
    ].join('\n');
    zip.file(`${context.safeTitle}_reviewed.md`, `${docHeader}${selectedVersion.content}`);
    zip.file(`${context.safeTitle}_comments.md`, commentsMd.markdown);
    zip.file(`${context.safeTitle}_comments.json`, JSON.stringify(commentsJson, null, 2));
    zip.file(
      'manifest.json',
      JSON.stringify(
        {
          exported_at: new Date().toISOString(),
          document_title: context.title,
          version_id: selectedVersion.id,
          version_label: selectedVersion.version_label,
          review: context.reviewMeta,
          files: [
            `${context.safeTitle}_reviewed.md`,
            `${context.safeTitle}_comments.md`,
            `${context.safeTitle}_comments.json`
          ]
        },
        null,
        2
      )
    );

    const blob = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${context.safeTitle}_review_bundle.zip`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function handleDownloadComments(format: 'json' | 'md') {
    if (!selectedVersion) return;
    const context = buildCommentExportContext();
    if (!context) return;
    if (format === 'json') {
      const payload = buildCommentsJson();
      if (!payload) return;
      downloadFile(
        `${context.safeTitle}_comments.json`,
        JSON.stringify(payload, null, 2),
        'application/json;charset=utf-8'
      );
      return;
    }
    const commentsMd = buildCommentsMarkdown();
    if (!commentsMd) return;
    downloadFile(`${context.safeTitle}_comments.md`, commentsMd.markdown);
  }

  return (
    <main>
      <div className="topbar">
        <Link className="brand brand-link" href="/">
          <div className="logo">ODR</div>
          <div>
            <div className="brand-title">Opinionated Doc Reviewer</div>
            <div className="brand-sub">Live multi‑persona review console</div>
          </div>
        </Link>
        <div className="top-actions">
          <button className="ghost-button" type="button" onClick={() => navigatePanel('/library')}>
            Library
          </button>
          <button className="ghost-button" type="button" onClick={() => navigatePanel('/agents')}>
            Agents
          </button>
          <button className="ghost-button" type="button" onClick={() => navigatePanel('/history')}>
            History
          </button>
          <button className="ghost-button" type="button" onClick={() => navigatePanel('/system')}>
            System
          </button>
        </div>
      </div>

      {(statusMessage || errorMessage) && (
        <div className={`status ${errorMessage ? 'warn' : ''}`}>
          {errorMessage ?? statusMessage}
        </div>
      )}

      {systemStatus &&
        (!systemStatus.redis.ok || !(systemStatus.llm?.ok ?? systemStatus.openai.ok)) && (
        <div className="status warn">
          {!systemStatus.redis.ok && (
            <div>Redis is offline. Start Redis to enable reviews.</div>
          )}
          {!(systemStatus.llm?.ok ?? systemStatus.openai.ok) && (
            <div>
              LLM provider issue ({systemStatus.llm?.provider ?? 'openai'}):{' '}
              {systemStatus.llm?.error ?? 'Check provider credentials/configuration.'}
            </div>
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
                className={`link-path ${activeCommentId === item.id ? 'selected' : ''}`}
                strokeWidth={2.4}
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
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
                  {selectedReviewJob
                    ? ` · run #${selectedReviewJob.id} ${selectedReviewJob.status} (${selectedReviewJob.provider}/${selectedReviewJob.model})`
                    : ''}
                </div>
              </div>
              <div className="doc-badges">
                <div className="mode-toggle">
                  <button
                    className={`mode-button ${docMode === 'view' ? 'active' : ''}`}
                    type="button"
                    onClick={() => setDocMode('view')}
                  >
                    View
                  </button>
                  <button
                    className={`mode-button ${docMode === 'source' ? 'active' : ''}`}
                    type="button"
                    onClick={() => setDocMode('source')}
                  >
                    Source
                  </button>
                </div>
                <span className="pill">{systemStatus?.redis.ok ? 'Live' : 'Paused'}</span>
                <span className="pill">{selectedVersion.version_label}</span>
                {selectedReviewJob && (
                  <span className="pill">
                    {selectedReviewJob.status === 'running' || selectedReviewJob.status === 'queued'
                      ? 'Reviewing...'
                      : selectedReviewJob.status}
                  </span>
                )}
                <button className="ghost-button" type="button" onClick={handleDownloadReviewedMarkdown}>
                  Download Doc
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => handleDownloadComments('md')}
                >
                  Download Comments
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => handleDownloadComments('json')}
                >
                  Comments JSON
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => void handleDownloadBundleZip()}
                >
                  Download Bundle
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  disabled={isReviewStarting}
                  onClick={() => handleRunReview(selectedVersion.id, { requireConfirm: true })}
                >
                  {isReviewStarting ? 'Starting...' : 'Re-run Review'}
                </button>
              </div>
            </div>
            <article className="doc-body" ref={docBodyRef}>
              {docMode === 'view' && (
                <div className="markdown-view">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code(props) {
                        const { className, children } = props;
                        const text = String(children ?? '').replace(/\n$/, '');
                        const language =
                          className?.startsWith('language-') === true
                            ? className.slice('language-'.length)
                            : '';
                        if (language === 'mermaid') {
                          return <MermaidDiagram chart={text} />;
                        }
                        return <code className={className}>{children}</code>;
                      }
                    }}
                  >
                    {selectedVersion.content}
                  </ReactMarkdown>
                </div>
              )}
              {docMode === 'source' && docSegments.length === 0 && <pre>{selectedVersion.content}</pre>}
              {docMode === 'source' && docSegments.length > 0 && (
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
                        className={`doc-highlight ${
                          activeCommentId === segment.comment.id ? 'selected' : ''
                        }`}
                        onClick={() => focusComment(segment.comment!.id)}
                        onMouseEnter={() => setHoveredCommentId(segment.comment!.id)}
                        onMouseLeave={() => setHoveredCommentId(null)}
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
                <div className="feed-title">Comments</div>
                <div className="feed-sub">Anchored reviewer comments for this document version.</div>
              </div>
              <button
                className="ghost-button"
                type="button"
                onClick={() => void loadComments(selectedVersion.id, false, selectedReviewJobId)}
              >
                Refresh
              </button>
            </div>
            <div
              className="feed-list"
              ref={feedListRef}
              onMouseMove={handleFeedPointerMove}
              onMouseLeave={() => {
                if (!focusedCommentId) setHoveredCommentId(null);
              }}
            >
              {visibleComments.length === 0 && (
                <div className="empty-feed">Waiting for anchored comments…</div>
              )}
              {visibleComments.map((comment, index) => {
                const persona = personaMap.get(comment.persona_id);
                const color = persona
                  ? getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id))
                  : AGENT_COLORS[0];
                const isFailure = comment.text.toLowerCase().startsWith('review failed:');
                const distance =
                  dockCenterIndex >= 0 ? Math.abs(index - dockCenterIndex) : Number.POSITIVE_INFINITY;
                let scale = 1;
                if (distance === 0) scale = 2;
                else if (distance === 1) scale = 1.26;
                else if (distance === 2) scale = 1.08;
                const shift = scale > 1 ? -Math.round((scale - 1) * 62) : 0;
                const zIndex = distance === 0 ? 140 : distance === 1 ? 80 : distance === 2 ? 48 : 1;
                return (
                  <div
                    key={comment.id}
                    ref={(element) => {
                      cardRefs.current[comment.id] = element;
                    }}
                    data-comment-id={comment.id}
                    className={`comment-card ${recentCommentIds.has(comment.id) ? 'new' : ''} ${
                      activeCommentId === comment.id ? 'selected' : ''
                    } ${activeCommentId && activeCommentId !== comment.id ? 'dimmed' : ''} ${
                      isFailure ? 'error' : ''
                    }`}
                    style={{
                      borderLeftColor: color,
                      ['--dock-scale' as '--dock-scale']: scale,
                      ['--dock-shift' as '--dock-shift']: `${shift}px`,
                      zIndex
                    } as CSSProperties}
                    onClick={() => focusComment(comment.id)}
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
                  {reviewJobs.length === 0 && <div className="subtle">No review runs yet.</div>}
                  {reviewJobs
                    .slice()
                    .reverse()
                    .map((job) => (
                      <div key={job.id} className="history-item">
                        <div>
                          <div className="history-msg">
                            #{job.id} {job.status} via {job.provider}/{job.model}
                          </div>
                          <div className="history-time">
                            {new Date(job.created_at).toLocaleString()}
                            {job.completed_at ? ` - completed ${new Date(job.completed_at).toLocaleString()}` : ''}
                          </div>
                        </div>
                        <span className="pill">{job.trigger}</span>
                      </div>
                    ))}
                </div>
                <div className="drawer-title" style={{ marginTop: 12 }}>
                  Commits
                </div>
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
                  <button
                    className={`filter-chip ${libraryFilter === 'archived' ? 'active' : ''}`}
                    type="button"
                    onClick={() => setLibraryFilter('archived')}
                  >
                    Archived
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

            {(showSelectionControls || bulkProgress) && (
              <div className="bulk-bar">
              <label className="bulk-select-all">
                <input
                  type="checkbox"
                  checked={allFilteredSelected}
                  disabled={bulkProgress !== null || !showSelectionControls}
                  onChange={(event) => {
                    const next = new Set(selectedLibraryIds);
                    if (event.target.checked) {
                      for (const entry of filteredLibraryWithSearch) {
                        next.add(entry.id);
                      }
                    } else {
                      for (const entry of filteredLibraryWithSearch) {
                        next.delete(entry.id);
                      }
                    }
                    setSelectedLibraryIds(next);
                  }}
                />
                Select all ({filteredLibraryWithSearch.length})
              </label>
              {bulkProgress && (
                <div className="bulk-progress">
                  {bulkProgress.label} {bulkProgress.done}/{bulkProgress.total}
                </div>
              )}
              <div className="bulk-actions">
                <button
                  className="ghost-button"
                  type="button"
                  disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                  onClick={() => void handleBulkArchive(true)}
                >
                  Archive Selected
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                  onClick={() => void handleBulkArchive(false)}
                >
                  Restore Selected
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                  onClick={() => void handleBulkRerun()}
                >
                  Re-run Selected
                </button>
                <button
                  className="ghost-button danger-button"
                  type="button"
                  disabled={selectedLibraryIds.size === 0 || bulkProgress !== null}
                  onClick={() => void handleBulkDelete()}
                >
                  Delete Selected
                </button>
              </div>
              </div>
            )}

            <div
              className="library-grid"
              onMouseEnter={() => setIsLibraryHovering(true)}
              onMouseLeave={() => setIsLibraryHovering(false)}
            >
              {filteredLibraryWithSearch.length === 0 && (
                <div className="subtle">No documents yet.</div>
              )}
              {filteredLibraryWithSearch.map((entry) => {
                const statusLabel = entry.is_archived
                  ? 'Archived'
                  : entry.needs_review
                    ? 'Needs Review'
                    : 'Reviewed';
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
                      <button
                        className="library-delete-btn"
                        type="button"
                        disabled={bulkProgress !== null}
                        onClick={() => void handleDeleteDocument(entry.id, entry.title)}
                        aria-label={`Delete ${entry.title}`}
                      >
                        ×
                      </button>
                      <label className={`library-select ${showSelectionControls ? 'visible' : ''}`}>
                        <input
                          type="checkbox"
                          checked={selectedLibraryIds.has(entry.id)}
                          disabled={bulkProgress !== null || !showSelectionControls}
                          onChange={(event) => {
                            const next = new Set(selectedLibraryIds);
                            if (event.target.checked) {
                              next.add(entry.id);
                            } else {
                              next.delete(entry.id);
                            }
                            setSelectedLibraryIds(next);
                          }}
                        />
                      </label>
                      <div className="library-card-summary">
                        <div className="library-card-title">{entry.title}</div>
                        <div className="library-card-meta">
                          <span
                            className={`status-pill ${
                              entry.is_archived ? 'neutral' : entry.needs_review ? 'warn' : 'ok'
                            }`}
                          >
                            {statusLabel}
                          </span>
                        </div>
                      </div>
                      <div className="library-card-detail">
                        <div className="library-card-meta">
                          <span className="meta-pill">{versionLabel}</span>
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
                            router.push(`/?doc=${entry.id}`);
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
                              router.push(`/?doc=${entry.id}&run=1`);
                            }}
                          >
                            Run Review
                          </button>
                          <button
                            className="ghost-button"
                            type="button"
                            disabled={!entry.latest_version_id}
                            onClick={() => {
                              if (!entry.latest_version_id) return;
                              const confirmed = window.confirm(
                                `Start a new review run for "${entry.title}"?`
                              );
                              if (!confirmed) return;
                              router.push(`/?doc=${entry.id}&run=1`);
                            }}
                          >
                            Re-run
                          </button>
                          <button
                            className="ghost-button"
                            type="button"
                            onClick={() => void handleSetArchived(entry.id, !entry.is_archived)}
                          >
                            {entry.is_archived ? 'Restore' : 'Archive'}
                          </button>
                        </div>
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
          <label className="subtle">LLM Provider</label>
          <select
            className="input"
            value={systemConfig?.llm_provider ?? 'openai'}
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
            value={systemConfig?.openai_model ?? ''}
            onChange={(event) =>
              setSystemConfig((prev) =>
                prev ? { ...prev, openai_model: event.target.value } : prev
              )
            }
            placeholder="gpt-4o-mini"
          />
          <div className="spacer" />
          <label className="subtle">OpenAI Max Tokens</label>
          <input
            className="input"
            type="number"
            value={systemConfig?.openai_max_tokens ?? 700}
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
          <div className="spacer" />
          <label className="subtle">Bedrock Model ID</label>
          <input
            className="input"
            value={systemConfig?.bedrock_model_id ?? ''}
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
            value={systemConfig?.bedrock_region ?? ''}
            onChange={(event) =>
              setSystemConfig((prev) =>
                prev ? { ...prev, bedrock_region: event.target.value } : prev
              )
            }
            placeholder="us-east-1"
          />
          <div className="spacer" />
          <label className="subtle">Review Inline (no worker queue)</label>
          <input
            type="checkbox"
            checked={Boolean(systemConfig?.review_inline)}
            onChange={(event) =>
              setSystemConfig((prev) =>
                prev ? { ...prev, review_inline: event.target.checked } : prev
              )
            }
          />
          <div className="spacer" />
          <button className="primary-button" type="button" onClick={() => void handleSystemConfigSave()}>
            Save Backend Settings
          </button>
          <div className="spacer" />
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
            Save Connection
          </button>
          <div className="spacer" />
          <label className="subtle">OpenAI API Key</label>
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              const value = window.prompt(
                `OpenAI API key (${systemConfig?.openai_api_key_set ? 'set' : 'not set'})`,
                ''
              );
              if (value !== null) {
                void handleSaveSecret('openai_api_key', value);
              }
            }}
          >
            {systemConfig?.openai_api_key_set ? 'Update OpenAI Key' : 'Set OpenAI Key'}
          </button>
          <div className="spacer" />
          <label className="subtle">Bedrock Access Key ID</label>
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              const value = window.prompt(
                `Bedrock access key (${systemConfig?.bedrock_access_key_set ? 'set' : 'not set'})`,
                ''
              );
              if (value !== null) {
                void handleSaveSecret('bedrock_aws_access_key_id', value);
              }
            }}
          >
            {systemConfig?.bedrock_access_key_set ? 'Update Access Key' : 'Set Access Key'}
          </button>
          <div className="spacer" />
          <label className="subtle">Bedrock Secret Access Key</label>
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              const value = window.prompt(
                `Bedrock secret key (${systemConfig?.bedrock_secret_key_set ? 'set' : 'not set'})`,
                ''
              );
              if (value !== null) {
                void handleSaveSecret('bedrock_aws_secret_access_key', value);
              }
            }}
          >
            {systemConfig?.bedrock_secret_key_set ? 'Update Secret Key' : 'Set Secret Key'}
          </button>
          <div className="spacer" />
          <label className="subtle">Bedrock Session Token</label>
          <button
            className="ghost-button"
            type="button"
            onClick={() => {
              const value = window.prompt(
                `Bedrock session token (${systemConfig?.bedrock_session_token_set ? 'set' : 'not set'})`,
                ''
              );
              if (value !== null) {
                void handleSaveSecret('bedrock_aws_session_token', value);
              }
            }}
          >
            {systemConfig?.bedrock_session_token_set ? 'Update Session Token' : 'Set Session Token'}
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
