'use client';

import {
  default as React,
  Suspense,
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
import { createPortal } from 'react-dom';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  apiFetch,
  DEFAULT_TENANT,
  getAccessToken,
  getApiBase,
  getTenantId,
  setAccessToken,
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
  AgentListSort,
  createDuplicateAgentName,
  listVisibleAgents
} from '../src/lib/agentList';
import {
  AdminOverview,
  AdminUserRead,
  DocumentPermissionRead,
  CommentRead,
  DocumentCommitRead,
  DocumentLibraryEntry,
  DocumentRead,
  DocumentVersionRead,
  PersonaRead,
  ReviewJobRead,
  MetaCommentSourceRead,
  MetaReviewRunRead,
  WorkerMonitorRead,
  SystemConfigRead,
  SystemStatus
} from '../src/lib/types';
import { useReviewPolling } from '../src/lib/hooks/useReviewPolling';

const POLL_INTERVAL_MS = 1200;
const META_STATUS_POLL_MAX_ATTEMPTS = 8;
const AGENT_COLORS = ['#1d8a7a', '#2d6eea', '#b7482f', '#7a4bd3', '#c57a1b', '#0f6e88'];

type DocSegment = { text: string; comment?: CommentRead };
type ConnectorPath = { id: string; path: string; color: string };
type MetaViewState = 'idle' | 'loading' | 'ready' | 'pending' | 'missing' | 'error';
type AgentDraft = {
  name: string;
  description: string;
  system_prompt: string;
  focus_areas_text: string;
  tone: string;
  reference_notes: string;
  examples_text: string;
  output_format: string;
  max_bullets: number;
  require_quote_excerpt: boolean;
  require_actionable: boolean;
  include_severity: boolean;
  sort_order: number;
  color_theme: string;
  is_active: boolean;
  group_id: number | null;
};
type AgentBundleImport = {
  schema_version: string;
  personas: unknown[];
  file_name: string;
};
type AgentImportResult = {
  created: number;
  updated: number;
  renamed: number;
  skipped: number;
  errors: string[];
};

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

