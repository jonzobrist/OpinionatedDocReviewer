export type DocumentRead = {
  id: number;
  tenant_id: string;
  title: string;
  created_at: string;
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
  openai: { ok: boolean };
  review_queue: string;
  doc_repo_enabled: boolean;
};

export type PersonaRead = {
  id: number;
  tenant_id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  focus_areas: string[];
  tone: string | null;
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
  created_at: string;
};
