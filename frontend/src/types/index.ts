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

export type MediaItemKind = 'clip' | 'audio';

export interface ProjectMediaItem {
  id: string;
  project_id: string;
  kind: MediaItemKind;
  file_path: string;
  original_filename: string;
  position: number;
  duration_seconds: number;
  has_video: boolean;
  has_audio: boolean;
  created_at: string;
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  video_codec?: string | null;
  audio_codec?: string | null;
}

export interface ExportMp4Result {
  id: string;
  project_id: string;
  output_path: string;
  duration_seconds: number;
  width: number;
  height: number;
  fps: number;
  has_video: boolean;
  has_audio: boolean;
  file_size_bytes: number;
  clip_ids: string[];
  created_at: string;
  video_codec?: string | null;
  audio_codec?: string | null;
  audio_id?: string | null;
}

export interface ProjectMediaBundle {
  project_id: string;
  clips: ProjectMediaItem[];
  audio: ProjectMediaItem | null;
  latest_export: ExportMp4Result | null;
}

export interface ExportMp4Options {
  target_width?: number;
  target_height?: number;
  target_fps?: number;
}
