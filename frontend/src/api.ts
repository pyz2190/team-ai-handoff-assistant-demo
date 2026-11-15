export type Member = { id: string; display_name: string; role_label: string };
export type Project = {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  role: string;
  members?: Array<{ member_id: string; display_name: string; role: string; active: boolean }>;
  tasks?: Task[];
};
export type Task = {
  id: string;
  project_id: string;
  display_no: string;
  title: string;
  goal: string;
  description: string;
  acceptance_criteria: string;
  progress: string;
  review_state: string;
  request_state: string;
  pending_request_id?: string | null;
  owner_id: string;
  owner_name: string;
  revision: number;
  materials?: Material[];
  drafts?: Draft[];
  confirmed_handoffs?: Confirmed[];
  requests?: RequestSummary[];
};
export type MaterialVersion = {
  id: string;
  version_no: number;
  content?: string | null;
  url?: string | null;
  unread_body: boolean;
  created_at: string;
};
export type Material = {
  id: string;
  display_no: string;
  kind: string;
  title: string;
  source_note: string;
  latest_version_id: string;
  created_at: string;
  versions: MaterialVersion[];
};
export type SectionKey =
  | "completed"
  | "decisions"
  | "verification"
  | "open_issues"
  | "next_steps";
export type Sections = Record<SectionKey, string>;
export type Citation = {
  id?: string;
  section: SectionKey;
  material_version_id: string;
  material_title?: string;
  material_display_no?: string;
  version_no?: number;
  start_line: number;
  end_line: number;
  quote: string;
  source_material_id?: string;
  source_content_hash?: string;
  quote_hash?: string;
  hash_algorithm?: string;
};
export type EvidenceState = "current" | "stale" | "missing" | "mismatch" | "unauthorized";
export type Draft = {
  id: string;
  task_id: string;
  origin: string;
  sections: Sections;
  citations: Citation[];
  revision: number;
  updated_at: string;
};
export type Confirmed = {
  id: string;
  task_id: string;
  version_no: number;
  task_snapshot: { title: string; goal: string; acceptance_criteria: string };
  sections: Sections;
  citations: Citation[];
  evidence_state: EvidenceState;
  confirmed_by_name: string;
  confirmed_at: string;
};
export type TaskEvent = {
  id: string;
  event_ref: string;
  task_id: string;
  seq: number;
  event_type: string;
  status: "proposed" | "started" | "succeeded" | "failed" | "cancelled" | "timed_out" | "not_executed" | "unknown";
  lifecycle: "active" | "superseded" | "withdrawn" | "reopened";
  parent_event_ref?: string | null;
  correlation_id?: string | null;
  source: string;
  actor_name: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  created_at: string;
};
export type RequestSummary = {
  id: string;
  task_id: string;
  confirmed_handoff_id: string;
  sender_name: string;
  recipient_id: string;
  recipient_name: string;
  status: string;
  reason?: string | null;
  revision: number;
  created_at: string;
};
export type RequestDetail = RequestSummary & {
  task: Task;
  confirmed_handoff: Confirmed;
  receipt?: { id: string; recipient_id: string; accepted_at: string } | null;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number
  ) {
    super(message);
  }
}

let currentMemberId = localStorage.getItem("handoff-member") ?? "";
export function setApiMember(memberId: string) {
  currentMemberId = memberId;
  localStorage.setItem("handoff-member", memberId);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (currentMemberId) headers.set("X-Demo-Member-ID", currentMemberId);
  const response = await fetch("/api/v1" + path, { ...init, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = data.error ?? {};
    throw new ApiError(error.message ?? "请求失败", error.code ?? "REQUEST_FAILED", response.status);
  }
  return data as T;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
