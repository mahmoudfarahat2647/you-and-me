import { ApiError } from './client';
import type {
  ReconcileWorkflowResponse,
  StageExecutionMode,
  StageId,
  WorkflowStateResponse,
} from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

async function parseWorkflowError(res: Response, fallback: string): Promise<string> {
  try {
    const data: unknown = await res.json();
    if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
      if (data.detail.trim()) {
        return data.detail;
      }
    }
  } catch {
    // ignore non-json responses
  }
  return res.statusText || fallback;
}

async function workflowRequest<T>(
  path: string,
  init: RequestInit,
  fallbackError: string
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(await parseWorkflowError(res, fallbackError), res.status);
  }
  return (await res.json()) as T;
}

export async function getProjectWorkflow(projectId: string): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow`,
    { method: 'GET' },
    'Failed to load workflow state.'
  );
}

export async function reconcileProjectWorkflow(
  projectId: string
): Promise<ReconcileWorkflowResponse> {
  return workflowRequest<ReconcileWorkflowResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/reconcile`,
    { method: 'POST' },
    'Failed to reconcile workflow.'
  );
}

export async function runProjectWorkflow(
  projectId: string,
  options?: { stage_modes?: Partial<Record<StageId, StageExecutionMode>>; force_new?: boolean }
): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/run`,
    {
      method: 'POST',
      body: JSON.stringify(options ?? {}),
    },
    'Failed to run workflow.'
  );
}

export async function runWorkflowStage(
  projectId: string,
  stageId: StageId
): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/stages/${encodeURIComponent(stageId)}/run`,
    { method: 'POST' },
    `Failed to run stage "${stageId}".`
  );
}

export async function pauseProjectWorkflow(projectId: string): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/pause`,
    { method: 'POST' },
    'Failed to pause workflow.'
  );
}

export async function cancelProjectWorkflow(projectId: string): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/cancel`,
    { method: 'POST' },
    'Failed to cancel workflow.'
  );
}

export async function resumeProjectWorkflow(projectId: string): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/resume`,
    { method: 'POST' },
    'Failed to resume workflow.'
  );
}

export async function retryWorkflowStage(
  projectId: string,
  stageId: StageId
): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/stages/${encodeURIComponent(stageId)}/retry`,
    { method: 'POST' },
    `Failed to retry stage "${stageId}".`
  );
}

export async function submitManualStageResult(
  projectId: string,
  stageId: StageId,
  payload: { content?: string; uri?: string; data?: Record<string, unknown>; auto_resume?: boolean }
): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/stages/${encodeURIComponent(stageId)}/manual`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    `Failed to submit manual output for "${stageId}".`
  );
}

export async function approveWorkflowStage(
  projectId: string,
  stageId: StageId,
  payload: {
    approved: boolean;
    edited_content?: string;
    edited_data?: Record<string, unknown>;
    reason?: string;
    rerun?: boolean;
    auto_resume?: boolean;
  }
): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/stages/${encodeURIComponent(stageId)}/approve`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
    `Failed to submit review for "${stageId}".`
  );
}

export async function updateWorkflowStageMode(
  projectId: string,
  stageId: StageId,
  mode: StageExecutionMode
): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/stages/${encodeURIComponent(stageId)}/mode`,
    {
      method: 'PUT',
      body: JSON.stringify({ mode }),
    },
    `Failed to update mode for "${stageId}".`
  );
}

export async function updateWorkflowScene(
  projectId: string,
  sceneId: string,
  payload: { prompt?: string; notes?: string; title?: string; reason?: string }
): Promise<WorkflowStateResponse> {
  return workflowRequest<WorkflowStateResponse>(
    `/projects/${encodeURIComponent(projectId)}/workflow/scenes/${encodeURIComponent(sceneId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
    `Failed to update scene "${sceneId}".`
  );
}
