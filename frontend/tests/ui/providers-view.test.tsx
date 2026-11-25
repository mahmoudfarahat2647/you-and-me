import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { BudgetPreflightBanner } from '../../src/components/BudgetPreflightBanner';
import { ProvidersView } from '../../src/components/ProvidersView';
import type {
  ProjectBudgetSummary,
  ProjectSpendLedger,
  ProviderConfigSummary,
  SpendPreflightResult,
} from '../../src/types/providers';

const baseProvider: ProviderConfigSummary = {
  id: 'prov-gemini-1',
  name: 'Gemini Studio',
  provider_type: 'gemini',
  base_url: 'https://generativelanguage.googleapis.com',
  credential_ref: 'provider:prov-gemini-1',
  credential_preview: '••••4321',
  credential_status: 'stored',
  connection_status: 'verified',
  supported_capabilities: ['text_generation', 'research', 'video_generation'],
  verified_models: ['gemini-2.5-flash', 'veo-2.0-generate-001'],
  selected_model: 'gemini-2.5-flash',
  last_error: null,
  last_tested_at: '2026-01-01T00:00:00Z',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const baseBudget: ProjectBudgetSummary = {
  project_id: 'proj-1',
  budget_limit_usd: 10,
  spent_usd: 2.5,
  outstanding_reservations_usd: 1.5,
  remaining_budget_usd: 7.5,
  available_budget_usd: 6.0,
  currency: 'USD',
  configured: true,
  updated_at: '2026-01-01T00:00:00Z',
};

const baseLedger: ProjectSpendLedger = {
  budget: baseBudget,
  reservations: [],
  requests: [
    {
      id: 'ext-1',
      project_id: 'proj-1',
      stage_run_id: 'stage-veo-1',
      request_key: 'req-veo-1',
      provider_id: 'prov-gemini-1',
      operation: 'video_generation',
      model: 'veo-2.0-generate-001',
      external_job_id: 'operations/veo-99',
      status: 'uncertain',
      attempt_number: 1,
      estimated_cost_usd: 1.5,
      reported_cost_usd: null,
      explicitly_approved: false,
      error_message: 'Timeout',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
};

test('ProvidersView configures provider with write-only secret, tests connection, and selects verified model', async () => {
  const user = userEvent.setup();
  const onConfigure = vi.fn().mockResolvedValue(baseProvider);
  const onTest = vi.fn().mockResolvedValue(undefined);
  const onSelectModel = vi.fn().mockResolvedValue(undefined);
  const onDelete = vi.fn().mockResolvedValue(undefined);
  const onUpdateBudget = vi.fn().mockResolvedValue(undefined);
  const onReconcile = vi.fn().mockResolvedValue(undefined);

  render(
    <ProvidersView
      providers={[baseProvider]}
      activeProjectId="proj-1"
      projectBudget={baseBudget}
      spendLedger={baseLedger}
      onConfigureProvider={onConfigure}
      onTestProvider={onTest}
      onSelectModel={onSelectModel}
      onDeleteProvider={onDelete}
      onUpdateProjectBudget={onUpdateBudget}
      onReconcileRequest={onReconcile}
    />
  );

  // Masked credential preview only, never raw key
  const card = screen.getByTestId('provider-card-prov-gemini-1');
  expect(within(card).getByText(/••••4321/)).toBeInTheDocument();
  expect(within(card).getByText('video_generation')).toBeInTheDocument();

  // Submit new provider with write-only key and verify input clears
  const nameInput = screen.getByLabelText('Provider Name');
  const keyInput = screen.getByLabelText('API Key (write-only)') as HTMLInputElement;
  await user.type(nameInput, 'Backup Gemini');
  await user.type(keyInput, 'AIzaSyTestSecret9999');
  await user.click(screen.getByRole('button', { name: /save provider/i }));

  await waitFor(() => {
    expect(onConfigure).toHaveBeenCalledWith({
      name: 'Backup Gemini',
      provider_type: 'gemini',
      base_url: 'https://generativelanguage.googleapis.com',
      api_key: 'AIzaSyTestSecret9999',
    });
  });
  expect(keyInput.value).toBe('');

  await user.click(screen.getByRole('button', { name: /test connection/i }));
  expect(onTest).toHaveBeenCalledWith('prov-gemini-1');

  await user.selectOptions(
    screen.getByLabelText('Model for Gemini Studio'),
    'veo-2.0-generate-001'
  );
  expect(onSelectModel).toHaveBeenCalledWith('prov-gemini-1', 'veo-2.0-generate-001');

  await user.click(screen.getByRole('button', { name: /reconcile/i }));
  expect(onReconcile).toHaveBeenCalledWith('proj-1', 'req-veo-1');
});

test('BudgetPreflightBanner renders pause decision with approve and manual fallback actions', async () => {
  const user = userEvent.setup();
  const onApprove = vi.fn();
  const onManual = vi.fn();

  const pausedPreflight: SpendPreflightResult = {
    allowed: false,
    decision: 'pause_budget_exceeded',
    requires_user_approval: true,
    allows_manual_fallback: true,
    message: 'Estimated cost ($2.00) + reservations ($1.50) exceeds remaining budget ($2.50).',
    project_id: 'proj-1',
    stage_run_id: 'stage-scenes-1',
    request_key: 'req-overrun-1',
    provider_id: 'prov-gemini-1',
    reservation_id: null,
    external_request_id: null,
    external_job_id: null,
    estimated_cost_usd: 2.0,
    reserved_amount_usd: 0,
    outstanding_reservations_usd: 1.5,
    remaining_budget_usd: 2.5,
    budget_limit_usd: 5.0,
    spent_usd: 2.5,
    attempts_used: 0,
    max_retries: 2,
    available_actions: ['approve_overrun', 'switch_to_manual'],
  };

  render(
    <BudgetPreflightBanner
      budget={baseBudget}
      preflight={pausedPreflight}
      onApproveOverrun={onApprove}
      onSwitchToManual={onManual}
    />
  );

  expect(screen.getByTestId('budget-preflight-pause')).toBeInTheDocument();
  expect(screen.getByText('pause_budget_exceeded')).toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: /approve & submit/i }));
  expect(onApprove).toHaveBeenCalledWith(pausedPreflight);

  await user.click(screen.getByRole('button', { name: /switch to manual/i }));
  expect(onManual).toHaveBeenCalledWith(pausedPreflight);
});
