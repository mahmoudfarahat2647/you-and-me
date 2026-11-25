import type {
  BackendHealth,
  CreateProjectPayload,
  ExportMp4Options,
  ExportMp4Result,
  Project,
  ProjectMediaBundle,
  ProjectMediaItem,
} from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

async function extractErrorDetail(res: Response, fallback: string): Promise<string> {
  let errorDetail = res.statusText || fallback;
  try {
    const data: unknown = await res.json();
    if (typeof data === 'object' && data !== null && 'detail' in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === 'string' && detail.trim()) {
        errorDetail = detail;
      } else if (detail !== undefined) {
        errorDetail = JSON.stringify(detail);
      }
    }
  } catch {
    // ignore json parse error
  }
  return errorDetail;
}

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

export async function checkBackendHealth(): Promise<BackendHealth> {
  const deadline = Date.now() + 10_000;
  while (true) {
    const remaining = deadline - Date.now();
    if (remaining <= 0) throw new ApiError('Timed out waiting for the local backend to start. Check the backend logs and retry.');
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(Math.min(1000, remaining)),
      });
      if (!res.ok) {
        throw new ApiError(`Backend responded with status ${res.status}: ${res.statusText}`, res.status);
      }
      const data: unknown = await res.json().catch(() => null);
      if (typeof data !== 'object' || data === null || !('status' in data) ||
          data.status !== 'ok' || !('app' in data) || typeof data.app !== 'string' ||
          !('version' in data) || typeof data.version !== 'string') {
        throw new ApiError('Invalid backend health response.');
      }
      return { status: data.status, app: data.app, version: data.version };
    } catch (err: unknown) {
      const retryable = (err instanceof ApiError && err.status === 503) ||
        err instanceof TypeError ||
        (err instanceof Error && (err.name === 'TimeoutError' || err.name === 'AbortError'));
      if (!retryable) {
        if (err instanceof ApiError) throw err;
        throw new ApiError(err instanceof Error ? err.message : 'Unable to connect to local backend server.');
      }
      const delay = Math.min(250, Math.max(0, deadline - Date.now()));
      if (delay > 0) await new Promise<void>((resolve) => setTimeout(resolve, delay));
    }
  }
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE_URL}/projects`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    throw new ApiError(`Failed to fetch projects: ${res.statusText}`, res.status);
  }
  return await res.json();
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${API_BASE_URL}/projects/${id}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    throw new ApiError(`Failed to fetch project ${id}: ${res.statusText}`, res.status);
  }
  return await res.json();
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  const res = await fetch(`${API_BASE_URL}/projects`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, 'Failed to create project.'), res.status);
  }
  return (await res.json()) as Project;
}

export async function getProjectMedia(projectId: string): Promise<ProjectMediaBundle> {
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, 'Failed to load project media.'), res.status);
  }
  return (await res.json()) as ProjectMediaBundle;
}

export async function uploadProjectClip(projectId: string, file: File): Promise<ProjectMediaItem> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/clips`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, `Failed to import clip "${file.name}".`), res.status);
  }
  return (await res.json()) as ProjectMediaItem;
}

export async function registerProjectClipPath(
  projectId: string,
  sourcePath: string,
  originalFilename?: string
): Promise<ProjectMediaItem> {
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/clips`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      source_path: sourcePath,
      original_filename: originalFilename,
    }),
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, `Failed to register clip "${sourcePath}".`), res.status);
  }
  return (await res.json()) as ProjectMediaItem;
}

export async function uploadProjectAudio(projectId: string, file: File): Promise<ProjectMediaItem> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/audio`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, `Failed to import narration "${file.name}".`), res.status);
  }
  return (await res.json()) as ProjectMediaItem;
}

export async function registerProjectAudioPath(
  projectId: string,
  sourcePath: string,
  originalFilename?: string
): Promise<ProjectMediaItem> {
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/audio`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      source_path: sourcePath,
      original_filename: originalFilename,
    }),
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, `Failed to register narration "${sourcePath}".`), res.status);
  }
  return (await res.json()) as ProjectMediaItem;
}

export async function reorderProjectClips(
  projectId: string,
  clipIds: string[]
): Promise<{ project_id: string; clips: ProjectMediaItem[] }> {
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/clips/order`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ clip_ids: clipIds }),
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, 'Failed to reorder clips.'), res.status);
  }
  return (await res.json()) as { project_id: string; clips: ProjectMediaItem[] };
}

export async function deleteProjectMediaItem(
  projectId: string,
  itemId: string
): Promise<{ deleted: boolean; item_id: string }> {
  const res = await fetch(
    `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/media/${encodeURIComponent(itemId)}`,
    {
      method: 'DELETE',
      headers: { Accept: 'application/json' },
    }
  );
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, 'Failed to remove media item.'), res.status);
  }
  return (await res.json()) as { deleted: boolean; item_id: string };
}

export async function exportProjectMp4(
  projectId: string,
  options?: ExportMp4Options
): Promise<ExportMp4Result> {
  const res = await fetch(`${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(options ?? {}),
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorDetail(res, 'Failed to export MP4.'), res.status);
  }
  return (await res.json()) as ExportMp4Result;
}

export function getOutputVideoUrl(projectId: string, exportId?: string): string {
  const base = `${API_BASE_URL}/projects/${encodeURIComponent(projectId)}/output/video`;
  return exportId ? `${base}?v=${encodeURIComponent(exportId)}` : base;
}
