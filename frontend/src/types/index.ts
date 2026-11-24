export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  channel_profile_id?: string | null;
}

export interface CreateProjectPayload {
  name: string;
  description?: string;
  channel_profile_id?: string | null;
}

export interface BackendHealth {
  status: string;
  app: string;
  version: string;
}

export type StageId = 'idea' | 'script' | 'voice' | 'scenes' | 'edit' | 'export';

export interface StageNode {
  id: StageId;
  label: string;
  status: 'completed' | 'in_progress' | 'pending';
  icon: string;
}

/** Rich execution statuses reported by the workflow engine. */
export type StageRunStatus =
  | 'pending'
  | 'queued'
  | 'running'
  | 'in_progress'
  | 'awaiting_approval'
  | 'completed'
  | 'failed'
  | 'error'
  | 'cancelled'
  | 'skipped';

/** How each node may be executed. Independent of its current status. */
export type StageExecutionMode = 'auto' | 'manual' | 'approval' | 'off';

export interface StageRuntimeState {
  status: StageRunStatus;
  mode?: StageExecutionMode;
  /** Optional caller-supplied footer; falls back to the execution mode label. */
  footer?: string;
  /** Only shown by the card when the mapped visual status is "error". */
  errorMessage?: string;
}
