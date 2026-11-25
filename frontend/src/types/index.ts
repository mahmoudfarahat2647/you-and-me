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
