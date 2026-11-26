export type ProviderType = 'gemini' | 'openai_compatible' | 'local_ollama';

export type ProviderCapability =
  | 'text_generation'
  | 'research'
  | 'tts'
  | 'video_generation';

export type ProviderConnectionStatus = 'unverified' | 'verified' | 'failed';

export type CredentialStatus = 'missing' | 'stored' | 'not_required';

export type ExternalJobStatus =
  | 'pending'
  | 'submitted'
  | 'succeeded'
  | 'failed'
  | 'uncertain';

export type ReservationStatus = 'active' | 'settled' | 'released' | 'uncertain';

export interface ProviderConfigSummary {
  id: string;
  name: string;
  provider_type: ProviderType;
  base_url: string;
  credential_ref: string | null;
  credential_preview: string | null;
  credential_status: CredentialStatus;
  connection_status: ProviderConnectionStatus;
  supported_capabilities: ProviderCapability[];
  verified_models: string[];
  selected_model: string | null;
  last_error: string | null;
  last_tested_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConfigureProviderPayload {
  provider_id?: string | null;
  name: string;
  provider_type: ProviderType;
  base_url?: string | null;
  api_key?: string | null;
  selected_model?: string | null;
}

export interface ProviderConnectionTestResult {
  provider_id: string;
  success: boolean;
  connection_status: ProviderConnectionStatus;
  supported_capabilities: ProviderCapability[];
  verified_models: string[];
  selected_model: string | null;
  message: string;
  tested_at: string;
}

export interface ProjectBudgetSummary {
  project_id: string;
  budget_limit_usd: number;
  spent_usd: number;
  outstanding_reservations_usd: number;
  remaining_budget_usd: number;
  available_budget_usd: number;
  currency: string;
  configured: boolean;
  updated_at: string;
}

export interface SpendReservationRecord {
  id: string;
  project_id: string;
  stage_run_id: string;
  request_key: string;
  provider_id: string;
  reserved_usd: number;
  settled_usd: number | null;
  status: ReservationStatus;
  created_at: string;
  updated_at: string;
}

export interface ExternalRequestRecord {
  id: string;
  project_id: string;
  stage_run_id: string;
  request_key: string;
  provider_id: string;
  operation: ProviderCapability;
  model: string | null;
  external_job_id: string | null;
  status: ExternalJobStatus;
  attempt_number: number;
  estimated_cost_usd: number | null;
  reported_cost_usd: number | null;
  explicitly_approved: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSpendLedger {
  budget: ProjectBudgetSummary;
  reservations: SpendReservationRecord[];
  requests: ExternalRequestRecord[];
}

export interface SpendPreflightPayload {
  stage_run_id: string;
  request_key: string;
  provider_id: string;
  operation: ProviderCapability;
  estimated_cost_usd: number | null;
  model?: string | null;
  is_retry?: boolean;
  max_retries?: number;
  explicit_approval?: boolean;
  approved_cost_cap_usd?: number | null;
}

export interface SpendPreflightResult {
  allowed: boolean;
  decision: string;
  requires_user_approval: boolean;
  allows_manual_fallback: boolean;
  message: string;
  project_id: string;
  stage_run_id: string;
  request_key: string;
  provider_id: string;
  reservation_id: string | null;
  external_request_id: string | null;
  external_job_id: string | null;
  estimated_cost_usd: number | null;
  reserved_amount_usd: number;
  outstanding_reservations_usd: number;
  remaining_budget_usd: number;
  budget_limit_usd: number;
  spent_usd: number;
  attempts_used: number;
  max_retries: number;
  available_actions: string[];
}

export interface ApproveSpendPayload {
  stage_run_id?: string;
  provider_id?: string;
  operation?: ProviderCapability;
  estimated_cost_usd?: number | null;
  approved_cost_cap_usd?: number | null;
  model?: string | null;
  is_retry?: boolean;
  max_retries?: number;
}

export interface ReconcileSpendPayload {
  status?: ExternalJobStatus;
  external_job_id?: string | null;
  reported_cost_usd?: number | null;
  error_message?: string | null;
}

export interface ReconcileSpendResult {
  request: ExternalRequestRecord;
  budget: ProjectBudgetSummary;
}
