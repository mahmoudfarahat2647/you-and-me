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
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) {
      throw new ApiError(`Backend responded with status ${res.status}: ${res.statusText}`, res.status);
    }
    return await res.json();
  } catch (err: any) {
    if (err.name === 'TimeoutError' || err.name === 'AbortError') {
      throw new ApiError('Connection timed out waiting for backend server.');
    }
    throw new ApiError(err.message || 'Unable to connect to local backend server.');
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
