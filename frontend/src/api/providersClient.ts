import { ApiError } from './client';
import type {
  ApproveSpendPayload,
  ConfigureProviderPayload,
  ProjectBudgetSummary,
  ProjectSpendLedger,
  ProviderConfigSummary,
  ProviderConnectionTestResult,
  ReconcileSpendPayload,
  ReconcileSpendResult,
  SpendPreflightPayload,
  SpendPreflightResult,
} from '../types/providers';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

async function requestProviderJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let detail = `HTTP error ${response.status}`;
    try {
      const errorData = (await response.json()) as { detail?: unknown };
      if (typeof errorData.detail === 'string') {
        detail = errorData.detail;
      } else if (errorData.detail !== undefined) {
        detail = JSON.stringify(errorData.detail);
      }
    } catch {
      // Ignore JSON parsing failure on non-JSON error responses
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export async function listProviders(): Promise<ProviderConfigSummary[]> {
  return requestProviderJson<ProviderConfigSummary[]>('/providers');
}

export async function configureProvider(
  payload: ConfigureProviderPayload
): Promise<ProviderConfigSummary> {
  return requestProviderJson<ProviderConfigSummary>('/providers', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function testProviderConnection(
  providerId: string
): Promise<ProviderConnectionTestResult> {
  return requestProviderJson<ProviderConnectionTestResult>(
    `/providers/${encodeURIComponent(providerId)}/test`,
    { method: 'POST' }
  );
}

export async function selectProviderModel(
  providerId: string,
  model: string
): Promise<ProviderConfigSummary> {
  return requestProviderJson<ProviderConfigSummary>(
    `/providers/${encodeURIComponent(providerId)}/model`,
    {
      method: 'PUT',
      body: JSON.stringify({ model }),
    }
  );
}

export async function deleteProvider(providerId: string): Promise<{ deleted: boolean }> {
  return requestProviderJson<{ deleted: boolean }>(
    `/providers/${encodeURIComponent(providerId)}`,
    { method: 'DELETE' }
  );
}

export async function getProjectBudget(projectId: string): Promise<ProjectBudgetSummary> {
  return requestProviderJson<ProjectBudgetSummary>(
    `/projects/${encodeURIComponent(projectId)}/budget`
  );
}

export async function setProjectBudget(
  projectId: string,
  budgetLimitUsd: number
): Promise<ProjectBudgetSummary> {
  return requestProviderJson<ProjectBudgetSummary>(
    `/projects/${encodeURIComponent(projectId)}/budget`,
    {
      method: 'PUT',
      body: JSON.stringify({ budget_limit_usd: budgetLimitUsd }),
    }
  );
}

export async function getProjectSpendLedger(projectId: string): Promise<ProjectSpendLedger> {
  return requestProviderJson<ProjectSpendLedger>(
    `/projects/${encodeURIComponent(projectId)}/spend`
  );
}

export async function evaluateSpendPreflight(
  projectId: string,
  payload: SpendPreflightPayload
): Promise<SpendPreflightResult> {
  return requestProviderJson<SpendPreflightResult>(
    `/projects/${encodeURIComponent(projectId)}/spend/preflight`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

export async function approveSpendRequest(
  projectId: string,
  requestKey: string,
  payload?: ApproveSpendPayload
): Promise<SpendPreflightResult> {
  return requestProviderJson<SpendPreflightResult>(
    `/projects/${encodeURIComponent(projectId)}/spend/${encodeURIComponent(requestKey)}/approve`,
    {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    }
  );
}

export async function reconcileSpendRequest(
  projectId: string,
  requestKey: string,
  payload?: ReconcileSpendPayload
): Promise<ReconcileSpendResult> {
  return requestProviderJson<ReconcileSpendResult>(
    `/projects/${encodeURIComponent(projectId)}/spend/${encodeURIComponent(requestKey)}/reconcile`,
    {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    }
  );
}
