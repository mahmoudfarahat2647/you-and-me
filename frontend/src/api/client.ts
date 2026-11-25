import type {
  AssetType,
  BackendHealth,
  ChannelProfile,
  CreateChannelPayload,
  CreatePresetPayload,
  CreateProjectAssetPayload,
  CreateProjectPayload,
  ExportMp4Options,
  ExportMp4Result,
  Project,
  ProjectAsset,
  ProjectMediaBundle,
  ProjectMediaItem,
  ProjectSettings,
  UpdateChannelPayload,
  UpdateProjectSettingsPayload,
  WorkflowPreset,
} from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface BackendProcessInfo {
  running: boolean;
  port: number;
  error?: string | null;
}

export async function isTauriEnvironment(): Promise<boolean> {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export async function getTauriBackendStatus(): Promise<BackendProcessInfo | null> {
  try {
    if (await isTauriEnvironment()) {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<BackendProcessInfo>('get_backend_status');
    }
  } catch (err) {
    console.warn('Could not query Tauri backend status:', err);
  }
  return null;
}

export async function restartTauriBackend(): Promise<BackendProcessInfo | null> {
  try {
    if (await isTauriEnvironment()) {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<BackendProcessInfo>('restart_backend');
    }
  } catch (err) {
    console.warn('Could not restart Tauri backend:', err);
  }
  return null;
}

async function parseErrorDetail(res: Response, fallback?: string): Promise<string> {
  let errorDetail = res.statusText || fallback || `HTTP ${res.status}`;
  try {
    const data: unknown = await res.json();
    if (typeof data === 'object' && data !== null && 'detail' in data && data.detail !== undefined) {
      if (typeof data.detail === 'string') {
        if (data.detail.trim()) {
          errorDetail = data.detail;
        }
      } else {
        errorDetail = JSON.stringify(data.detail);
      }
    }
  } catch {
    // ignore json parse error
  }
  return errorDetail;
}

async function requestJson<T>(path: string, init?: RequestInit, fallbackError?: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorDetail(res, fallbackError), res.status);
  }
  return (await res.json()) as T;
}

export async function checkBackendHealth(): Promise<BackendHealth> {
  const deadline = Date.now() + 10_000;
  while (true) {
    const remaining = deadline - Date.now();
    if (remaining <= 0) {
      throw new ApiError(
        'Timed out waiting for the local backend to start. Check the backend logs and retry.'
      );
    }
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(Math.min(1000, remaining)),
      });
      if (!res.ok) {
        throw new ApiError(`Backend responded with status ${res.status}: ${res.statusText}`, res.status);
      }
      const data: unknown = await res.json().catch(() => null);
      if (
        typeof data !== 'object' ||
        data === null ||
        !('status' in data) ||
        data.status !== 'ok' ||
        !('app' in data) ||
        typeof data.app !== 'string' ||
        !('version' in data) ||
        typeof data.version !== 'string'
      ) {
        throw new ApiError('Invalid backend health response.');
      }
      return { status: data.status, app: data.app, version: data.version };
    } catch (err: unknown) {
      const retryable =
        (err instanceof ApiError && err.status === 503) ||
        err instanceof TypeError ||
        (err instanceof Error && (err.name === 'TimeoutError' || err.name === 'AbortError'));
      if (!retryable) {
        if (err instanceof ApiError) throw err;
        throw new ApiError(
          err instanceof Error ? err.message : 'Unable to connect to local backend server.'
        );
      }
      const delay = Math.min(250, Math.max(0, deadline - Date.now()));
      if (delay > 0) await new Promise<void>((resolve) => setTimeout(resolve, delay));
    }
  }
}

export async function listProjects(channelProfileId?: string): Promise<Project[]> {
  const query = channelProfileId
    ? `?channel_profile_id=${encodeURIComponent(channelProfileId)}`
    : '';
  return requestJson<Project[]>(`/projects${query}`, { method: 'GET' });
}

export async function getProject(id: string): Promise<Project> {
  return requestJson<Project>(`/projects/${encodeURIComponent(id)}`, { method: 'GET' });
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  return requestJson<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, 'Failed to create project.');
}

export async function listChannels(): Promise<ChannelProfile[]> {
  return requestJson<ChannelProfile[]>('/channels', { method: 'GET' });
}

