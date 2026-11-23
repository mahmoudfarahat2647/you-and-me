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