function HomePageContent() {
  const [apiBase, setApiBaseState] = useState('');
  const [tenantId, setTenantIdState] = useState('');
  const [accessToken, setAccessTokenState] = useState('');

  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [libraryEntries, setLibraryEntries] = useState<DocumentLibraryEntry[]>([]);
  const [versions, setVersions] = useState<DocumentVersionRead[]>([]);
  const [comments, setComments] = useState<CommentRead[]>([]);
  const [reviewJobs, setReviewJobs] = useState<ReviewJobRead[]>([]);
  const [personas, setPersonas] = useState<PersonaRead[]>([]);
  const [history, setHistory] = useState<DocumentCommitRead[]>([]);
  const [historyJobs, setHistoryJobs] = useState<ReviewJobRead[]>([]);
  const [historyDocumentId, setHistoryDocumentId] = useState<number | null>(null);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [systemConfig, setSystemConfig] = useState<SystemConfigRead | null>(null);
  const [workerMonitor, setWorkerMonitor] = useState<WorkerMonitorRead | null>(null);
  const [isWorkerMonitorLoading, setIsWorkerMonitorLoading] = useState(false);
  const [adminOverview, setAdminOverview] = useState<AdminOverview | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUserRead[]>([]);
  const [adminPermissions, setAdminPermissions] = useState<DocumentPermissionRead[]>([]);
  const [selectedPermissionDocumentId, setSelectedPermissionDocumentId] = useState<number | null>(null);
  const [newAdminUser, setNewAdminUser] = useState({
    name: '',
    email: '',
    role: 'default' as 'admin' | 'default'
  });
  const [newPermission, setNewPermission] = useState({
    user_id: 0,
    permission_level: 'viewer' as 'owner' | 'editor' | 'viewer'
  });

  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);
  const [selectedReviewJobId, setSelectedReviewJobId] = useState<number | null>(null);
  const [docMode, setDocMode] = useState<'view' | 'source'>('view');
  const [commentViewMode, setCommentViewMode] = useState<'individual' | 'meta'>('meta');
  const [commentModeSelectionSource, setCommentModeSelectionSource] = useState<'auto' | 'manual'>(
    'auto'
  );
  const [focusedCommentId, setFocusedCommentId] = useState<number | null>(null);
  const [hoveredCommentId, setHoveredCommentId] = useState<number | null>(null);
  const [focusedMetaCommentId, setFocusedMetaCommentId] = useState<number | null>(null);
  const [hoveredMetaCommentId, setHoveredMetaCommentId] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [enabledPersonas, setEnabledPersonas] = useState<Set<number>>(new Set());
  const [recentCommentIds, setRecentCommentIds] = useState<Set<number>>(new Set());
  const [agentThemes, setAgentThemes] = useState<Record<string, AgentTheme>>({});
  const [metaReviewRun, setMetaReviewRun] = useState<MetaReviewRunRead | null>(null);
  const [metaViewState, setMetaViewState] = useState<MetaViewState>('idle');
  const [isMetaLoading, setIsMetaLoading] = useState(false);
  const [isPageVisible, setIsPageVisible] = useState(true);
  const [metaCategoryFilter, setMetaCategoryFilter] = useState<
    'all' | 'structure' | 'clarity' | 'technical' | 'security' | 'accessibility' | 'style'
  >('all');
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
  const [isBundleImporting, setIsBundleImporting] = useState(false);
  const [connectorPaths, setConnectorPaths] = useState<ConnectorPath[]>([]);
  const [highlightTick, setHighlightTick] = useState(0);
  const [floatingMetaCardStyle, setFloatingMetaCardStyle] = useState<{
    left: number;
    top: number;
    width: number;
  } | null>(null);
  const [editingPersonaId, setEditingPersonaId] = useState<number | null>(null);
  const [isCreatingAgent, setIsCreatingAgent] = useState(false);
  const [agentDraft, setAgentDraft] = useState<AgentDraft>(() => createEmptyAgentDraft());
  const [isAgentSaving, setIsAgentSaving] = useState(false);
  const [agentBusyId, setAgentBusyId] = useState<number | null>(null);
  const [agentSearch, setAgentSearch] = useState('');
  const [agentSortBy, setAgentSortBy] = useState<AgentListSort>('order');
  const [agentImportConflictPolicy, setAgentImportConflictPolicy] = useState<
    'skip' | 'overwrite' | 'rename'
  >('rename');
  const [pendingAgentImport, setPendingAgentImport] = useState<AgentBundleImport | null>(null);
  const [agentImportPreview, setAgentImportPreview] = useState<AgentImportResult | null>(null);
  const [isAgentImporting, setIsAgentImporting] = useState(false);
  const lastPollRef = useRef<number>(Date.now());
  const commentsRef = useRef<CommentRead[]>([]);
  const commentSignatureRef = useRef('');
  const workspaceRef = useRef<HTMLElement | null>(null);
  const docPanelRef = useRef<HTMLDivElement | null>(null);
  const docBodyRef = useRef<HTMLElement | null>(null);
  const feedListRef = useRef<HTMLDivElement | null>(null);
  const markRefs = useRef<Record<number, HTMLElement | null>>({});
  const cardRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const metaCardRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const hoveredCommentIdRef = useRef<number | null>(null);
  const hoveredMetaCommentIdRef = useRef<number | null>(null);
  const hoverAlignFrameRef = useRef<number | null>(null);
  const handledRouteIntentRef = useRef<string | null>(null);
  // Dedupe key for in-flight meta auto-loads so polling-driven status
  // changes do not fire concurrent duplicate requests.
  const metaLoadInFlightRef = useRef<string | null>(null);
  const isApplyingRouteQueryStateRef = useRef(false);
  const importAgentsInputRef = useRef<HTMLInputElement | null>(null);
  const importReviewBundleInputRef = useRef<HTMLInputElement | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchParamsKey = searchParams.toString();
  const latestSearchParamsKeyRef = useRef(searchParamsKey);
  const normalizedPath = (pathname || '/').toLowerCase();
  const showLibrary = normalizedPath === '/library';
  const showAgents = normalizedPath === '/agents';
  const showHistory = normalizedPath === '/history';
  const showSettings = normalizedPath === '/system';
  const showAdmin = normalizedPath === '/admin';

  useEffect(() => {
    latestSearchParamsKeyRef.current = searchParamsKey;
  }, [searchParamsKey]);

  const selectedDocument = useMemo(() => {
    const fromLibrary = libraryEntries.find((doc) => doc.id === selectedDocumentId);
    if (fromLibrary) return fromLibrary;
    return documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  }, [documents, libraryEntries, selectedDocumentId]);

  const selectedVersion = useMemo(
    () => versions.find((version) => version.id === selectedVersionId) ?? null,
    [versions, selectedVersionId]
  );
  const reviewGenerationOptions = useMemo(() => {
    if (reviewJobs.length === 0) return [];

    const jobsById = [...reviewJobs].sort((a, b) => a.id - b.id);
    const generationByJobId = new Map<number, number>();
    let fallbackGeneration = 0;

    for (const job of jobsById) {
      const generationFromApi = normalizeGenerationIndex(job.generation_index);
      if (generationFromApi !== null) {
        fallbackGeneration = Math.max(fallbackGeneration, generationFromApi);
        generationByJobId.set(job.id, generationFromApi);
      } else {
        fallbackGeneration += 1;
        generationByJobId.set(job.id, fallbackGeneration);
      }
    }

    const latestGeneration = jobsById.reduce((latest, job) => {
      return Math.max(latest, generationByJobId.get(job.id) ?? 0);
    }, 0);

    return reviewJobs
      .map((job) => {
        const generation = generationByJobId.get(job.id) ?? 1;
        const isLatest =
          typeof job.is_latest_for_version === 'boolean'
            ? job.is_latest_for_version
            : generation === latestGeneration;
        const commentCount = Number.isInteger(job.comment_count) ? Number(job.comment_count) : null;
        const commentLabel =
          commentCount === null
            ? ''
            : ` · ${commentCount} comment${commentCount === 1 ? '' : 's'}`;
        return {
          job,
          generation,
          isLatest,
          label: `v${generation}${isLatest ? ' (latest)' : ''} · run #${job.id} · ${job.status}${commentLabel}`
        };
      })
      .sort((a, b) => b.generation - a.generation || b.job.id - a.job.id);
  }, [reviewJobs]);

  const selectedReviewJob = useMemo(
    () => reviewJobs.find((job) => job.id === selectedReviewJobId) ?? null,
    [reviewJobs, selectedReviewJobId]
  );
  const selectedReviewGeneration = useMemo(
    () => reviewGenerationOptions.find((entry) => entry.job.id === selectedReviewJobId) ?? null,
    [reviewGenerationOptions, selectedReviewJobId]
  );
  const editingPersona = useMemo(
    () => personas.find((persona) => persona.id === editingPersonaId) ?? null,
    [personas, editingPersonaId]
  );
  const visibleAgents = useMemo(
    () => listVisibleAgents(personas, agentSearch, agentSortBy),
    [personas, agentSearch, agentSortBy]
  );

  useEffect(() => {
    commentsRef.current = comments;
    commentSignatureRef.current = buildCommentSignature(comments);
  }, [comments]);

  useEffect(() => {
    setApiBaseState(getApiBase());
    setTenantIdState(getTenantId());
    setAccessTokenState(getAccessToken());
    setAgentThemes(loadAgentThemes());
  }, []);

  useEffect(() => {
    void refreshAll();
  }, [tenantId]);

  useEffect(() => {
    if (!showHistory) return;
    if (historyDocumentId === null) {
      const preferredId = selectedDocumentId ?? libraryEntries[0]?.id ?? null;
      setHistoryDocumentId(preferredId);
      void refreshHistoryPanel(preferredId);
      return;
    }
    void refreshHistoryPanel(historyDocumentId);
  }, [showHistory, historyDocumentId, selectedDocumentId, libraryEntries]);

  useEffect(() => {
    if (!showAgents) return;
    if (personas.length === 0) {
      setEditingPersonaId(null);
      setIsCreatingAgent(true);
      setAgentDraft(createEmptyAgentDraft());
      return;
    }
    if (isCreatingAgent) return;
    if (editingPersonaId && personas.some((persona) => persona.id === editingPersonaId)) {
      return;
    }
    const first = personas[0];
    setEditingPersonaId(first.id);
    setAgentDraft(createDraftFromPersona(first));
  }, [showAgents, personas, editingPersonaId, isCreatingAgent]);

  useEffect(() => {
    if (!showAgents || !pendingAgentImport) return;
    void refreshAgentImportPreview(pendingAgentImport);
  }, [agentImportConflictPolicy]);

  const { generationRef: selectionGenerationRef } = useReviewPolling({
    versionId: selectedVersionId,
    reviewJobId: selectedReviewJobId,
    intervalMs: POLL_INTERVAL_MS,
    onPoll: (vid, jid) => {
      void loadComments(vid, true, jid);
      void loadReviewJobsSnapshot(vid);
    },
  });

  useEffect(() => {
    setMetaReviewRun(null);
    setMetaViewState('idle');
    const routeParams = new URLSearchParams(latestSearchParamsKeyRef.current);
    const requestedMode = parseCommentViewModeParam(routeParams.get('mode'));
    if (requestedMode) {
      setCommentModeSelectionSource('manual');
      setCommentViewMode(requestedMode);
    } else {
      setCommentModeSelectionSource('auto');
      setCommentViewMode('meta');
    }
    setMetaCategoryFilter('all');
  }, [selectedVersionId, selectedReviewJobId]);

  useEffect(() => {
    if (commentViewMode !== 'meta') return;
    if (!selectedVersionId) return;
    // Key includes everything that meaningfully changes a meta-load outcome.
    // Polling can rebuild reviewJobs on every tick, but if (version, job,
    // status) is unchanged we must not fire a duplicate request in flight.
    const key = `${selectedVersionId}:${selectedReviewJobId ?? 'none'}:${selectedReviewJob?.status ?? 'na'}:${commentModeSelectionSource}`;
    if (metaLoadInFlightRef.current === key) return;
    metaLoadInFlightRef.current = key;
    void loadOrCreateMetaReview(selectedVersionId, selectedReviewJobId, false, {
      fallbackToIndividualOnMissing: commentModeSelectionSource === 'auto',
      reviewJobStatus: selectedReviewJob?.status ?? null
    }).finally(() => {
      if (metaLoadInFlightRef.current === key) {
        metaLoadInFlightRef.current = null;
      }
    });
  }, [
    commentViewMode,
    selectedVersionId,
    selectedReviewJobId,
    selectedReviewJob?.status,
    commentModeSelectionSource
  ]);

  useEffect(() => {
    if (normalizedPath !== '/') return;
    if (commentViewMode !== 'meta') return;
    if (!selectedVersionId) return;
    if (metaViewState !== 'pending') return;
    if (!isPageVisible) return;

    let cancelled = false;
    let attempts = 0;
    let timeout: number | null = null;

    const clearTimer = () => {
      if (timeout !== null) {
        window.clearTimeout(timeout);
        timeout = null;
      }
    };

    const scheduleNextPoll = () => {
      if (cancelled) return;
      if (attempts >= META_STATUS_POLL_MAX_ATTEMPTS) {
        setStatusMessage(
          'Meta directives are still being synthesized. Auto-refresh paused to avoid noisy polling.'
        );
        return;
      }
      timeout = window.setTimeout(() => {
        void pollMetaStatus();
      }, metaStatusPollDelayForAttempt(attempts + 1));
    };

    const pollMetaStatus = async () => {
      clearTimer();
      if (cancelled) return;
      attempts += 1;
      try {
        const statusOnly = await fetchLatestMetaReviewRun(selectedVersionId, selectedReviewJobId, {
          includeComments: false
        });
        if (cancelled) return;

        setMetaReviewRun((previous) => {
          if (
            statusOnly.comments.length === 0 &&
            previous &&
            previous.id === statusOnly.id &&
            previous.comments.length > 0
          ) {
            return { ...statusOnly, comments: previous.comments };
          }
          return statusOnly;
        });

        if (isMetaSynthesisPendingStatus(statusOnly.status)) {
          scheduleNextPoll();
          return;
        }

        if (isMetaSynthesisFailedStatus(statusOnly.status)) {
          setMetaViewState('error');
          setStatusMessage(
            statusOnly.error_message
              ? `Meta synthesis failed: ${statusOnly.error_message}`
              : 'Meta synthesis failed. Recompute to retry.'
          );
          return;
        }

        const hydrated = await fetchLatestMetaReviewRun(selectedVersionId, selectedReviewJobId, {
          includeComments: true
        });
        if (cancelled) return;

        setMetaReviewRun(hydrated);
        if (isMetaSynthesisPendingStatus(hydrated.status)) {
          setMetaViewState('pending');
          setStatusMessage('Meta directives are still being synthesized.');
          scheduleNextPoll();
          return;
        }

        if (isMetaSynthesisFailedStatus(hydrated.status)) {
          setMetaViewState('error');
          setStatusMessage(
            hydrated.error_message
              ? `Meta synthesis failed: ${hydrated.error_message}`
              : 'Meta synthesis failed. Recompute to retry.'
          );
          return;
        }

        setMetaViewState('ready');
        setStatusMessage(
          hydrated.comments.length > 0
            ? `Meta review loaded (${hydrated.comments.length} directives).`
            : 'Meta review loaded (no directives).'
        );
      } catch {
        if (cancelled) return;
        scheduleNextPoll();
      }
    };

    scheduleNextPoll();
    return () => {
      cancelled = true;
      clearTimer();
    };
  }, [
    normalizedPath,
    commentViewMode,
    selectedVersionId,
    selectedReviewJobId,
    metaViewState,
    isPageVisible
  ]);

  useEffect(() => {
    if (!focusedCommentId) return;
    const card = cardRefs.current[focusedCommentId];
    const mark = markRefs.current[focusedCommentId];
    card?.scrollIntoView?.({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    mark?.scrollIntoView?.({ behavior: 'smooth', block: 'center', inline: 'nearest' });
  }, [focusedCommentId]);

  useEffect(() => {
    if (!hoveredCommentId || focusedCommentId) return;
    if (hoverAlignFrameRef.current !== null) {
      cancelAnimationFrame(hoverAlignFrameRef.current);
    }
    hoverAlignFrameRef.current = requestAnimationFrame(() => {
      const mark = markRefs.current[hoveredCommentId];
      const card = cardRefs.current[hoveredCommentId];
      card?.scrollIntoView?.({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      mark?.scrollIntoView?.({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    });
    return () => {
      if (hoverAlignFrameRef.current !== null) {
        cancelAnimationFrame(hoverAlignFrameRef.current);
        hoverAlignFrameRef.current = null;
      }
    };
  }, [hoveredCommentId, focusedCommentId]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!focusedCommentId && !focusedMetaCommentId) return;
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const inComment = target.closest('.comment-card');
      const inHighlight = target.closest('.doc-highlight');
      if (!inComment && !inHighlight) {
        setFocusedCommentId(null);
        setFocusedMetaCommentId(null);
      }
    };
    window.addEventListener('pointerdown', onPointerDown);
    return () => {
      window.removeEventListener('pointerdown', onPointerDown);
    };
  }, [focusedCommentId, focusedMetaCommentId]);

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
      void loadWorkerMonitor();
    }
  }, [showSettings]);

  useEffect(() => {
    if (!showSettings) return;
    const interval = setInterval(() => {
      void loadWorkerMonitor();
    }, 5000);
    return () => clearInterval(interval);
  }, [showSettings]);

  useEffect(() => {
    if (showAdmin) {
      void refreshAdminData();
    }
  }, [showAdmin]);

  useEffect(() => {
    if (!statusMessage) return;
    const timer = window.setTimeout(() => {
      setStatusMessage((current) => (current === statusMessage ? null : current));
    }, 4500);
    return () => window.clearTimeout(timer);
  }, [statusMessage]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const syncVisibility = () => {
      setIsPageVisible(document.visibilityState !== 'hidden');
    };
    syncVisibility();
    document.addEventListener('visibilitychange', syncVisibility);
    return () => {
      document.removeEventListener('visibilitychange', syncVisibility);
    };
  }, []);

  useEffect(() => {
    const previous = document.body.style.overflow;
    if (showLibrary || showHistory || showAgents || showSettings || showAdmin) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = previous || '';
    }
    return () => {
      document.body.style.overflow = previous || '';
    };
  }, [showLibrary, showHistory, showAgents, showSettings, showAdmin]);

  async function refreshAll() {
    setErrorMessage(null);
    try {
      const [docList, personaList, libraryList] = await Promise.all([
        apiFetch<DocumentRead[]>('/documents'),
        apiFetch<PersonaRead[]>('/personas'),
        apiFetch<DocumentLibraryEntry[]>('/documents/library')
      ]);
      const safeDocs = Array.isArray(docList) ? docList : [];
      const safePersonas = Array.isArray(personaList) ? personaList : [];
      const safeLibrary = Array.isArray(libraryList) ? libraryList : [];
      setDocuments(safeDocs);
      setPersonas(safePersonas);
      setLibraryEntries(safeLibrary);
      if (enabledPersonas.size === 0 && safePersonas.length > 0) {
        setEnabledPersonas(new Set(safePersonas.filter((p) => p.is_active).map((p) => p.id)));
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

  async function loadWorkerMonitor() {
    setIsWorkerMonitorLoading(true);
    try {
      const monitor = await apiFetch<WorkerMonitorRead>('/admin/worker-monitor');
      setWorkerMonitor(monitor);
    } catch (error) {
      setErrorMessage(normalizeError(error));
      setWorkerMonitor(null);
    } finally {
      setIsWorkerMonitorLoading(false);
    }
  }

  async function loadAdminOverview() {
    try {
      const data = await apiFetch<AdminOverview>('/admin/overview');
      setAdminOverview(data);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function loadAdminUsers() {
    try {
      const users = await apiFetch<AdminUserRead[]>('/admin/users');
      const safeUsers = Array.isArray(users) ? users : [];
      setAdminUsers(safeUsers);
      if (safeUsers.length > 0 && newPermission.user_id === 0) {
        setNewPermission((prev) => ({ ...prev, user_id: safeUsers[0].id }));
      }
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function loadAdminPermissions() {
    try {
      const permissions = await apiFetch<DocumentPermissionRead[]>('/admin/permissions');
      setAdminPermissions(Array.isArray(permissions) ? permissions : []);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function refreshAdminData() {
    await Promise.all([
      loadAdminOverview(),
      loadAdminUsers(),
      loadAdminPermissions()
    ]);
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

  async function loadHistoryJobs() {
    try {
      const jobs = await apiFetch<ReviewJobRead[]>('/review-jobs');
      const safeJobs = Array.isArray(jobs) ? jobs : [];
      safeJobs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setHistoryJobs(safeJobs);
    } catch (error) {
      setErrorMessage(normalizeError(error));
      setHistoryJobs([]);
    }
  }

  async function refreshHistoryPanel(documentId: number | null) {
    setIsHistoryLoading(true);
    try {
      await loadHistoryJobs();
      if (documentId) {
        await loadHistory(documentId);
      } else {
        setHistory([]);
      }
    } finally {
      setIsHistoryLoading(false);
    }
  }

  async function loadReviewJobsForVersion(versionId: number) {
    try {
      const jobs = await apiFetch<ReviewJobRead[]>(`/review-jobs?document_version_id=${versionId}`);
      setReviewJobs(jobs);
      const preferred = pickLatestReviewGenerationJob(jobs);
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

  async function loadReviewJobsSnapshot(versionId: number): Promise<{
    jobs: ReviewJobRead[];
    selectedId: number | null;
  }> {
    const generationAtCall = selectionGenerationRef.current;
    const currentSelected = selectedReviewJobId;
    try {
      const jobs = await apiFetch<ReviewJobRead[]>(`/review-jobs?document_version_id=${versionId}`);
      // Drop the response if the user has switched documents in the meantime.
      if (selectionGenerationRef.current !== generationAtCall) {
        return { jobs: [], selectedId: currentSelected };
      }
      setReviewJobs(jobs);
      if (jobs.length === 0) {
        setSelectedReviewJobId(null);
        return { jobs, selectedId: null };
      }
      let nextSelected = currentSelected;
      const selectedExists =
        currentSelected !== null && jobs.some((job) => job.id === currentSelected);
      if (!selectedExists) {
        const latestGeneration = pickLatestReviewGenerationJob(jobs);
        nextSelected = latestGeneration?.id ?? null;
        setSelectedReviewJobId(nextSelected);
      }
      const running = jobs.some((job) => job.status === 'queued' || job.status === 'running');
      if (!running) {
        setIsReviewStarting(false);
      }
      return { jobs, selectedId: nextSelected };
    } catch {
      // Snapshot polling should not surface transient errors in the primary UI flow.
      return { jobs: [], selectedId: currentSelected };
    }
  }

  async function handleSelectReviewGeneration(reviewJobId: number) {
    if (!selectedVersion) return;
    const nextReviewJob = reviewJobs.find((job) => job.id === reviewJobId) ?? null;

    setSelectedReviewJobId(reviewJobId);
    setFocusedCommentId(null);
    setHoveredCommentId(null);
    setRecentCommentIds(new Set());

    const scoped = await loadComments(selectedVersion.id, false, reviewJobId);
    const generationLabel =
      nextReviewJob?.generation_index && nextReviewJob.generation_index > 0
        ? `v${nextReviewJob.generation_index}`
        : `run #${reviewJobId}`;

    setStatusMessage(
      scoped.length > 0
        ? `Showing ${scoped.length} comments for ${generationLabel}.`
        : `No comments available yet for ${generationLabel}.`
    );
  }

  async function handleRefreshCurrentComments() {
    if (!selectedVersion) return;
    const snapshot = await loadReviewJobsSnapshot(selectedVersion.id);
    const activeReviewJobId = snapshot.selectedId;
    const scoped = await loadComments(selectedVersion.id, false, activeReviewJobId);
    if (activeReviewJobId && scoped.length === 0) {
      const fallback = await loadComments(selectedVersion.id, false, null);
      setStatusMessage(
        fallback.length > 0
          ? `Loaded ${fallback.length} comments from latest available run.`
          : 'No comments available yet for this version.'
      );
      return;
    }
    setStatusMessage(
      scoped.length > 0
        ? `Refreshed ${scoped.length} comments.`
        : 'No comments available yet for this run.'
    );
  }

  async function loadComments(
    versionId: number,
    markRecent: boolean,
    reviewJobId?: number | null
  ): Promise<CommentRead[]> {
    const generationAtCall = selectionGenerationRef.current;
    try {
      const query = reviewJobId ? `&review_job_id=${reviewJobId}` : '';
      const data = await apiFetch<CommentRead[]>(`/comments?document_version_id=${versionId}${query}`);
      // Drop stale response if the user has switched documents.
      if (selectionGenerationRef.current !== generationAtCall) {
        return commentsRef.current;
      }
      const signature = buildCommentSignature(data);
      if (markRecent) {
        const now = Date.now();
        const fresh = new Set<number>();
        if (signature !== commentSignatureRef.current) {
          for (const comment of data) {
            const created = new Date(comment.created_at).getTime();
            if (created > lastPollRef.current - 500) {
              fresh.add(comment.id);
            }
          }
        }
        lastPollRef.current = now;
        setRecentCommentIds(fresh);
      }
      if (signature !== commentSignatureRef.current) {
        setComments(data);
        return data;
      }
      return commentsRef.current;
    } catch (error) {
      setErrorMessage(normalizeError(error));
      return [];
    }
  }

  async function fetchLatestMetaReviewRun(
    versionId: number,
    reviewJobId?: number | null,
    options?: {
      includeComments?: boolean;
    }
  ): Promise<MetaReviewRunRead> {
    const params = new URLSearchParams({ document_version_id: String(versionId) });
    if (reviewJobId) {
      params.set('review_job_id', String(reviewJobId));
    }
    if (options?.includeComments === false) {
      params.set('include_comments', 'false');
    }
    return apiFetch<MetaReviewRunRead>(`/meta-reviews/latest?${params.toString()}`);
  }

  async function loadOrCreateMetaReview(
    versionId: number,
    reviewJobId?: number | null,
    force = false,
    options?: {
      fallbackToIndividualOnMissing?: boolean;
      reviewJobStatus?: string | null;
    }
  ) {
    setIsMetaLoading(true);
    setMetaViewState('loading');
    try {
      if (!force) {
        try {
          const latest = await fetchLatestMetaReviewRun(versionId, reviewJobId, {
            includeComments: true
          });
          setMetaReviewRun(latest);
          if (isMetaSynthesisPendingStatus(latest.status)) {
            setMetaViewState('pending');
            setStatusMessage('Meta directives are still being synthesized.');
          } else if (isMetaSynthesisFailedStatus(latest.status)) {
            setMetaViewState('error');
            setStatusMessage(
              latest.error_message
                ? `Meta synthesis failed: ${latest.error_message}`
                : 'Meta synthesis failed. Recompute to retry.'
            );
          } else {
            setMetaViewState('ready');
            setStatusMessage(
              latest.comments.length > 0
                ? `Meta review loaded (${latest.comments.length} directives).`
                : 'Meta review loaded (no directives).'
            );
          }
          return latest;
        } catch (error) {
          const message = normalizeError(error);
          const lower = message.toLowerCase();
          const missingMetaRun =
            lower.includes('404') ||
            lower.includes('meta review run not found') ||
            lower.includes('not found');
          if (!missingMetaRun) {
            throw error;
          }

          setMetaReviewRun(null);
          const synthesisPending = isMetaSynthesisPendingStatus(options?.reviewJobStatus);
          if (synthesisPending) {
            setMetaViewState('pending');
            setStatusMessage('Meta directives are pending while the active review run is still processing.');
            return null;
          }

          setMetaViewState('missing');
          if (options?.fallbackToIndividualOnMissing) {
            setCommentViewMode('individual');
            setStatusMessage('No meta directives found for this run yet. Showing individual reviewer comments.');
          } else {
            setStatusMessage('No meta directives available for this run yet. Recompute to synthesize now.');
          }
          return null;
        }
      }

      const created = await apiFetch<MetaReviewRunRead>('/meta-reviews', {
        method: 'POST',
        body: JSON.stringify({
          document_version_id: versionId,
          review_job_id: reviewJobId ?? null,
          force
        })
      });
      setMetaReviewRun(created);
      if (isMetaSynthesisPendingStatus(created.status)) {
        setMetaViewState('pending');
        setStatusMessage('Meta synthesis queued. Directives will appear shortly.');
      } else if (isMetaSynthesisFailedStatus(created.status)) {
        setMetaViewState('error');
        setStatusMessage(
          created.error_message
            ? `Meta synthesis failed: ${created.error_message}`
            : 'Meta synthesis failed. Recompute to retry.'
        );
      } else {
        setMetaViewState('ready');
        setStatusMessage(
          created.comments.length > 0
            ? `Meta review ready (${created.comments.length} directives).`
            : 'No meta directives produced for this version.'
        );
      }
      return created;
    } catch (error) {
      const message = normalizeError(error);
      setErrorMessage(message);
      setMetaViewState('error');
      if (message.toLowerCase().includes('no reviewer comments available yet')) {
        setStatusMessage('Meta review is waiting for reviewer comments to arrive.');
      }
      return null;
    } finally {
      setIsMetaLoading(false);
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
    if (ids.length === 0) {
      setStatusMessage('Select one or more documents first.');
      return;
    }
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
    if (ids.length === 0) {
      setStatusMessage('Select one or more documents first.');
      return;
    }
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
    if (targets.length === 0) {
      setStatusMessage('Select documents with at least one version to re-run review.');
      return;
    }
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

  function navigateToDocumentContext(documentId: number) {
    const nextParams = new URLSearchParams(latestSearchParamsKeyRef.current);
    nextParams.set('doc', String(documentId));
    nextParams.delete('run');
    const nextQuery = nextParams.toString();
    router.replace(nextQuery ? `/?${nextQuery}` : '/');
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
      navigateToDocumentContext(lastDocId);
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
    const resolvedApiBase =
      apiBase.trim() || (typeof window !== 'undefined' ? `${window.location.origin}/api` : getApiBase());
    setTenantId(tenantId || DEFAULT_TENANT);
    setApiBase(resolvedApiBase);
    setAccessToken(accessToken);
    setStatusMessage('Connection settings saved.');
    void refreshAll();
  }

  async function handleExportAgents() {
    try {
      const bundle = await apiFetch<{
        schema_version: string;
        exported_at: string;
        personas: unknown[];
      }>('/personas/bundle/export');
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      downloadFile(
        `agent-pack-${stamp}.json`,
        JSON.stringify(bundle, null, 2),
        'application/json;charset=utf-8'
      );
      setStatusMessage('Agent pack exported.');
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function runAgentImport(bundle: AgentBundleImport, dry_run: boolean) {
    return apiFetch<AgentImportResult>('/personas/bundle/import', {
      method: 'POST',
      body: JSON.stringify({
        schema_version: bundle.schema_version ?? 'v1',
        conflict_policy: agentImportConflictPolicy,
        dry_run,
        personas: bundle.personas ?? []
      })
    });
  }

  async function refreshAgentImportPreview(bundle: AgentBundleImport) {
    setIsAgentImporting(true);
    try {
      const preview = await runAgentImport(bundle, true);
      setAgentImportPreview(preview);
    } catch (error) {
      setErrorMessage(normalizeError(error));
      setAgentImportPreview(null);
    } finally {
      setIsAgentImporting(false);
    }
  }

  async function handleApplyAgentImport() {
    if (!pendingAgentImport) return;
    setIsAgentImporting(true);
    try {
      const result = await runAgentImport(pendingAgentImport, false);
      await refreshAll();
      setStatusMessage(
        `Import complete: created ${result.created}, updated ${result.updated}, renamed ${result.renamed}, skipped ${result.skipped}.`
      );
      setPendingAgentImport(null);
      setAgentImportPreview(null);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setIsAgentImporting(false);
    }
  }

  async function handleImportAgentsFromFile(file: File) {
    try {
      const rawText =
        typeof file.text === 'function' ? await file.text() : await new Response(file).text();
      const text = rawText.replace(/^\uFEFF/, '').trim();
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.personas)) {
        throw new Error('Invalid agent bundle: expected JSON object with a personas array.');
      }
      const bundle: AgentBundleImport = {
        schema_version: parsed.schema_version ?? 'v1',
        personas: parsed.personas ?? [],
        file_name: file.name
      };
      setPendingAgentImport(bundle);
      await refreshAgentImportPreview(bundle);
      setStatusMessage('Import preview ready. Review counts and apply when ready.');
    } catch (error) {
      setErrorMessage(`Import failed: ${normalizeError(error)}`);
    }
  }

  async function handleCreateAdminUser() {
    if (!newAdminUser.name.trim() || !newAdminUser.email.trim()) {
      setErrorMessage('User name and email are required.');
      return;
    }
    try {
      await apiFetch<AdminUserRead>('/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          name: newAdminUser.name.trim(),
          email: newAdminUser.email.trim(),
          role: newAdminUser.role,
          is_active: true
        })
      });
      setNewAdminUser({ name: '', email: '', role: 'default' });
      setStatusMessage('User created.');
      await refreshAdminData();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleUpdateAdminUser(
    userId: number,
    patch: Partial<{ role: 'admin' | 'default'; is_active: boolean }>
  ) {
    try {
      await apiFetch<AdminUserRead>(`/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch)
      });
      await refreshAdminData();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleDeleteAdminUser(userId: number) {
    const confirmed = window.confirm('Delete this user and all document permissions?');
    if (!confirmed) return;
    try {
      await apiFetch<null>(`/admin/users/${userId}`, { method: 'DELETE' });
      setStatusMessage('User deleted.');
      await refreshAdminData();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleCreatePermission() {
    if (!selectedPermissionDocumentId || newPermission.user_id <= 0) {
      setErrorMessage('Select a document and user before adding permission.');
      return;
    }
    try {
      await apiFetch<DocumentPermissionRead>('/admin/permissions', {
        method: 'POST',
        body: JSON.stringify({
          document_id: selectedPermissionDocumentId,
          user_id: newPermission.user_id,
          permission_level: newPermission.permission_level
        })
      });
      setStatusMessage('Permission upserted.');
      await refreshAdminData();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleUpdatePermission(
    permissionId: number,
    permission_level: 'owner' | 'editor' | 'viewer'
  ) {
    try {
      await apiFetch<DocumentPermissionRead>(`/admin/permissions/${permissionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ permission_level })
      });
      await refreshAdminData();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
  }

  async function handleDeletePermission(permissionId: number) {
    try {
      await apiFetch<null>(`/admin/permissions/${permissionId}`, { method: 'DELETE' });
      await refreshAdminData();
    } catch (error) {
      setErrorMessage(normalizeError(error));
    }
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
        review_inline: systemConfig.review_inline,
        redis_url: systemConfig.redis_url,
        review_queue_name: systemConfig.review_queue_name,
        doc_repo_enabled: systemConfig.doc_repo_enabled,
        doc_repo_root: systemConfig.doc_repo_root,
        cors_allow_origins: systemConfig.cors_allow_origins,
        cors_allow_origin_regex: systemConfig.cors_allow_origin_regex,
        cors_allow_credentials: systemConfig.cors_allow_credentials,
        cors_allow_methods: systemConfig.cors_allow_methods,
        cors_allow_headers: systemConfig.cors_allow_headers,
        cors_max_age: systemConfig.cors_max_age,
        meta_agent_name: systemConfig.meta_agent_name,
        meta_agent_description: systemConfig.meta_agent_description,
        meta_agent_system_prompt: systemConfig.meta_agent_system_prompt,
        meta_agent_focus_areas: systemConfig.meta_agent_focus_areas,
        meta_agent_tone: systemConfig.meta_agent_tone,
        meta_agent_reference_notes: systemConfig.meta_agent_reference_notes,
        meta_agent_output_format: systemConfig.meta_agent_output_format,
        meta_agent_output_max_bullets: systemConfig.meta_agent_output_max_bullets,
        meta_agent_output_require_quote_excerpt:
          systemConfig.meta_agent_output_require_quote_excerpt,
        meta_agent_output_require_actionable: systemConfig.meta_agent_output_require_actionable,
        meta_agent_output_include_severity: systemConfig.meta_agent_output_include_severity,
        meta_agent_examples: systemConfig.meta_agent_examples,
        meta_max_directives_per_group: systemConfig.meta_max_directives_per_group,
        meta_global_dedupe_threshold: systemConfig.meta_global_dedupe_threshold
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
        redis_url: systemConfig.redis_url,
        review_queue_name: systemConfig.review_queue_name,
        doc_repo_enabled: systemConfig.doc_repo_enabled,
        doc_repo_root: systemConfig.doc_repo_root,
        cors_allow_origins: systemConfig.cors_allow_origins,
        cors_allow_origin_regex: systemConfig.cors_allow_origin_regex,
        cors_allow_credentials: systemConfig.cors_allow_credentials,
        cors_allow_methods: systemConfig.cors_allow_methods,
        cors_allow_headers: systemConfig.cors_allow_headers,
        cors_max_age: systemConfig.cors_max_age,
        meta_agent_name: systemConfig.meta_agent_name,
        meta_agent_description: systemConfig.meta_agent_description,
        meta_agent_system_prompt: systemConfig.meta_agent_system_prompt,
        meta_agent_focus_areas: systemConfig.meta_agent_focus_areas,
        meta_agent_tone: systemConfig.meta_agent_tone,
        meta_agent_reference_notes: systemConfig.meta_agent_reference_notes,
        meta_agent_output_format: systemConfig.meta_agent_output_format,
        meta_agent_output_max_bullets: systemConfig.meta_agent_output_max_bullets,
        meta_agent_output_require_quote_excerpt:
          systemConfig.meta_agent_output_require_quote_excerpt,
        meta_agent_output_require_actionable: systemConfig.meta_agent_output_require_actionable,
        meta_agent_output_include_severity: systemConfig.meta_agent_output_include_severity,
        meta_agent_examples: systemConfig.meta_agent_examples,
        meta_max_directives_per_group: systemConfig.meta_max_directives_per_group,
        meta_global_dedupe_threshold: systemConfig.meta_global_dedupe_threshold,
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

  function setPersonaForEditing(persona: PersonaRead) {
    setIsCreatingAgent(false);
    setEditingPersonaId(persona.id);
    setAgentDraft(createDraftFromPersona(persona));
  }

  function handleCreateAgent() {
    setIsCreatingAgent(true);
    setEditingPersonaId(null);
    setAgentDraft(createEmptyAgentDraft());
  }

  function handleDuplicateAgent(persona: PersonaRead) {
    const duplicateName = createDuplicateAgentName(personas, persona.name);
    const draft = createDraftFromPersona(persona);
    setIsCreatingAgent(true);
    setEditingPersonaId(null);
    setAgentDraft({
      ...draft,
      name: duplicateName,
      sort_order: persona.sort_order + 1
    });
    setStatusMessage(`Duplicating "${persona.name}". Save to create a new agent.`);
  }

  async function handleSaveAgent() {
    setErrorMessage(null);
    if (!agentDraft.name.trim()) {
      setErrorMessage('Agent name is required.');
      return;
    }
    if (!agentDraft.system_prompt.trim()) {
      setErrorMessage('System prompt is required.');
      return;
    }
    setIsAgentSaving(true);
    try {
      const payload = buildPersonaPayload(agentDraft);
      const saved = editingPersonaId
        ? await apiFetch<PersonaRead>(`/personas/${editingPersonaId}`, {
            method: 'PATCH',
            body: JSON.stringify(payload)
          })
        : await apiFetch<PersonaRead>('/personas', {
            method: 'POST',
            body: JSON.stringify(payload)
          });

      setPersonas((prev) => {
        const next = editingPersonaId
          ? prev.map((persona) => (persona.id === saved.id ? saved : persona))
          : [...prev, saved];
        return next.slice().sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
      });
      if (saved.color_theme) {
        updateAgentTheme(saved.id, saved.color_theme, saved.name);
      }
      setIsCreatingAgent(false);
      setEditingPersonaId(saved.id);
      setAgentDraft(createDraftFromPersona(saved));
      setStatusMessage(editingPersonaId ? 'Agent updated.' : 'Agent created.');
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setIsAgentSaving(false);
    }
  }

  async function handleDeleteAgent(persona: PersonaRead) {
    if (persona.is_system_locked) {
      setErrorMessage('System default agents cannot be deleted.');
      return;
    }
    const confirmed = window.confirm(`Delete agent "${persona.name}"?`);
    if (!confirmed) return;

    setAgentBusyId(persona.id);
    setErrorMessage(null);
    try {
      await apiFetch<null>(`/personas/${persona.id}`, { method: 'DELETE' });
      const next = personas.filter((item) => item.id !== persona.id);
      setPersonas(next);
      if (editingPersonaId === persona.id) {
        if (next.length > 0) {
          setPersonaForEditing(next[0]);
        } else {
          setIsCreatingAgent(true);
          setEditingPersonaId(null);
          setAgentDraft(createEmptyAgentDraft());
        }
      }
      setStatusMessage('Agent deleted.');
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setAgentBusyId(null);
    }
  }

  async function handleResetDefaultAgents() {
    const confirmed = window.confirm(
      'Reset system default agents to the latest defaults? Custom agents are preserved.'
    );
    if (!confirmed) return;
    setErrorMessage(null);
    setIsAgentSaving(true);
    try {
      const next = await apiFetch<PersonaRead[]>('/personas/reset-defaults', { method: 'POST' });
      setPersonas(next);
      if (next.length > 0) {
        const stillSelected =
          editingPersonaId !== null ? next.find((persona) => persona.id === editingPersonaId) : null;
        if (stillSelected) {
          setIsCreatingAgent(false);
          setAgentDraft(createDraftFromPersona(stillSelected));
        } else {
          setPersonaForEditing(next[0]);
        }
      } else {
        setIsCreatingAgent(true);
        setEditingPersonaId(null);
        setAgentDraft(createEmptyAgentDraft());
      }
      setStatusMessage('Default agents reset.');
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setIsAgentSaving(false);
    }
  }

  async function handleRevertDefaultAgent(persona: PersonaRead) {
    setErrorMessage(null);
    setAgentBusyId(persona.id);
    try {
      const reverted = await apiFetch<PersonaRead>(`/personas/${persona.id}/reset-default`, {
        method: 'POST'
      });
      setPersonas((prev) =>
        prev
          .map((item) => (item.id === reverted.id ? reverted : item))
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
      );
      setPersonaForEditing(reverted);
      if (reverted.color_theme) {
        updateAgentTheme(reverted.id, reverted.color_theme, reverted.name);
      }
      setStatusMessage(`Reverted "${reverted.name}" to default.`);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setAgentBusyId(null);
    }
  }

  async function handleQuickToggleAgent(persona: PersonaRead) {
    setErrorMessage(null);
    setAgentBusyId(persona.id);
    try {
      const updated = await apiFetch<PersonaRead>(`/personas/${persona.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          is_active: !persona.is_active
        })
      });
      setPersonas((prev) =>
        prev
          .map((item) => (item.id === updated.id ? updated : item))
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
      );
      if (editingPersonaId === updated.id) {
        setAgentDraft(createDraftFromPersona(updated));
      }
      setStatusMessage(updated.is_active ? `Enabled "${updated.name}".` : `Disabled "${updated.name}".`);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setAgentBusyId(null);
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

  function enableAllPersonas() {
    const active = personas.filter((persona) => persona.is_active).map((persona) => persona.id);
    setEnabledPersonas(new Set(active));
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
  const commentById = useMemo(() => {
    const map = new Map<number, CommentRead>();
    for (const comment of comments) {
      map.set(comment.id, comment);
    }
    return map;
  }, [comments]);
  const hasFilteredOutComments = comments.length > 0 && visibleComments.length === 0;

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

  const visibleAdminPermissions = useMemo(() => {
    if (!selectedPermissionDocumentId) return adminPermissions;
    return adminPermissions.filter((perm) => perm.document_id === selectedPermissionDocumentId);
  }, [adminPermissions, selectedPermissionDocumentId]);

  const filteredMetaComments = useMemo(() => {
    const comments = metaReviewRun?.comments ?? [];
    const subset =
      metaCategoryFilter === 'all'
        ? comments
        : comments.filter((comment) => comment.category === metaCategoryFilter);
    const priorityRank: Record<string, number> = {
      critical: 4,
      high: 3,
      medium: 2,
      low: 1
    };
    return subset
      .slice()
      .sort((a, b) => {
        const scoreDelta = (b.rank_score ?? 0) - (a.rank_score ?? 0);
        if (scoreDelta !== 0) return scoreDelta;
        if (a.start_offset !== b.start_offset) return a.start_offset - b.start_offset;
        const rankDelta = (priorityRank[b.priority] ?? 0) - (priorityRank[a.priority] ?? 0);
        if (rankDelta !== 0) return rankDelta;
        return a.order_index - b.order_index;
      });
  }, [metaReviewRun, metaCategoryFilter]);
  const metaSummary = metaReviewRun?.summary ?? null;

  const activeCommentId = focusedCommentId ?? hoveredCommentId;
  const activeMetaCommentId = commentViewMode === 'meta' ? focusedMetaCommentId ?? hoveredMetaCommentId : null;
  const activePathId =
    commentViewMode === 'meta'
      ? activeMetaCommentId
        ? `m-${activeMetaCommentId}`
        : null
      : activeCommentId
        ? `c-${activeCommentId}`
        : null;

  useEffect(() => {
    if (commentViewMode !== 'meta') return;
    if (!focusedMetaCommentId) return;
    if (metaViewState !== 'ready') return;
    const existsInRun = metaReviewRun?.comments?.some((comment) => comment.id === focusedMetaCommentId);
    if (existsInRun) return;
    setFocusedMetaCommentId(null);
    setStatusMessage(`Requested directive #${focusedMetaCommentId} is not available for this run.`);
  }, [commentViewMode, focusedMetaCommentId, metaViewState, metaReviewRun]);

  useEffect(() => {
    if (!hoveredMetaCommentId || focusedMetaCommentId) return;
    if (commentViewMode !== 'meta') return;
    if (hoverAlignFrameRef.current !== null) {
      cancelAnimationFrame(hoverAlignFrameRef.current);
    }
    hoverAlignFrameRef.current = requestAnimationFrame(() => {
      const card = metaCardRefs.current[hoveredMetaCommentId];
      card?.scrollIntoView?.({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      const metaItem = filteredMetaComments.find((item) => item.id === hoveredMetaCommentId);
      const sourceCommentId = metaItem?.sources[0]?.comment_id ?? null;
      if (sourceCommentId) {
        const mark = markRefs.current[sourceCommentId];
        mark?.scrollIntoView?.({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      }
    });
    return () => {
      if (hoverAlignFrameRef.current !== null) {
        cancelAnimationFrame(hoverAlignFrameRef.current);
        hoverAlignFrameRef.current = null;
      }
    };
  }, [hoveredMetaCommentId, focusedMetaCommentId, commentViewMode, filteredMetaComments]);
  const floatingMetaComment = useMemo(
    () => filteredMetaComments.find((comment) => comment.id === activeMetaCommentId) ?? null,
    [filteredMetaComments, activeMetaCommentId]
  );
  const [floatingCardStyle, setFloatingCardStyle] = useState<{
    left: number;
    top: number;
    width: number;
  } | null>(null);
  const floatingComment = useMemo(
    () => visibleComments.find((comment) => comment.id === activeCommentId) ?? null,
    [visibleComments, activeCommentId]
  );

  useEffect(() => {
    hoveredCommentIdRef.current = hoveredCommentId;
  }, [hoveredCommentId]);

  useEffect(() => {
    hoveredMetaCommentIdRef.current = hoveredMetaCommentId;
  }, [hoveredMetaCommentId]);

  useEffect(() => {
    const routeParams = new URLSearchParams(searchParamsKey);
    const requestedDirectiveId = parsePositiveIntParam(routeParams.get('directive'));
    setHoveredMetaCommentId(null);
    if (requestedDirectiveId !== null) {
      return;
    }
    setFocusedMetaCommentId(null);
  }, [selectedVersionId, selectedReviewJobId, searchParamsKey]);

  useEffect(() => {
    if (commentViewMode === 'meta') return;
    setHoveredMetaCommentId(null);
    setFocusedMetaCommentId(null);
  }, [commentViewMode]);

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
        span.className = 'doc-highlight view-highlight';
        span.dataset.commentId = String(match.comment.id);
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
    agentThemes
  ]);

  useEffect(() => {
    const root = docBodyRef.current;
    if (!root) return;
    const highlights = root.querySelectorAll<HTMLElement>('span[data-odr-view-highlight="1"]');
    highlights.forEach((node) => {
      const raw = node.dataset.commentId;
      const commentId = raw ? Number(raw) : Number.NaN;
      const selected = Number.isFinite(commentId) && activeCommentId === commentId;
      node.classList.toggle('selected', selected);
    });
  }, [activeCommentId, docMode, highlightTick]);

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
  const metaHoverCenterIndex = useMemo(
    () => filteredMetaComments.findIndex((comment) => comment.id === hoveredMetaCommentId),
    [filteredMetaComments, hoveredMetaCommentId]
  );
  const metaFocusCenterIndex = useMemo(
    () => filteredMetaComments.findIndex((comment) => comment.id === focusedMetaCommentId),
    [filteredMetaComments, focusedMetaCommentId]
  );
  const metaDockCenterIndex = focusedMetaCommentId ? metaFocusCenterIndex : metaHoverCenterIndex;

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
      const intersectsViewport = (rect: DOMRect, padding = 24) =>
        rect.bottom >= -padding &&
        rect.top <= window.innerHeight + padding &&
        rect.right >= -padding &&
        rect.left <= window.innerWidth + padding;
      const nextPaths: ConnectorPath[] = [];

      if (commentViewMode === 'meta') {
        for (const metaComment of filteredMetaComments) {
          const card = metaCardRefs.current[metaComment.id];
          if (!card) continue;
          const to = card.getBoundingClientRect();
          if (!intersectsViewport(to)) continue;
          const color = colorForPriority(metaComment.priority);
          metaComment.sources.forEach((source, sourceIndex) => {
            const sourceCommentId = source.comment_id;
            const mark = sourceCommentId ? markRefs.current[sourceCommentId] : null;
            if (!mark) return;
            const from = mark.getBoundingClientRect();
            const verticalGap = Math.abs(to.top - from.top);
            const maxVerticalGap = Math.max(window.innerHeight * 2.5, 1800);
            if (verticalGap > maxVerticalGap) return;
            const startX = from.right - workspaceRect.left + 6;
            const startY = from.top + from.height / 2 - workspaceRect.top;
            const endX = to.left - workspaceRect.left - 8;
            const endY = to.top + to.height / 2 - workspaceRect.top;
            const delta = Math.max(42, (endX - startX) * 0.45);
            const path = `M ${startX} ${startY} C ${startX + delta} ${startY}, ${endX - delta} ${endY}, ${endX} ${endY}`;
            nextPaths.push({ id: `m-${metaComment.id}-${sourceIndex}`, path, color });
          });
        }
      } else {
        for (const comment of anchoredComments) {
          const mark = markRefs.current[comment.id];
          const card = cardRefs.current[comment.id];
          if (!mark || !card) continue;

          const from = mark.getBoundingClientRect();
          const to = card.getBoundingClientRect();
          if (!intersectsViewport(to)) continue;
          const verticalGap = Math.abs(to.top - from.top);
          const maxVerticalGap = Math.max(window.innerHeight * 2.5, 1800);
          if (verticalGap > maxVerticalGap) continue;
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
          nextPaths.push({ id: `c-${comment.id}`, path, color });
        }
      }
      setConnectorPaths((prev) => {
        if (prev.length !== nextPaths.length) return nextPaths;
        for (let idx = 0; idx < prev.length; idx += 1) {
          if (
            prev[idx].id !== nextPaths[idx].id ||
            prev[idx].color !== nextPaths[idx].color ||
            prev[idx].path !== nextPaths[idx].path
          ) {
            return nextPaths;
          }
        }
        return prev;
      });
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
  }, [
    anchoredComments,
    selectedVersion,
    personaMap,
    agentThemes,
    docMode,
    highlightTick,
    commentViewMode,
    filteredMetaComments,
    hoveredMetaCommentId,
    focusedMetaCommentId
  ]);

  useEffect(() => {
    if (commentViewMode !== 'individual' || !activeCommentId) {
      setFloatingCardStyle(null);
      return;
    }
    const recalc = () => {
      const card = cardRefs.current[activeCommentId];
      if (!card) {
        setFloatingCardStyle(null);
        return;
      }
      const rect = card.getBoundingClientRect();
      const margin = 18;
      const topMargin = 82;
      const scale = 1.55;
      const width = Math.min(rect.width * scale, window.innerWidth - margin * 2);
      const scaledHeight = rect.height * scale;
      const left = Math.min(
        window.innerWidth - width - margin,
        Math.max(margin, rect.right - width)
      );
      const top = Math.min(
        window.innerHeight - scaledHeight - margin,
        Math.max(topMargin, rect.top + (rect.height - scaledHeight) / 2)
      );
      setFloatingCardStyle({ left, top, width });
    };

    const frame = requestAnimationFrame(recalc);
    const onRecalc = () => requestAnimationFrame(recalc);
    window.addEventListener('resize', onRecalc);
    window.addEventListener('scroll', onRecalc, true);
    const feed = feedListRef.current;
    const doc = docPanelRef.current;
    feed?.addEventListener('scroll', onRecalc);
    doc?.addEventListener('scroll', onRecalc);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', onRecalc);
      window.removeEventListener('scroll', onRecalc, true);
      feed?.removeEventListener('scroll', onRecalc);
      doc?.removeEventListener('scroll', onRecalc);
    };
  }, [activeCommentId, commentViewMode, visibleComments, dockCenterIndex]);

  useEffect(() => {
    if (commentViewMode !== 'meta' || !activeMetaCommentId) {
      setFloatingMetaCardStyle(null);
      return;
    }
    const recalc = () => {
      const card = metaCardRefs.current[activeMetaCommentId];
      if (!card) {
        setFloatingMetaCardStyle(null);
        return;
      }
      const rect = card.getBoundingClientRect();
      const margin = 18;
      const topMargin = 82;
      const scale = 1.55;
      const width = Math.min(rect.width * scale, window.innerWidth - margin * 2);
      const scaledHeight = rect.height * scale;
      const left = Math.min(
        window.innerWidth - width - margin,
        Math.max(margin, rect.right - width)
      );
      const top = Math.min(
        window.innerHeight - scaledHeight - margin,
        Math.max(topMargin, rect.top + (rect.height - scaledHeight) / 2)
      );
      setFloatingMetaCardStyle({ left, top, width });
    };

    const frame = requestAnimationFrame(recalc);
    const onRecalc = () => requestAnimationFrame(recalc);
    window.addEventListener('resize', onRecalc);
    window.addEventListener('scroll', onRecalc, true);
    const feed = feedListRef.current;
    const doc = docPanelRef.current;
    feed?.addEventListener('scroll', onRecalc);
    doc?.addEventListener('scroll', onRecalc);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', onRecalc);
      window.removeEventListener('scroll', onRecalc, true);
      feed?.removeEventListener('scroll', onRecalc);
      doc?.removeEventListener('scroll', onRecalc);
    };
  }, [activeMetaCommentId, commentViewMode, filteredMetaComments, metaDockCenterIndex]);

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

  function drillDownToSourceComment(source: MetaCommentSourceRead) {
    const sourceComment = commentById.get(source.comment_id);
    if (!sourceComment) {
      setStatusMessage(`Source comment #${source.comment_id} is unavailable for this run.`);
      return;
    }

    if (!enabledPersonas.has(sourceComment.persona_id)) {
      setEnabledPersonas((prev) => {
        const next = new Set(prev);
        next.add(sourceComment.persona_id);
        return next;
      });
    }

    setCommentModeSelectionSource('manual');
    setCommentViewMode('individual');
    setFocusedMetaCommentId(null);
    setHoveredMetaCommentId(null);
    setFocusedCommentId(sourceComment.id);
    setDocMode('source');
    setStatusMessage(`Jumped to source comment #${source.comment_id} (${source.reviewer_name}).`);
  }

  function handleFeedPointerMove(event: ReactMouseEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement | null;
    if (!target) return;
    if (commentViewMode === 'meta') {
      if (focusedMetaCommentId) return;
      const metaCard = target.closest<HTMLElement>('.comment-card[data-meta-id]');
      if (!metaCard) {
        if (hoveredMetaCommentIdRef.current !== null) {
          setHoveredMetaCommentId(null);
        }
        return;
      }
      const rawMetaId = metaCard.dataset.metaId;
      if (!rawMetaId) return;
      const nextMetaId = Number(rawMetaId);
      if (!Number.isFinite(nextMetaId)) return;
      if (hoveredMetaCommentIdRef.current !== nextMetaId) {
        setHoveredMetaCommentId(nextMetaId);
      }
      return;
    }
    if (focusedCommentId) return;
    const card = target.closest<HTMLElement>('.comment-card[data-comment-id]');
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
    if (commentViewMode === 'individual' && (!hoveredCommentId || focusedCommentId)) return;
    if (commentViewMode === 'meta' && (!hoveredMetaCommentId || focusedMetaCommentId)) return;
    const onPointerMove = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const inFeed = Boolean(target.closest('.feed-panel'));
      if (!inFeed) {
        if (commentViewMode === 'individual') {
          setHoveredCommentId(null);
        } else {
          setHoveredMetaCommentId(null);
        }
      }
    };
    window.addEventListener('pointermove', onPointerMove);
    return () => {
      window.removeEventListener('pointermove', onPointerMove);
    };
  }, [
    hoveredCommentId,
    focusedCommentId,
    hoveredMetaCommentId,
    focusedMetaCommentId,
    commentViewMode
  ]);

  useEffect(() => {
    if (normalizedPath !== '/') return;

    const routeParams = new URLSearchParams(searchParamsKey);
    let appliedRouteState = false;
    const requestedMode = parseCommentViewModeParam(routeParams.get('mode'));
    const requestedDirectiveId = parsePositiveIntParam(routeParams.get('directive'));

    if (requestedMode && requestedMode !== commentViewMode) {
      setCommentModeSelectionSource('manual');
      setCommentViewMode(requestedMode);
      appliedRouteState = true;
    }

    if (requestedDirectiveId !== null && requestedMode !== 'individual') {
      if (requestedMode !== 'meta' && commentViewMode !== 'meta') {
        setCommentModeSelectionSource('manual');
        setCommentViewMode('meta');
        appliedRouteState = true;
      }
      if (focusedMetaCommentId !== requestedDirectiveId) {
        setFocusedMetaCommentId(requestedDirectiveId);
        appliedRouteState = true;
      }
    } else if (requestedDirectiveId === null && focusedMetaCommentId !== null) {
      setFocusedMetaCommentId(null);
      appliedRouteState = true;
    }

    if (appliedRouteState) {
      isApplyingRouteQueryStateRef.current = true;
    }
  }, [normalizedPath, searchParamsKey, selectedVersionId, selectedReviewJobId]);

  useEffect(() => {
    if (normalizedPath !== '/') return;

    if (isApplyingRouteQueryStateRef.current) {
      isApplyingRouteQueryStateRef.current = false;
      return;
    }

    const currentParams = new URLSearchParams(searchParamsKey);
    const hasDocumentContext = selectedDocumentId !== null || Boolean(currentParams.get('doc'));
    if (!hasDocumentContext) return;

    const nextParams = new URLSearchParams(currentParams.toString());
    nextParams.set('mode', commentViewMode);
    if (commentViewMode === 'meta' && focusedMetaCommentId !== null) {
      nextParams.set('directive', String(focusedMetaCommentId));
    } else {
      nextParams.delete('directive');
    }

    const currentQuery = currentParams.toString();
    const nextQuery = nextParams.toString();
    if (currentQuery === nextQuery) return;

    router.replace(nextQuery ? `/?${nextQuery}` : '/');
  }, [
    normalizedPath,
    searchParamsKey,
    selectedDocumentId,
    commentViewMode,
    focusedMetaCommentId,
    router
  ]);

  useEffect(() => {
    if (normalizedPath !== '/') return;
    const routeParams = new URLSearchParams(searchParamsKey);
    const docRaw = routeParams.get('doc');
    if (!docRaw) return;
    const docId = Number(docRaw);
    if (!Number.isFinite(docId) || docId <= 0) return;
    const runRequested = routeParams.get('run') === '1';
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
  }, [normalizedPath, searchParamsKey]);

  function navigatePanel(path: '/library' | '/agents' | '/history' | '/system' | '/admin') {
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

  function buildReviewBundleJson(metaRunOverride?: MetaReviewRunRead | null) {
    if (!selectedVersion) return null;
    const context = buildCommentExportContext();
    if (!context) return null;
    const runForBundle = metaRunOverride !== undefined ? metaRunOverride : metaReviewRun;
    const comments = context.sorted.map((comment) => ({
      id: comment.id,
      persona_id: comment.persona_id,
      persona_name: personaMap.get(comment.persona_id)?.name ?? null,
      text: comment.text,
      start_offset: comment.start_offset,
      end_offset: comment.end_offset,
      excerpt: comment.excerpt,
      output_metadata: comment.output_metadata ?? null,
      created_at: comment.created_at
    }));
    const personaIds = new Set(comments.map((comment) => comment.persona_id));
    const personasForBundle = personas
      .filter((persona) => personaIds.has(persona.id))
      .map((persona) => ({
        id: persona.id,
        name: persona.name,
        description: persona.description,
        system_prompt: persona.system_prompt,
        focus_areas: persona.focus_areas,
        tone: persona.tone,
        reference_notes: persona.reference_notes,
        output_requirements: persona.output_requirements,
        examples: persona.examples,
        sort_order: persona.sort_order,
        color_theme: persona.color_theme,
        is_active: persona.is_active
      }));
    return {
      schema_version: 'odr.review-bundle.v2',
      exported_at: new Date().toISOString(),
      document: {
        title: context.title
      },
      version: {
        version_label: selectedVersion.version_label,
        content: selectedVersion.content
      },
      review_job: selectedReviewJob
        ? {
            status: selectedReviewJob.status,
            trigger: selectedReviewJob.trigger,
            provider: selectedReviewJob.provider,
            model: selectedReviewJob.model,
            created_at: selectedReviewJob.created_at,
            completed_at: selectedReviewJob.completed_at
          }
        : null,
      personas: personasForBundle,
      comments,
      meta_review_run: runForBundle
        ? {
            status: runForBundle.status,
            is_synthesized: runForBundle.is_synthesized,
            provider: runForBundle.provider,
            model: runForBundle.model,
            error_message: runForBundle.error_message,
            created_at: runForBundle.created_at,
            summary: runForBundle.summary
              ? {
                  verdict: runForBundle.summary.verdict,
                  attention_points: runForBundle.summary.attention_points.map((point) => ({
                    meta_comment_id: point.meta_comment_id,
                    location: point.location,
                    reason: point.reason,
                    priority: point.priority,
                    start_offset: point.start_offset,
                    end_offset: point.end_offset,
                    source_comment_ids: point.source_comment_ids
                  })),
                  clean_sections: runForBundle.summary.clean_sections,
                  clean_statement: runForBundle.summary.clean_statement
                }
              : null,
            comments: runForBundle.comments.map((metaComment) => ({
              content: metaComment.content,
              category: metaComment.category,
              priority: metaComment.priority,
              impact: metaComment.impact,
              effort: metaComment.effort,
              confidence: metaComment.confidence,
              why_now: metaComment.why_now,
              recommended_change: metaComment.recommended_change,
              verification_step: metaComment.verification_step,
              status: metaComment.status,
              assignee: metaComment.assignee,
              due_at: metaComment.due_at,
              rank_score: metaComment.rank_score,
              start_offset: metaComment.start_offset,
              end_offset: metaComment.end_offset,
              order_index: metaComment.order_index,
              is_unsynthesized: metaComment.is_unsynthesized,
              sources: metaComment.sources.map((source) => ({
                comment_id: source.comment_id,
                reviewer_name: source.reviewer_name,
                reviewer_id: source.reviewer_id,
                original_comment_text: source.original_comment_text
              }))
            }))
          }
        : null
    };
  }

  async function resolveMetaReviewForExport(
    versionId: number,
    reviewJobId?: number | null
  ): Promise<MetaReviewRunRead | null> {
    if (
      metaReviewRun &&
      metaReviewRun.document_version_id === versionId &&
      (reviewJobId ?? null) === (metaReviewRun.review_job_id ?? null)
    ) {
      return metaReviewRun;
    }

    const scopedQuery = reviewJobId
      ? `/meta-reviews/latest?document_version_id=${versionId}&review_job_id=${reviewJobId}`
      : `/meta-reviews/latest?document_version_id=${versionId}`;
    try {
      return await apiFetch<MetaReviewRunRead>(scopedQuery);
    } catch (error) {
      const message = normalizeError(error).toLowerCase();
      const missing = message.includes('404') || message.includes('not found');
      if (!missing) {
        throw error;
      }
      if (!reviewJobId) {
        return null;
      }
    }

    try {
      return await apiFetch<MetaReviewRunRead>(`/meta-reviews/latest?document_version_id=${versionId}`);
    } catch (error) {
      const message = normalizeError(error).toLowerCase();
      if (message.includes('404') || message.includes('not found')) {
        return null;
      }
      throw error;
    }
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

    let metaRunForBundle: MetaReviewRunRead | null = null;
    try {
      metaRunForBundle = await resolveMetaReviewForExport(selectedVersion.id, selectedReviewJobId);
    } catch (error) {
      setErrorMessage(normalizeError(error));
      return;
    }

    const reviewBundle = buildReviewBundleJson(metaRunForBundle);
    if (!reviewBundle) return;

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
    zip.file(`${context.safeTitle}_review_bundle.json`, JSON.stringify(reviewBundle, null, 2));
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
            `${context.safeTitle}_comments.json`,
            `${context.safeTitle}_review_bundle.json`
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

  async function handleImportReviewBundleFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (list.length === 0) return;
    setIsBundleImporting(true);
    setErrorMessage(null);
    try {
      let importedCount = 0;
      let lastImportedDocumentId: number | null = null;
      for (const file of list) {
        const filename = file.name.toLowerCase();
        let payload: unknown = null;
        if (filename.endsWith('.zip')) {
          const data = await file.arrayBuffer();
          const zip = await JSZip.loadAsync(data);
          const bundleEntry =
            Object.values(zip.files).find((entry) => entry.name.endsWith('_review_bundle.json')) ??
            Object.values(zip.files).find((entry) => entry.name.endsWith('_comments.json'));
          if (!bundleEntry) {
            throw new Error(`No importable bundle JSON found in ${file.name}`);
          }
          payload = JSON.parse(await bundleEntry.async('text'));
        } else if (filename.endsWith('.json')) {
          payload = JSON.parse(await file.text());
        } else {
          throw new Error(`Unsupported bundle file: ${file.name}`);
        }

        // Backward compatibility: old comments-only export format.
        if (payload && typeof payload === 'object' && 'comments' in payload && !('document' in payload)) {
          const legacy = payload as {
            document_title?: string;
            version_label?: string;
            comments?: Array<{ excerpt?: string | null; text?: string | null }>;
          };
          const legacyContent = (legacy.comments ?? [])
            .map((comment) => comment.excerpt || comment.text || '')
            .join('\n')
            .trim();
          payload = {
            schema_version: 'odr.review-bundle.v1-legacy',
            document: { title: legacy.document_title ?? `Imported ${Date.now()}` },
            version: {
              version_label: legacy.version_label ?? 'Imported',
              content: legacyContent || 'Imported review bundle'
            },
            comments: Array.isArray(legacy.comments) ? legacy.comments : []
          };
        }

        const result = await apiFetch<{
          document_id: number;
          version_id: number;
          review_job_id: number | null;
          comments_imported: number;
          personas_created: number;
          meta_comments_imported: number;
        }>('/documents/import-bundle', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        importedCount += 1;
        lastImportedDocumentId = result.document_id;
        setSelectedDocumentId(result.document_id);
        await loadVersions(result.document_id);
      }
      if (lastImportedDocumentId) {
        navigateToDocumentContext(lastImportedDocumentId);
      }
      await refreshAll();
      setStatusMessage(`Imported ${importedCount} review bundle${importedCount === 1 ? '' : 's'}.`);
    } catch (error) {
      setErrorMessage(normalizeError(error));
    } finally {
      setIsBundleImporting(false);
    }
  }

  return (
    <main>
      <div className="topbar">
        <Link className="brand brand-link" href="/library">
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
          <button className="ghost-button" type="button" onClick={() => navigatePanel('/admin')}>
            Admin
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

      {!selectedVersion && !showAgents && !showHistory && !showSettings && !showAdmin && (
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
            {connectorPaths.map((item) => {
              const selected =
                commentViewMode === 'meta'
                  ? Boolean(activeMetaCommentId) && item.id.startsWith(`m-${activeMetaCommentId}-`)
                  : activePathId === item.id;
              const dimmed =
                commentViewMode === 'meta'
                  ? Boolean(activeMetaCommentId) && !item.id.startsWith(`m-${activeMetaCommentId}-`)
                  : Boolean(activePathId) && activePathId !== item.id;
              return (
              <path
                key={item.id}
                d={item.path}
                stroke={item.color}
                className={`link-path ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
                strokeWidth={2.4}
                strokeLinecap="round"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
                fill="none"
              />
              );
            })}
          </svg>
          <div className="doc-panel" ref={docPanelRef}>
            <div className="doc-header">
              <div>
                <div className="doc-title">{selectedDocument?.title ?? 'Untitled document'}</div>
                <div className="doc-meta">
                  {visibleComments.length} comments · {enabledPersonas.size} active agents
                  {selectedReviewJob
                    ? ` · ${selectedReviewGeneration ? `v${selectedReviewGeneration.generation} ` : ''}run #${selectedReviewJob.id} ${selectedReviewJob.status} (${selectedReviewJob.provider}/${selectedReviewJob.model})${Number.isInteger(selectedReviewJob.comment_count) ? ` · ${selectedReviewJob.comment_count} comments` : ''}`
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
                {selectedReviewGeneration && (
                  <span className="pill">
                    v{selectedReviewGeneration.generation}
                    {selectedReviewGeneration.isLatest ? ' latest' : ''}
                  </span>
                )}
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

          <aside
            className="feed-panel"
            onMouseLeave={() => {
              if (!focusedCommentId) setHoveredCommentId(null);
              if (!focusedMetaCommentId) setHoveredMetaCommentId(null);
            }}
          >
            <div className="feed-header">
              <div>
                <div className="feed-title">Comments</div>
                <div className="feed-sub">
                  {commentViewMode === 'meta'
                    ? 'Verdict, top attention points, and clean sections.'
                    : 'Anchored reviewer comments for this document version.'}
                </div>
              </div>
              <div className="feed-controls">
                <div className="mode-toggle">
                  <button
                    className={`mode-button ${commentViewMode === 'individual' ? 'active' : ''}`}
                    type="button"
                    onClick={() => {
                      setCommentModeSelectionSource('manual');
                      setCommentViewMode('individual');
                    }}
                  >
                    Individual
                  </button>
                  <button
                    className={`mode-button ${commentViewMode === 'meta' ? 'active' : ''}`}
                    type="button"
                    onClick={() => {
                      setCommentModeSelectionSource('manual');
                      setCommentViewMode('meta');
                    }}
                  >
                    Meta
                  </button>
                </div>
                {reviewGenerationOptions.length > 1 && (
                  <select
                    aria-label="Review generation"
                    className="input compact"
                    value={selectedReviewJobId ?? reviewGenerationOptions[0]?.job.id ?? ''}
                    onChange={(event) => {
                      const nextReviewJobId = Number(event.target.value);
                      if (!Number.isInteger(nextReviewJobId) || nextReviewJobId <= 0) return;
                      void handleSelectReviewGeneration(nextReviewJobId);
                    }}
                  >
                    {reviewGenerationOptions.map((entry) => (
                      <option key={entry.job.id} value={entry.job.id}>
                        {entry.label}
                      </option>
                    ))}
                  </select>
                )}
                {commentViewMode === 'meta' && (
                  <>
                    <select
                      className="input compact"
                      value={metaCategoryFilter}
                      onChange={(event) =>
                        setMetaCategoryFilter(
                          event.target.value as
                            | 'all'
                            | 'structure'
                            | 'clarity'
                            | 'technical'
                            | 'security'
                            | 'accessibility'
                            | 'style'
                        )
                      }
                    >
                      <option value="all">all categories</option>
                      <option value="structure">structure</option>
                      <option value="clarity">clarity</option>
                      <option value="technical">technical</option>
                      <option value="security">security</option>
                      <option value="accessibility">accessibility</option>
                      <option value="style">style</option>
                    </select>
                    <button
                      className="ghost-button"
                      type="button"
                      disabled={isMetaLoading}
                      onClick={() =>
                        void loadOrCreateMetaReview(selectedVersion.id, selectedReviewJobId, true)
                      }
                    >
                      {isMetaLoading ? 'Computing…' : 'Recompute'}
                    </button>
                  </>
                )}
                {commentViewMode === 'individual' && (
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => void handleRefreshCurrentComments()}
                  >
                    Refresh
                  </button>
                )}
              </div>
            </div>
            {commentViewMode === 'meta' &&
              !isMetaLoading &&
              metaViewState === 'ready' &&
              metaSummary && (
                <div className="meta-summary-panel">
                  <div className={`meta-verdict meta-verdict-${metaSummary.verdict}`}>
                    <div className="meta-verdict-icon">
                      {metaSummary.verdict === 'clean'
                        ? '✓'
                        : metaSummary.verdict === 'problems'
                          ? '!'
                          : '•'}
                    </div>
                    <div>
                      <div className="meta-verdict-label">
                        {metaSummary.verdict === 'clean'
                          ? 'Clean'
                          : metaSummary.verdict === 'problems'
                            ? 'Problems'
                            : 'Review needed'}
                      </div>
                      <div className="meta-verdict-copy">
                        {metaSummary.verdict === 'clean'
                          ? 'No significant issues found.'
                          : metaSummary.verdict === 'problems'
                            ? 'Do not approve, send, or ship without fixing these.'
                            : 'A few things are worth your attention.'}
                      </div>
                    </div>
                  </div>
                  {metaSummary.attention_points.length > 0 && (
                    <div className="meta-summary-block">
                      <div className="meta-summary-title">Top attention points</div>
                      <div className="meta-attention-list">
                        {metaSummary.attention_points.map((point) => (
                          <button
                            key={`meta-summary-${point.meta_comment_id}`}
                            type="button"
                            className="meta-attention-item"
                            onClick={() => {
                              setFocusedMetaCommentId(point.meta_comment_id);
                              const target = metaReviewRun?.comments.find(
                                (comment) => comment.id === point.meta_comment_id
                              );
                              const sourceId = target?.sources[0]?.comment_id ?? null;
                              if (sourceId) {
                                focusComment(sourceId);
                              }
                            }}
                          >
                            <span className={`priority-pill ${point.priority}`}>{point.priority}</span>
                            <strong>{point.location}</strong>: {point.reason}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="meta-summary-block">
                    <div className="meta-summary-title">What is fine</div>
                    <div className="meta-clean-copy">{metaSummary.clean_statement}</div>
                    {metaSummary.clean_sections.length > 0 && (
                      <div className="meta-clean-sections">
                        {metaSummary.clean_sections.map((section) => (
                          <span key={section} className="meta-clean-pill">
                            {section}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            <div
              className="feed-list"
              ref={feedListRef}
              onMouseMove={handleFeedPointerMove}
              onMouseLeave={() => {
                setHoveredCommentId(null);
                setHoveredMetaCommentId(null);
              }}
            >
              {commentViewMode === 'individual' && visibleComments.length === 0 && (
                <div className="empty-feed">
                  {hasFilteredOutComments
                    ? 'Comments are available, but all current agent filters are hidden.'
                    : 'Waiting for anchored comments…'}
                  {hasFilteredOutComments && (
                    <div style={{ marginTop: 10 }}>
                      <button className="ghost-button" type="button" onClick={enableAllPersonas}>
                        Enable all agents
                      </button>
                    </div>
                  )}
                </div>
              )}
              {commentViewMode === 'individual' &&
                visibleComments.map((comment, index) => {
                const persona = personaMap.get(comment.persona_id);
                const color = persona
                  ? getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id))
                  : AGENT_COLORS[0];
                const isFailure = comment.text.toLowerCase().startsWith('review failed:');
                const distance =
                  dockCenterIndex >= 0 ? Math.abs(index - dockCenterIndex) : Number.POSITIVE_INFINITY;
                const isFloatingActive =
                  commentViewMode === 'individual' &&
                  activeCommentId === comment.id &&
                  floatingCardStyle !== null;
                let scale = 1;
                if (distance === 0) scale = 1.55;
                else if (distance === 1) scale = 1.2;
                else if (distance === 2) scale = 1.08;
                if (isFloatingActive) scale = 1;
                // Keep the focused card away from the browser edge while preserving in-pane layering.
                const shift = isFloatingActive ? 0 : distance === 0 ? -12 : 0;
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
                    } ${isFloatingActive ? 'ghost-active' : ''}`}
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
                    <div className="comment-text">{formatCommentBody(comment)}</div>
                    {isFailure && selectedReviewJobId && (
                      <button
                        className="ghost-button retry-button"
                        type="button"
                        onClick={async (event) => {
                          event.stopPropagation();
                          try {
                            await apiFetch(`/review-jobs/${selectedReviewJobId}/retry-persona/${comment.persona_id}`, {
                              method: 'POST'
                            });
                            setStatusMessage('Retry queued for failed reviewer.');
                            await loadComments(selectedVersion.id, false, selectedReviewJobId);
                          } catch (error) {
                            setErrorMessage(normalizeError(error));
                          }
                        }}
                      >
                        Retry
                      </button>
                    )}
                    {comment.excerpt && (
                      <details className="comment-source">
                        <summary>Show linked text</summary>
                        <div>{comment.excerpt}</div>
                      </details>
                    )}
                  </div>
                );
              })}
              {commentViewMode === 'meta' && isMetaLoading && (
                <div className="empty-feed">Loading meta directives…</div>
              )}
              {commentViewMode === 'meta' && !isMetaLoading && metaViewState === 'pending' && (
                <div className="empty-feed">Meta directives are still being synthesized…</div>
              )}
              {commentViewMode === 'meta' && !isMetaLoading && metaViewState === 'missing' && (
                <div className="empty-feed">
                  No meta directives available for this run yet. Recompute to synthesize now.
                </div>
              )}
              {commentViewMode === 'meta' && !isMetaLoading && metaViewState === 'error' && (
                <div className="empty-feed">Unable to load meta directives right now.</div>
              )}
              {commentViewMode === 'meta' &&
                !isMetaLoading &&
                metaViewState === 'ready' &&
                filteredMetaComments.length === 0 && (
                  <div className="empty-feed">
                    {(metaReviewRun?.comments.length ?? 0) > 0
                      ? 'No attention points match this category filter.'
                      : 'No attention points were raised.'}
                  </div>
                )}
              {commentViewMode === 'meta' &&
                !isMetaLoading &&
                metaViewState === 'ready' &&
                filteredMetaComments.map((metaComment, index) => {
                  const topSource = metaComment.sources[0];
                  const pseudoColor = colorForPriority(metaComment.priority);
                  const isFloatingMetaActive =
                    commentViewMode === 'meta' &&
                    activeMetaCommentId === metaComment.id &&
                    floatingMetaCardStyle !== null;
                  const distance =
                    metaDockCenterIndex >= 0
                      ? Math.abs(index - metaDockCenterIndex)
                      : Number.POSITIVE_INFINITY;
                  let scale = 1;
                  if (distance === 0) scale = 1.55;
                  else if (distance === 1) scale = 1.2;
                  else if (distance === 2) scale = 1.08;
                  if (isFloatingMetaActive) scale = 1;
                  const shift = isFloatingMetaActive ? 0 : distance === 0 ? -12 : 0;
                  const zIndex = distance === 0 ? 140 : distance === 1 ? 80 : distance === 2 ? 48 : 1;
                  return (
                    <div
                      key={`meta-${metaComment.id}`}
                      ref={(element) => {
                        metaCardRefs.current[metaComment.id] = element;
                      }}
                      data-meta-id={metaComment.id}
                      className={`comment-card meta-card priority-${metaComment.priority} ${
                        activeMetaCommentId === metaComment.id ? 'selected' : ''
                      } ${activeMetaCommentId && activeMetaCommentId !== metaComment.id ? 'dimmed' : ''} ${
                        isFloatingMetaActive ? 'ghost-active' : ''
                      }`}
                      style={
                        {
                          borderLeftColor: pseudoColor,
                          ['--dock-scale' as '--dock-scale']: scale,
                          ['--dock-shift' as '--dock-shift']: `${shift}px`,
                          zIndex
                        } as CSSProperties
                      }
                      onClick={() => {
                        setFocusedMetaCommentId((prev) => (prev === metaComment.id ? null : metaComment.id));
                        if (topSource?.comment_id) {
                          focusComment(topSource.comment_id);
                        }
                      }}
                      onMouseEnter={() => setHoveredMetaCommentId(metaComment.id)}
                      onMouseLeave={() => {
                        if (!focusedMetaCommentId) setHoveredMetaCommentId(null);
                      }}
                    >
                      <div className="comment-head">
                        <div className="comment-agent">
                          <span className="agent-dot" style={{ backgroundColor: pseudoColor }} />
                          Meta Reviewer
                        </div>
                        <span className={`priority-pill ${metaComment.priority}`}>{metaComment.priority}</span>
                      </div>
                      <div className="meta-tags">
                        <span className="meta-pill">
                          {metaSummary?.attention_points.find(
                            (point) => point.meta_comment_id === metaComment.id
                          )?.location ?? `${metaComment.start_offset}-${metaComment.end_offset}`}
                        </span>
                        <span className="meta-pill">{metaComment.category}</span>
                        {!metaReviewRun?.is_synthesized && <span className="meta-pill">fallback</span>}
                      </div>
                      <div className="comment-text">{metaComment.content}</div>
                      <details className="comment-source">
                        <summary>Show sources ({metaComment.sources.length})</summary>
                        <div className="meta-sources">
                          {metaComment.sources.map((source) => {
                            const sourceComment = commentById.get(source.comment_id);
                            const sourceExcerpt = sourceComment?.excerpt?.trim();
                            const isSelectedSource = activeCommentId === source.comment_id;
                            return (
                              <div
                                key={source.id}
                                className={`meta-source-item ${isSelectedSource ? 'selected' : ''}`}
                              >
                                <div className="meta-source-head">
                                  {source.reviewer_name} · #{source.comment_id}
                                </div>
                                <div>{source.original_comment_text}</div>
                                {sourceExcerpt && (
                                  <div className="meta-source-excerpt">Anchor excerpt: “{sourceExcerpt}”</div>
                                )}
                                <button
                                  type="button"
                                  className="ghost-button source-jump-button"
                                  onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    drillDownToSourceComment(source);
                                  }}
                                >
                                  Jump to source #{source.comment_id}
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </details>
                    </div>
                  );
                })}
            </div>
            {commentViewMode === 'individual' &&
              floatingComment &&
              floatingCardStyle &&
              typeof document !== 'undefined' &&
              createPortal(
                <div className="comment-float-layer" aria-hidden="true">
                  <div
                    className="comment-float-card selected"
                    style={
                      {
                        left: `${floatingCardStyle.left}px`,
                        top: `${floatingCardStyle.top}px`,
                        width: `${floatingCardStyle.width}px`,
                        borderLeftColor:
                          personaMap.get(floatingComment.persona_id)
                            ? getThemeForPersona(
                                agentThemes,
                                floatingComment.persona_id,
                                colorForPersona(floatingComment.persona_id)
                              )
                            : AGENT_COLORS[0]
                      } as CSSProperties
                    }
                  >
                    <div className="comment-head">
                      <div className="comment-agent">
                        <span
                          className="agent-dot"
                          style={{
                            backgroundColor:
                              personaMap.get(floatingComment.persona_id)
                                ? getThemeForPersona(
                                    agentThemes,
                                    floatingComment.persona_id,
                                    colorForPersona(floatingComment.persona_id)
                                  )
                                : AGENT_COLORS[0]
                          }}
                        />
                        {personaMap.get(floatingComment.persona_id)?.name ??
                          `Agent ${floatingComment.persona_id}`}
                      </div>
                      <span className="comment-time">
                        {new Date(floatingComment.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="comment-text">{formatCommentBody(floatingComment)}</div>
                    {floatingComment.excerpt && (
                      <div className="comment-source-preview">{floatingComment.excerpt}</div>
                    )}
                  </div>
                </div>,
                document.body
              )}
            {commentViewMode === 'meta' &&
              floatingMetaComment &&
              floatingMetaCardStyle &&
              typeof document !== 'undefined' &&
              createPortal(
                <div className="comment-float-layer" aria-hidden="true">
                  <div
                    className="comment-float-card selected"
                    style={
                      {
                        left: `${floatingMetaCardStyle.left}px`,
                        top: `${floatingMetaCardStyle.top}px`,
                        width: `${floatingMetaCardStyle.width}px`,
                        borderLeftColor: colorForPriority(floatingMetaComment.priority)
                      } as CSSProperties
                    }
                  >
                    <div className="comment-head">
                      <div className="comment-agent">
                        <span
                          className="agent-dot"
                          style={{ backgroundColor: colorForPriority(floatingMetaComment.priority) }}
                        />
                        Meta Reviewer
                      </div>
                      <span className={`priority-pill ${floatingMetaComment.priority}`}>
                        {floatingMetaComment.priority}
                      </span>
                    </div>
                    <div className="meta-tags">
                      <span className="meta-pill">{floatingMetaComment.category}</span>
                      <span className="meta-pill">impact {floatingMetaComment.impact}</span>
                      <span className="meta-pill">effort {floatingMetaComment.effort}</span>
                      <span className="meta-pill">
                        conf {(floatingMetaComment.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="meta-pill">score {floatingMetaComment.rank_score.toFixed(2)}</span>
                      <span className="meta-pill">
                        {floatingMetaComment.start_offset}-{floatingMetaComment.end_offset}
                      </span>
                    </div>
                    <div className="comment-text">{floatingMetaComment.content}</div>
                    {floatingMetaComment.sources.length > 0 && (
                      <div className="comment-source-preview">
                        {floatingMetaComment.sources[0].reviewer_name}: {floatingMetaComment.sources[0].original_comment_text}
                      </div>
                    )}
                  </div>
                </div>,
                document.body
              )}
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
                <button
                  className="ghost-button"
                  type="button"
                  disabled={isBundleImporting}
                  onClick={() => importReviewBundleInputRef.current?.click()}
                >
                  {isBundleImporting ? 'Importing…' : 'Import Bundle'}
                </button>
                <input
                  ref={importReviewBundleInputRef}
                  type="file"
                  accept="application/json,.json,application/zip,.zip"
                  multiple
                  hidden
                  onChange={(event) => {
                    if (event.target.files) {
                      void handleImportReviewBundleFiles(event.target.files);
                    }
                    event.target.value = '';
                  }}
                />
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

      {showHistory && (
        <div className="library-overlay">
          <div className="library-shell">
            <div className="library-header">
              <div>
                <div className="library-title">History</div>
                <div className="library-sub">
                  Review runs across your workspace and Git-backed document commits.
                </div>
              </div>
              <div className="library-actions">
                <select
                  className="input compact"
                  value={historyDocumentId ?? ''}
                  onChange={(event) => {
                    const raw = event.target.value;
                    if (!raw) {
                      setHistoryDocumentId(null);
                      return;
                    }
                    const next = Number(raw);
                    setHistoryDocumentId(Number.isFinite(next) ? next : null);
                  }}
                >
                  <option value="">No document selected</option>
                  {libraryEntries.map((entry) => (
                    <option key={`history-doc-${entry.id}`} value={entry.id}>
                      {entry.title}
                    </option>
                  ))}
                </select>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => void refreshHistoryPanel(historyDocumentId)}
                  disabled={isHistoryLoading}
                >
                  {isHistoryLoading ? 'Refreshing…' : 'Refresh'}
                </button>
                {historyDocumentId && (
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => router.push(`/?doc=${historyDocumentId}`)}
                  >
                    Open Document
                  </button>
                )}
              </div>
            </div>

            <div className="admin-grid">
              <section className="admin-card wide">
                <div className="drawer-title">Review Runs</div>
                <div className="history-list">
                  {historyJobs.length === 0 && (
                    <div className="subtle">No review runs yet.</div>
                  )}
                  {historyJobs.map((job) => (
                    <div key={`history-job-${job.id}`} className="history-item">
                      <div>
                        <div className="history-msg">
                          #{job.id} {job.status} · version {job.document_version_id}
                        </div>
                        <div className="history-time">
                          {new Date(job.created_at).toLocaleString()}
                          {job.completed_at
                            ? ` · completed ${new Date(job.completed_at).toLocaleString()}`
                            : ''}
                        </div>
                      </div>
                      <span className="pill">
                        {job.provider}/{job.model}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="admin-card wide">
                <div className="drawer-title">Document Commits</div>
                <div className="history-list">
                  {!historyDocumentId && (
                    <div className="subtle">Select a document to view commit history.</div>
                  )}
                  {historyDocumentId && history.length === 0 && (
                    <div className="subtle">No commits yet for this document.</div>
                  )}
                  {history.map((commit) => (
                    <div key={`history-commit-${commit.sha}`} className="history-item">
                      <div>
                        <div className="history-msg">{commit.message}</div>
                        <div className="history-time">
                          {new Date(commit.authored_at).toLocaleString()}
                        </div>
                      </div>
                      <span className="pill">{commit.sha.slice(0, 7)}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        </div>
      )}

      {showAgents && (
        <div className="agents-overlay">
          <div className="agents-shell">
            <div className="agents-header">
              <div>
                <div className="library-title">Agent Studio</div>
                <div className="library-sub">
                  Create and tune reviewer agents. Defaults persist; custom agents are fully editable.
                </div>
              </div>
              <div className="agents-actions">
                <button className="ghost-button" type="button" onClick={() => void handleExportAgents()}>
                  Export
                </button>
                <select
                  className="input compact"
                  value={agentImportConflictPolicy}
                  onChange={(event) =>
                    setAgentImportConflictPolicy(
                      event.target.value as 'skip' | 'overwrite' | 'rename'
                    )
                  }
                >
                  <option value="rename">import: rename conflicts</option>
                  <option value="overwrite">import: overwrite conflicts</option>
                  <option value="skip">import: skip conflicts</option>
                </select>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={() => importAgentsInputRef.current?.click()}
                >
                  Import
                </button>
                <button className="ghost-button" type="button" onClick={handleCreateAgent}>
                  New Agent
                </button>
                <button className="ghost-button" type="button" onClick={() => void handleResetDefaultAgents()}>
                  Reset Defaults
                </button>
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => void handleSaveAgent()}
                  disabled={isAgentSaving}
                >
                  {isAgentSaving ? 'Saving...' : isCreatingAgent ? 'Create Agent' : 'Save Agent'}
                </button>
              </div>
              <input
                ref={importAgentsInputRef}
                type="file"
                accept="application/json,.json"
                style={{ display: 'none' }}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    void handleImportAgentsFromFile(file);
                  }
                  event.target.value = '';
                }}
              />
            </div>

            {pendingAgentImport && (
              <div className="agent-import-preview">
                <div className="drawer-title">Import Preview: {pendingAgentImport.file_name}</div>
                {isAgentImporting && <div className="subtle">Running dry-run preview…</div>}
                {agentImportPreview && (
                  <>
                    <div className="meta-tags">
                      <span className="meta-pill">create {agentImportPreview.created}</span>
                      <span className="meta-pill">update {agentImportPreview.updated}</span>
                      <span className="meta-pill">rename {agentImportPreview.renamed}</span>
                      <span className="meta-pill">skip {agentImportPreview.skipped}</span>
                      {agentImportPreview.errors.length > 0 && (
                        <span className="meta-pill">errors {agentImportPreview.errors.length}</span>
                      )}
                    </div>
                    {agentImportPreview.errors.length > 0 && (
                      <div className="subtle">
                        {agentImportPreview.errors.join(' | ')}
                      </div>
                    )}
                  </>
                )}
                <div className="agents-actions">
                  <button
                    className="primary-button"
                    type="button"
                    disabled={isAgentImporting}
                    onClick={() => void handleApplyAgentImport()}
                  >
                    Apply Import
                  </button>
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => {
                      setPendingAgentImport(null);
                      setAgentImportPreview(null);
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="agents-workspace">
              <aside className="agents-list">
                <div className="agents-list-toolbar">
                  <input
                    className="input compact"
                    placeholder="Search agents"
                    value={agentSearch}
                    onChange={(event) => setAgentSearch(event.target.value)}
                  />
                  <select
                    className="input compact"
                    aria-label="Sort agents"
                    value={agentSortBy}
                    onChange={(event) => setAgentSortBy(event.target.value as AgentListSort)}
                  >
                    <option value="order">sort: order</option>
                    <option value="name">sort: name</option>
                    <option value="status">sort: status</option>
                  </select>
                </div>
                {personas.length === 0 && <div className="subtle">No agents configured.</div>}
                {personas.length > 0 && visibleAgents.length === 0 && (
                  <div className="subtle">No agents match your search.</div>
                )}
                {visibleAgents.map((persona) => {
                  const color = getThemeForPersona(agentThemes, persona.id, colorForPersona(persona.id));
                  const selected = persona.id === editingPersonaId;
                  return (
                    <div
                      key={persona.id}
                      className={`agents-list-item ${selected ? 'active' : ''}`}
                    >
                      <button
                        type="button"
                        className="agents-list-select"
                        onClick={() => {
                          setPersonaForEditing(persona);
                        }}
                      >
                        <div className="agents-list-row">
                          <span className="agent-dot" style={{ backgroundColor: color }} />
                          <span className="agents-list-name">{persona.name}</span>
                          <span className={`status-pill ${persona.is_active ? 'ok' : 'neutral'}`}>
                            {persona.is_active ? 'Active' : 'Disabled'}
                          </span>
                        </div>
                        <div className="agents-list-row tags">
                          {persona.is_default && <span className="meta-pill">Default</span>}
                          {persona.is_system_locked && <span className="meta-pill">Locked</span>}
                          <span className="meta-pill">Order {persona.sort_order}</span>
                        </div>
                      </button>
                      <div className="agents-inline-actions">
                        <button
                          className="ghost-button"
                          type="button"
                          disabled={agentBusyId === persona.id}
                          onClick={() => void handleQuickToggleAgent(persona)}
                        >
                          {agentBusyId === persona.id
                            ? 'Saving...'
                            : persona.is_active
                              ? 'Disable'
                              : 'Enable'}
                        </button>
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={() => handleDuplicateAgent(persona)}
                        >
                          Duplicate
                        </button>
                      </div>
                    </div>
                  );
                })}
              </aside>

              <section className="agents-editor">
                <label className="subtle">Name</label>
                <input
                  className="input"
                  placeholder="Reviewer name"
                  value={agentDraft.name}
                  onChange={(event) => setAgentDraft((prev) => ({ ...prev, name: event.target.value }))}
                />
                <div className="spacer" />
                <label className="subtle">Description</label>
                <textarea
                  className="textarea"
                  rows={2}
                  value={agentDraft.description}
                  onChange={(event) =>
                    setAgentDraft((prev) => ({ ...prev, description: event.target.value }))
                  }
                />
                <div className="spacer" />
                <label className="subtle">System Prompt</label>
                <textarea
                  className="textarea"
                  rows={6}
                  placeholder="How this agent should review and respond..."
                  value={agentDraft.system_prompt}
                  onChange={(event) =>
                    setAgentDraft((prev) => ({ ...prev, system_prompt: event.target.value }))
                  }
                />
                <div className="grid-two">
                  <div>
                    <label className="subtle">Focus Areas (one per line)</label>
                    <textarea
                      className="textarea"
                      rows={5}
                      value={agentDraft.focus_areas_text}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({ ...prev, focus_areas_text: event.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="subtle">Examples (one per line)</label>
                    <textarea
                      className="textarea"
                      rows={5}
                      value={agentDraft.examples_text}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({ ...prev, examples_text: event.target.value }))
                      }
                    />
                  </div>
                </div>
                <div className="spacer" />
                <label className="subtle">Reference Notes</label>
                <textarea
                  className="textarea"
                  rows={4}
                  value={agentDraft.reference_notes}
                  onChange={(event) =>
                    setAgentDraft((prev) => ({ ...prev, reference_notes: event.target.value }))
                  }
                />
                <div className="spacer" />
                <label className="subtle">Tone</label>
                <input
                  className="input"
                  value={agentDraft.tone}
                  onChange={(event) => setAgentDraft((prev) => ({ ...prev, tone: event.target.value }))}
                />
                <div className="grid-three">
                  <div>
                    <label className="subtle">Output Format</label>
                    <input
                      className="input"
                      value={agentDraft.output_format}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({ ...prev, output_format: event.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="subtle">Max Bullets</label>
                    <input
                      className="input"
                      type="number"
                      min={1}
                      max={20}
                      value={agentDraft.max_bullets}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({
                          ...prev,
                          max_bullets: Math.max(1, Math.min(20, Number(event.target.value) || 1))
                        }))
                      }
                    />
                  </div>
                  <div>
                    <label className="subtle">Sort Order</label>
                    <input
                      className="input"
                      type="number"
                      min={0}
                      value={agentDraft.sort_order}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({
                          ...prev,
                          sort_order: Math.max(0, Number(event.target.value) || 0)
                        }))
                      }
                    />
                  </div>
                </div>
                <div className="grid-three toggles">
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={agentDraft.require_quote_excerpt}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({
                          ...prev,
                          require_quote_excerpt: event.target.checked
                        }))
                      }
                    />
                    Require quote
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={agentDraft.require_actionable}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({
                          ...prev,
                          require_actionable: event.target.checked
                        }))
                      }
                    />
                    Require actionable
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={agentDraft.include_severity}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({ ...prev, include_severity: event.target.checked }))
                      }
                    />
                    Include severity
                  </label>
                </div>
                <div className="grid-three toggles">
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={agentDraft.is_active}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({ ...prev, is_active: event.target.checked }))
                      }
                    />
                    Agent active
                  </label>
                  <label className="toggle-row">
                    <span>Theme</span>
                    <input
                      className="agent-color"
                      type="color"
                      value={agentDraft.color_theme}
                      onChange={(event) =>
                        setAgentDraft((prev) => ({ ...prev, color_theme: event.target.value }))
                      }
                    />
                  </label>
                </div>
                {editingPersona && !editingPersona.is_system_locked && (
                  <div className="agents-danger">
                    <button
                      className="ghost-button danger-button"
                      type="button"
                      disabled={agentBusyId === editingPersona.id}
                      onClick={() => void handleDeleteAgent(editingPersona)}
                    >
                      {agentBusyId === editingPersona.id ? 'Deleting...' : 'Delete Agent'}
                    </button>
                  </div>
                )}
                {editingPersona && editingPersona.is_default && editingPersona.is_system_locked && (
                  <div className="agents-danger">
                    <button
                      className="ghost-button"
                      type="button"
                      disabled={agentBusyId === editingPersona.id}
                      onClick={() => void handleRevertDefaultAgent(editingPersona)}
                    >
                      {agentBusyId === editingPersona.id ? 'Reverting...' : 'Revert to Default'}
                    </button>
                  </div>
                )}
              </section>
            </div>
          </div>
        </div>
      )}

      {showAdmin && (
        <div className="admin-overlay">
          <div className="admin-shell">
            <div className="admin-header">
              <div>
                <div className="library-title">Administrator</div>
                <div className="library-sub">
                  Repository visibility, user access control, document permissions, and review operations.
                </div>
              </div>
              <button className="ghost-button" type="button" onClick={() => void refreshAdminData()}>
                Refresh
              </button>
            </div>

            <div className="admin-grid">
              <section className="admin-card">
                <div className="drawer-title">Repository</div>
                <div className="admin-kv">Enabled: {adminOverview?.repository.enabled ? 'Yes' : 'No'}</div>
                <div className="admin-kv">Root: {adminOverview?.repository.root ?? '—'}</div>
                <div className="admin-kv">Tenant Repo Path: {adminOverview?.repository.tenant_root ?? '—'}</div>
                <div className="admin-kv">
                  Repositories: {adminOverview?.repository.repository_count ?? 0}
                </div>
              </section>

              <section className="admin-card">
                <div className="drawer-title">Summary</div>
                <div className="admin-stats">
                  <div className="stat">
                    <div className="stat-label">Users</div>
                    <div className="stat-value">{adminOverview?.users.total ?? 0}</div>
                  </div>
                  <div className="stat">
                    <div className="stat-label">Admins</div>
                    <div className="stat-value">{adminOverview?.users.admins ?? 0}</div>
                  </div>
                  <div className="stat">
                    <div className="stat-label">Documents</div>
                    <div className="stat-value">{adminOverview?.documents.total ?? 0}</div>
                  </div>
                  <div className="stat">
                    <div className="stat-label">In Progress Jobs</div>
                    <div className="stat-value">{adminOverview?.jobs.in_progress ?? 0}</div>
                  </div>
                </div>
              </section>

              <section className="admin-card wide">
                <div className="drawer-title">Work In Progress</div>
                <div className="history-list">
                  {(adminOverview?.in_progress_jobs ?? []).length === 0 && (
                    <div className="subtle">No jobs currently running.</div>
                  )}
                  {(adminOverview?.in_progress_jobs ?? []).map((job) => (
                    <div key={job.id} className="history-item">
                      <div>
                        <div className="history-msg">
                          #{job.id} {job.status} · {job.document_title}
                        </div>
                        <div className="history-time">
                          {new Date(job.created_at).toLocaleString()} · {job.provider}/{job.model}
                        </div>
                      </div>
                      <span className="pill">{job.trigger}</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="admin-card wide">
                <div className="drawer-title">Historical Jobs</div>
                <div className="history-list">
                  {(adminOverview?.recent_jobs ?? []).length === 0 && (
                    <div className="subtle">No jobs yet.</div>
                  )}
                  {(adminOverview?.recent_jobs ?? []).slice(0, 20).map((job) => (
                    <div key={job.id} className="history-item">
                      <div>
                        <div className="history-msg">
                          #{job.id} {job.status} · {job.document_title}
                        </div>
                        <div className="history-time">
                          {new Date(job.created_at).toLocaleString()}
                          {job.completed_at ? ` · completed ${new Date(job.completed_at).toLocaleString()}` : ''}
                        </div>
                      </div>
                      <span className="pill">
                        {job.provider}/{job.model}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="admin-card">
                <div className="drawer-title">Users</div>
                <div className="admin-user-create">
                  <input
                    className="input"
                    placeholder="Name"
                    value={newAdminUser.name}
                    onChange={(event) =>
                      setNewAdminUser((prev) => ({ ...prev, name: event.target.value }))
                    }
                  />
                  <input
                    className="input"
                    placeholder="Email"
                    value={newAdminUser.email}
                    onChange={(event) =>
                      setNewAdminUser((prev) => ({ ...prev, email: event.target.value }))
                    }
                  />
                  <select
                    className="input"
                    value={newAdminUser.role}
                    onChange={(event) =>
                      setNewAdminUser((prev) => ({
                        ...prev,
                        role: event.target.value as 'admin' | 'default'
                      }))
                    }
                  >
                    <option value="default">Default</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button className="primary-button" type="button" onClick={() => void handleCreateAdminUser()}>
                    Add User
                  </button>
                </div>
                <div className="history-list">
                  {adminUsers.map((user) => (
                    <div key={user.id} className="history-item">
                      <div>
                        <div className="history-msg">
                          {user.name} · {user.email}
                        </div>
                        <div className="history-time">Created {new Date(user.created_at).toLocaleString()}</div>
                      </div>
                      <div className="admin-user-actions">
                        <select
                          className="input compact"
                          value={user.role}
                          onChange={(event) =>
                            void handleUpdateAdminUser(user.id, {
                              role: event.target.value as 'admin' | 'default'
                            })
                          }
                        >
                          <option value="default">default</option>
                          <option value="admin">admin</option>
                        </select>
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={() =>
                            void handleUpdateAdminUser(user.id, {
                              is_active: !user.is_active
                            })
                          }
                        >
                          {user.is_active ? 'Disable' : 'Enable'}
                        </button>
                        <button
                          className="ghost-button danger-button"
                          type="button"
                          onClick={() => void handleDeleteAdminUser(user.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="admin-card">
                <div className="drawer-title">Document Permissions</div>
                <select
                  className="input"
                  value={selectedPermissionDocumentId ?? ''}
                  onChange={(event) => {
                    const rawValue = event.target.value;
                    if (!rawValue) {
                      setSelectedPermissionDocumentId(null);
                      return;
                    }
                    const value = Number(rawValue);
                    setSelectedPermissionDocumentId(Number.isFinite(value) ? value : null);
                  }}
                >
                  <option value="">Select document</option>
                  {libraryEntries.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.title}
                    </option>
                  ))}
                </select>
                <div className="spacer" />
                <div className="admin-user-create">
                  <select
                    className="input"
                    value={newPermission.user_id}
                    onChange={(event) =>
                      setNewPermission((prev) => ({
                        ...prev,
                        user_id: Number(event.target.value)
                      }))
                    }
                  >
                    <option value={0}>Select user</option>
                    {adminUsers.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.name} ({user.email})
                      </option>
                    ))}
                  </select>
                  <select
                    className="input"
                    value={newPermission.permission_level}
                    onChange={(event) =>
                      setNewPermission((prev) => ({
                        ...prev,
                        permission_level: event.target.value as 'owner' | 'editor' | 'viewer'
                      }))
                    }
                  >
                    <option value="viewer">viewer</option>
                    <option value="editor">editor</option>
                    <option value="owner">owner</option>
                  </select>
                  <button className="primary-button" type="button" onClick={() => void handleCreatePermission()}>
                    Grant/Update
                  </button>
                </div>
                <div className="history-list">
                  {visibleAdminPermissions.map((perm) => (
                    <div key={perm.id} className="history-item">
                      <div>
                        <div className="history-msg">
                          {perm.user_name} · {perm.user_email}
                        </div>
                        <div className="history-time">Added {new Date(perm.created_at).toLocaleString()}</div>
                      </div>
                      <div className="admin-user-actions">
                        <select
                          className="input compact"
                          value={perm.permission_level}
                          onChange={(event) =>
                            void handleUpdatePermission(
                              perm.id,
                              event.target.value as 'owner' | 'editor' | 'viewer'
                            )
                          }
                        >
                          <option value="viewer">viewer</option>
                          <option value="editor">editor</option>
                          <option value="owner">owner</option>
                        </select>
                        <button
                          className="ghost-button danger-button"
                          type="button"
                          onClick={() => void handleDeletePermission(perm.id)}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="admin-card wide">
                <div className="drawer-title">Permission Matrix</div>
                {adminUsers.length === 0 || libraryEntries.length === 0 ? (
                  <div className="subtle">Add users and documents to view matrix.</div>
                ) : (
                  <div className="admin-matrix-wrap">
                    <table className="admin-matrix">
                      <thead>
                        <tr>
                          <th>User</th>
                          {libraryEntries.slice(0, 8).map((entry) => (
                            <th key={`head-${entry.id}`}>{entry.title}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {adminUsers.map((user) => (
                          <tr key={`row-${user.id}`}>
                            <td>{user.name}</td>
                            {libraryEntries.slice(0, 8).map((entry) => {
                              const perm = adminPermissions.find(
                                (item) => item.user_id === user.id && item.document_id === entry.id
                              );
                              return (
                                <td key={`cell-${user.id}-${entry.id}`}>
                                  <span className="meta-pill">{perm?.permission_level ?? '—'}</span>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="admin-card wide">
                <div className="drawer-title">Recent Admin Actions</div>
                <div className="history-list">
                  {(adminOverview?.recent_actions ?? []).length === 0 && (
                    <div className="subtle">No admin actions logged yet.</div>
                  )}
                  {(adminOverview?.recent_actions ?? []).map((action) => (
                    <div key={action.id} className="history-item">
                      <div>
                        <div className="history-msg">
                          {action.action} · {action.target_type}
                          {action.target_id ? ` #${action.target_id}` : ''}
                        </div>
                        <div className="history-time">
                          {action.actor_email ?? 'unknown'} ·{' '}
                          {new Date(action.created_at).toLocaleString()}
                        </div>
                      </div>
                      <span className="pill">{action.details ?? ''}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        </div>
      )}

      {showSettings && (
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
      )}

    </main>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <HomePageContent />
    </Suspense>
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

function colorForPriority(priority: 'critical' | 'high' | 'medium' | 'low' | string) {
  if (priority === 'critical') return '#b7482f';
  if (priority === 'high') return '#c57a1b';
  if (priority === 'medium') return '#2d6eea';
  return '#1d8a7a';
}

function isMetaSynthesisPendingStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const normalized = status.trim().toLowerCase();
  return (
    normalized === 'queued' ||
    normalized === 'running' ||
    normalized === 'pending' ||
    normalized === 'in_progress' ||
    normalized === 'processing'
  );
}

function isMetaSynthesisFailedStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  const normalized = status.trim().toLowerCase();
  return normalized === 'failed' || normalized === 'error';
}

function normalizeGenerationIndex(value: number | null | undefined): number | null {
  if (!Number.isInteger(value) || Number(value) <= 0) return null;
  return Number(value);
}

function pickLatestReviewGenerationJob(jobs: ReviewJobRead[]): ReviewJobRead | null {
  if (jobs.length === 0) return null;

  const flaggedLatest = jobs
    .filter((job) => job.is_latest_for_version === true)
    .sort((a, b) => {
      const aGeneration = normalizeGenerationIndex(a.generation_index) ?? 0;
      const bGeneration = normalizeGenerationIndex(b.generation_index) ?? 0;
      if (aGeneration !== bGeneration) return bGeneration - aGeneration;
      return b.id - a.id;
    })[0];
  if (flaggedLatest) return flaggedLatest;

  const highestGeneration = jobs
    .slice()
    .sort((a, b) => {
      const aGeneration = normalizeGenerationIndex(a.generation_index) ?? 0;
      const bGeneration = normalizeGenerationIndex(b.generation_index) ?? 0;
      if (aGeneration !== bGeneration) return bGeneration - aGeneration;
      return b.id - a.id;
    })[0];
  if ((normalizeGenerationIndex(highestGeneration?.generation_index) ?? 0) > 0) {
    return highestGeneration ?? null;
  }

  return jobs
    .slice()
    .sort((a, b) => b.id - a.id)[0] ?? null;
}

function metaStatusPollDelayForAttempt(attempt: number): number {
  const normalizedAttempt = Math.max(1, attempt);
  return Math.min(40 * 2 ** (normalizedAttempt - 1), 320);
}

function parseCommentViewModeParam(value: string | null): 'individual' | 'meta' | null {
  if (!value) return null;
  const normalized = value.trim().toLowerCase();
  if (normalized === 'individual' || normalized === 'meta') {
    return normalized;
  }
  return null;
}

function parsePositiveIntParam(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
}

function buildCommentSignature(comments: CommentRead[]): string {
  if (comments.length === 0) return '0';
  return comments
    .map(
      (comment) =>
        `${comment.id}|${comment.review_job_id}|${comment.start_offset}|${comment.end_offset}|${comment.created_at}|${comment.text}`
    )
    .join('||');
}

function formatCommentBody(comment: CommentRead): string {
  const raw = (comment.text || '').trim();
  if (!raw) return '';
  if (!comment.excerpt) return raw;

  const excerpt = comment.excerpt.trim();
  if (!excerpt) return raw;

  // Hide inline duplicated source text from feedback cards while keeping it discoverable via details.
  const withoutExactExcerpt = raw
    .replace(excerpt, '')
    .replace(`"${excerpt}"`, '')
    .replace(`'${excerpt}'`, '')
    .trim();
  const normalizedExcerpt = excerpt.replace(/^["'`]+|["'`]+$/g, '').trim();
  const withoutNormalizedExcerpt =
    withoutExactExcerpt === raw
      ? raw.replace(normalizedExcerpt, '').trim()
      : withoutExactExcerpt;

  const cleanedLines = withoutNormalizedExcerpt
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => {
      const compact = line
        .replace(/^[-*]\s*/, '')
        .replace(/^(quote|quoted text|excerpt|source|text|snippet)\s*:\s*/i, '')
        .replace(/^["'`]+|["'`]+$/g, '')
        .trim();
      if (!compact) return false;
      return compact.toLowerCase() !== normalizedExcerpt.toLowerCase();
    });

  const cleaned = cleanedLines
    .join('\n')
    .replace(/^(quote|quoted text|excerpt|source|text|snippet)\s*:\s*/i, '')
    .replace(/^\-\s*(quote|quoted text|excerpt|source|text|snippet)\s*:\s*/i, '')
    .replace(/^[-:;,\s]+/, '')
    .trim();

  return cleaned || raw;
}

function splitLines(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function createEmptyAgentDraft(): AgentDraft {
  return {
    name: '',
    description: '',
    system_prompt: '',
    focus_areas_text: '',
    tone: '',
    reference_notes: '',
    examples_text: '',
    output_format: 'bullet_list',
    max_bullets: 4,
    require_quote_excerpt: true,
    require_actionable: true,
    include_severity: false,
    sort_order: 100,
    color_theme: '#2d6eea',
    is_active: true,
    group_id: null
  };
}

function createDraftFromPersona(persona: PersonaRead): AgentDraft {
  return {
    name: persona.name,
    description: persona.description ?? '',
    system_prompt: persona.system_prompt,
    focus_areas_text: persona.focus_areas.join('\n'),
    tone: persona.tone ?? '',
    reference_notes: persona.reference_notes ?? '',
    examples_text: persona.examples.join('\n'),
    output_format: persona.output_requirements.format,
    max_bullets: persona.output_requirements.max_bullets,
    require_quote_excerpt: persona.output_requirements.require_quote_excerpt,
    require_actionable: persona.output_requirements.require_actionable,
    include_severity: persona.output_requirements.include_severity,
    sort_order: persona.sort_order,
    color_theme: persona.color_theme ?? colorForPersona(persona.id),
    is_active: persona.is_active,
    group_id: persona.group_id
  };
}

function buildPersonaPayload(draft: AgentDraft) {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    system_prompt: draft.system_prompt.trim(),
    focus_areas: splitLines(draft.focus_areas_text),
    tone: draft.tone.trim() || null,
    reference_notes: draft.reference_notes.trim() || null,
    output_requirements: {
      format: draft.output_format.trim() || 'bullet_list',
      max_bullets: Math.max(1, Math.min(20, draft.max_bullets)),
      require_quote_excerpt: draft.require_quote_excerpt,
      require_actionable: draft.require_actionable,
      include_severity: draft.include_severity
    },
    examples: splitLines(draft.examples_text),
    sort_order: Math.max(0, draft.sort_order),
    color_theme: draft.color_theme,
    group_id: draft.group_id,
    is_active: draft.is_active
  };
}