export async function createChannel(payload: CreateChannelPayload): Promise<ChannelProfile> {
  return requestJson<ChannelProfile>('/channels', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateChannel(
  id: string,
  payload: UpdateChannelPayload
): Promise<ChannelProfile> {
  return requestJson<ChannelProfile>(`/channels/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteChannel(id: string): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`/channels/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export async function listPresets(): Promise<WorkflowPreset[]> {
  return requestJson<WorkflowPreset[]>('/presets', { method: 'GET' });
}

export async function createPreset(payload: CreatePresetPayload): Promise<WorkflowPreset> {
  return requestJson<WorkflowPreset>('/presets', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getProjectSettings(projectId: string): Promise<ProjectSettings> {
  return requestJson<ProjectSettings>(
    `/projects/${encodeURIComponent(projectId)}/settings`,
    { method: 'GET' }
  );
}

export async function updateProjectSettings(
  projectId: string,
  payload: UpdateProjectSettingsPayload
): Promise<ProjectSettings> {
  return requestJson<ProjectSettings>(
    `/projects/${encodeURIComponent(projectId)}/settings`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    }
  );
}

export async function listProjectAssets(
  projectId: string,
  assetType?: AssetType
): Promise<ProjectAsset[]> {
  const query = assetType ? `?asset_type=${encodeURIComponent(assetType)}` : '';
  return requestJson<ProjectAsset[]>(
    `/projects/${encodeURIComponent(projectId)}/assets${query}`,
    { method: 'GET' }
  );
}

export async function createProjectAsset(
  projectId: string,
  payload: CreateProjectAssetPayload
): Promise<ProjectAsset> {
  return requestJson<ProjectAsset>(
    `/projects/${encodeURIComponent(projectId)}/assets`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

export async function deleteProjectAsset(
  projectId: string,
  assetId: string
): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(
    `/projects/${encodeURIComponent(projectId)}/assets/${encodeURIComponent(assetId)}`,
    { method: 'DELETE' }
  );
}

export async function getProjectMedia(projectId: string): Promise<ProjectMediaBundle> {
  return requestJson<ProjectMediaBundle>(
    `/projects/${encodeURIComponent(projectId)}/media`,
    { method: 'GET' },
    'Failed to load project media.'
  );
}

export async function uploadProjectClip(projectId: string, file: File): Promise<ProjectMediaItem> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/clips`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorDetail(res, `Failed to import clip "${file.name}".`), res.status);
  }
  return (await res.json()) as ProjectMediaItem;
}

export async function registerProjectClipPath(
  projectId: string,
  sourcePath: string,
  originalFilename?: string
): Promise<ProjectMediaItem> {
  return requestJson<ProjectMediaItem>(
    `/projects/${encodeURIComponent(projectId)}/media/clips`,
    {
      method: 'POST',
      body: JSON.stringify({
        source_path: sourcePath,
        original_filename: originalFilename,
      }),
    },
    `Failed to register clip "${sourcePath}".`
  );
}

export async function uploadProjectAudio(projectId: string, file: File): Promise<ProjectMediaItem> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/audio`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    throw new ApiError(await parseErrorDetail(res, `Failed to import narration "${file.name}".`), res.status);
  }
  return (await res.json()) as ProjectMediaItem;
}

export async function registerProjectAudioPath(
  projectId: string,
  sourcePath: string,
  originalFilename?: string
): Promise<ProjectMediaItem> {
  return requestJson<ProjectMediaItem>(
    `/projects/${encodeURIComponent(projectId)}/media/audio`,
    {
      method: 'POST',
      body: JSON.stringify({
        source_path: sourcePath,
        original_filename: originalFilename,
      }),
    },
    `Failed to register narration "${sourcePath}".`
  );
}

export async function reorderProjectClips(
  projectId: string,
  clipIds: string[]
): Promise<{ project_id: string; clips: ProjectMediaItem[] }> {
  return requestJson<{ project_id: string; clips: ProjectMediaItem[] }>(
    `/projects/${encodeURIComponent(projectId)}/media/clips/order`,
    {
      method: 'PUT',
      body: JSON.stringify({ clip_ids: clipIds }),
    },
    'Failed to reorder clips.'
  );
}

export async function deleteProjectMediaItem(
  projectId: string,
  itemId: string
): Promise<{ deleted: boolean; item_id: string }> {
  return requestJson<{ deleted: boolean; item_id: string }>(
    `/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(itemId)}`,
    { method: 'DELETE' },
    'Failed to remove media item.'
  );
}

export async function exportProjectMp4(
  projectId: string,
  options?: ExportMp4Options
): Promise<ExportMp4Result> {
  return requestJson<ExportMp4Result>(
    `/projects/${encodeURIComponent(projectId)}/export`,
    {
      method: 'POST',
      body: JSON.stringify(options ?? {}),
    },
    'Failed to export MP4.'
  );
}

export function getOutputVideoUrl(projectId: string, exportId?: string): string {
  const base = `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/output/video`;
  return exportId ? `${base}?v=${encodeURIComponent(exportId)}` : base;
}
