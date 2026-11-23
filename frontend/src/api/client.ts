import type { BackendHealth, CreateProjectPayload, Project } from '../types';

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
    let errorDetail = res.statusText;
    try {
      const data = await res.json();
      if (data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new ApiError(errorDetail, res.status);
  }
  return await res.json();
}
