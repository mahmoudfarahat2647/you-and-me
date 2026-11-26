export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  channel_profile_id?: string | null;
  preset_id?: string | null;
}

export interface CreateProjectPayload {
  name: string;
  description?: string;
  channel_profile_id?: string | null;
  preset_id?: string | null;
}

export interface ChannelProfile {
  id: string;
  name: string;
  topic_focus: string;
  language: string;
  default_narrator: string;
  visual_style: string;
  video_format: string;
  budget_limit_usd: number;
  upload_destination: string;
  created_at: string;
  updated_at: string;
}

export interface CreateChannelPayload {
  name: string;
  topic_focus?: string;
  language?: string;
  default_narrator?: string;
  visual_style?: string;
  video_format?: string;
  budget_limit_usd?: number;
  upload_destination?: string;
}

export interface UpdateChannelPayload {
  name?: string;
  topic_focus?: string;
  language?: string;
  default_narrator?: string;
  visual_style?: string;
  video_format?: string;
  budget_limit_usd?: number;
  upload_destination?: string;
}

export type StageParamScalar = string | number | boolean;
export type StageParamMap = Partial<Record<StageId, Record<string, StageParamScalar>>>;

export interface WorkflowPreset {
  id: string;
  name: string;
  description: string;
  default_stage_modes: Partial<Record<StageId, StageExecutionMode>>;
  default_stage_params: StageParamMap;
  is_builtin: boolean;
}

export interface CreatePresetPayload {
  name: string;
  description?: string;
  default_stage_modes?: Partial<Record<StageId, StageExecutionMode>>;
  default_stage_params?: StageParamMap;
}

export interface ProjectSettings {
  project_id: string;
  updated_at: string;
  channel_profile_id?: string | null;
  preset_id?: string | null;
  topic_focus: string;
  language: string;
  narrator: string;
  visual_style: string;
  video_format: string;
  budget_limit_usd: number;
  upload_destination: string;
  stage_modes: Partial<Record<StageId, StageExecutionMode>>;
  stage_params: StageParamMap;
}

export interface UpdateProjectSettingsPayload {
  topic_focus?: string;
  language?: string;
  narrator?: string;
  visual_style?: string;
  video_format?: string;
  budget_limit_usd?: number;
  upload_destination?: string;
  stage_modes?: Partial<Record<StageId, StageExecutionMode>>;
  stage_params?: StageParamMap;
}

export type AssetType = 'script' | 'scene' | 'audio' | 'export';

export interface ProjectAsset {
  id: string;
  project_id: string;
  asset_type: AssetType;
  name: string;
  content: string;
  file_path?: string | null;
  metadata: Record<string, StageParamScalar>;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectAssetPayload {
  asset_type: AssetType;
  name: string;
  content?: string;
  file_path?: string | null;
  metadata?: Record<string, StageParamScalar>;
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
  | 'waiting_manual'
  | 'awaiting_approval'
  | 'completed'
  | 'failed'
  | 'error'
  | 'cancelled'
  | 'canceled'
  | 'skipped'
  | 'stale'
  | 'unknown_outcome';

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

export type WorkflowJobStatus =
  | 'pending'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'canceled'
  | 'needs_reconciliation';

export interface WorkflowArtifact {
  artifact_id: string;
  stage_id: string;
  artifact_type: string;
  uri?: string | null;
  data: Record<string, unknown>;
  schema_version: string;
  compatible: boolean;
  stale: boolean;
  created_at?: string | null;
  content_hash?: string | null;
}

export interface WorkflowSceneItem {
  item_id: string;
  status: StageRunStatus;
  artifact?: WorkflowArtifact | null;
  input_data: Record<string, unknown>;
  error?: string | null;
}

export interface WorkflowStageState {
  stage_id: StageId;
  mode: StageExecutionMode;
  status: StageRunStatus;
  dependencies: string[];
  required: boolean;
  artifact_type: string;
  artifact?: WorkflowArtifact | null;
  items: WorkflowSceneItem[];
  params: Record<string, unknown>;
  external_run_id?: string | null;
  error?: string | null;
  attempt_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
}

export interface WorkflowJob {
  id: string;
  project_id: string;
  status: WorkflowJobStatus;
  stage_order: StageId[];
  stages: WorkflowStageState[];
  created_at: string;
  updated_at: string;
  pause_requested: boolean;
  cancel_requested: boolean;
  completed_at?: string | null;
  error?: string | null;
}

export interface WorkflowLogEntry {
  id: string;
  job_id: string;
  project_id: string;
  stage_id: string;
  level: 'info' | 'warning' | 'error';
  message: string;
  created_at: string;
}

export interface WorkflowStateResponse {
  project_id: string;
  job: WorkflowJob | null;
  logs: WorkflowLogEntry[];
}

export interface ReconcileWorkflowResponse extends WorkflowStateResponse {
  reconciled_job_ids: string[];
  needs_reconciliation_job_ids: string[];
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
