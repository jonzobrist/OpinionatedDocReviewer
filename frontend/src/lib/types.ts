export type DocumentRead = {
  id: number;
  tenant_id: string;
  title: string;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
};

export type DocumentLibraryEntry = {
  id: number;
  tenant_id: string;
  title: string;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  latest_version_id: number | null;
  latest_version_label: string | null;
  latest_version_created_at: string | null;
  latest_review_job_id: number | null;
  latest_review_status: string | null;
  latest_review_created_at: string | null;
  latest_review_completed_at: string | null;
  needs_review: boolean;
};

export type DocumentVersionRead = {
  id: number;
  tenant_id: string;
  document_id: number;
  version_label: string;
  content: string;
  created_at: string;
};

export type DocumentCommitRead = {
  sha: string;
  message: string;
  authored_at: string;
};

export type SystemStatus = {
  redis: { ok: boolean; error: string | null };
  llm?: { provider: string; ok: boolean; error: string | null; model?: string | null };
  openai: { ok: boolean };
  review_queue: string;
  doc_repo_enabled: boolean;
};

export type SystemConfigRead = {
  llm_provider: 'openai' | 'bedrock';
  openai_model: string;
  openai_max_tokens: number;
  openai_temperature: number;
  openai_timeout_seconds: number;
  bedrock_model_id: string;
  bedrock_region: string;
  review_inline: boolean;
  redis_url: string;
  review_queue_name: string;
  doc_repo_enabled: boolean;
  doc_repo_root: string;
  cors_allow_origins: string;
  cors_allow_origin_regex: string | null;
  cors_allow_credentials: boolean;
  cors_allow_methods: string;
  cors_allow_headers: string;
  cors_max_age: number;
  openai_api_key_set: boolean;
  bedrock_access_key_set: boolean;
  bedrock_secret_key_set: boolean;
  bedrock_session_token_set: boolean;
};

export type PersonaRead = {
  id: number;
  tenant_id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  focus_areas: string[];
  tone: string | null;
  reference_notes: string | null;
  output_requirements: {
    format: string;
    max_bullets: number;
    require_quote_excerpt: boolean;
    require_actionable: boolean;
    include_severity: boolean;
  };
  examples: string[];
  is_default: boolean;
  is_system_locked: boolean;
  sort_order: number;
  color_theme: string | null;
  group_id: number | null;
  is_active: boolean;
  created_at: string;
};

export type PersonaGroupRead = {
  id: number;
  tenant_id: string;
  name: string;
  description: string | null;
  created_at: string;
};

export type CommentRead = {
  id: number;
  tenant_id: string;
  persona_id: number;
  document_version_id: number;
  review_job_id: number | null;
  text: string;
  start_offset: number;
  end_offset: number;
  excerpt: string | null;
  output_metadata?: Record<string, unknown> | null;
  created_at: string;
};

export type ReviewJobRead = {
  id: number;
  tenant_id: string;
  document_version_id: number;
  status: string;
  trigger: string;
  provider: string;
  model: string;
  completed_at: string | null;
  created_at: string;
};

export type AdminUserRead = {
  id: number;
  tenant_id: string;
  name: string;
  email: string;
  role: 'admin' | 'default';
  is_active: boolean;
  created_at: string;
};

export type DocumentPermissionRead = {
  id: number;
  tenant_id: string;
  document_id: number;
  user_id: number;
  permission_level: 'owner' | 'editor' | 'viewer';
  created_at: string;
  user_name: string;
  user_email: string;
};

export type AdminJobRead = {
  id: number;
  document_version_id: number;
  document_id: number;
  document_title: string;
  status: string;
  trigger: string;
  provider: string;
  model: string;
  created_at: string;
  completed_at: string | null;
};

export type AdminOverview = {
  tenant_id: string;
  repository: {
    enabled: boolean;
    root: string;
    tenant_root: string;
    repository_count: number;
  };
  users: {
    total: number;
    admins: number;
    active: number;
  };
  documents: {
    total: number;
    archived: number;
    active: number;
  };
  jobs: {
    in_progress: number;
    completed: number;
    failed: number;
    recent_total: number;
  };
  in_progress_jobs: AdminJobRead[];
  recent_jobs: AdminJobRead[];
  recent_actions?: Array<{
    id: number;
    actor_user_id: number | null;
    actor_email: string | null;
    action: string;
    target_type: string;
    target_id: number | null;
    details: string | null;
    created_at: string;
  }>;
};

export type MetaCommentSourceRead = {
  id: number;
  comment_id: number;
  reviewer_name: string;
  reviewer_id: number;
  original_comment_text: string;
};

export type MetaCommentRead = {
  id: number;
  content: string;
  category: 'structure' | 'clarity' | 'technical' | 'security' | 'accessibility' | 'style';
  priority: 'critical' | 'high' | 'medium' | 'low';
  start_offset: number;
  end_offset: number;
  order_index: number;
  is_unsynthesized: boolean;
  sources: MetaCommentSourceRead[];
};

export type MetaReviewRunRead = {
  id: number;
  tenant_id: string;
  document_version_id: number;
  review_job_id: number | null;
  input_hash: string;
  status: string;
  is_synthesized: boolean;
  provider: string;
  model: string;
  error_message: string | null;
  created_at: string;
  comments: MetaCommentRead[];
};

export type WorkerSnapshotRead = {
  name: string;
  state: string;
  queues: string[];
  current_job_id: string | null;
  last_heartbeat: string | null;
};

export type WorkerQueueStatsRead = {
  name: string;
  queued: number;
  started: number;
  scheduled: number;
  deferred: number;
  failed: number;
  finished: number;
};

export type WorkerLogEventRead = {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | string;
  source: string;
  message: string;
  detail: string | null;
  review_job_id: number | null;
  rq_job_id: string | null;
  document_title: string | null;
};

export type WorkerMonitorRead = {
  redis_ok: boolean;
  redis_error: string | null;
  queue: WorkerQueueStatsRead;
  workers: WorkerSnapshotRead[];
  logs: WorkerLogEventRead[];
};
