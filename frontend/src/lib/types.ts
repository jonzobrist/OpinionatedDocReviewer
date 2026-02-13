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
