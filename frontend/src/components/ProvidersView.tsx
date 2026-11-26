import React, { useId, useState } from 'react';
import {
  CheckCircle2,
  Cpu,
  KeyRound,
  Plug,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Wallet,
  XCircle,
} from 'lucide-react';
import type {
  ConfigureProviderPayload,
  ProjectBudgetSummary,
  ProjectSpendLedger,
  ProviderConfigSummary,
  ProviderType,
} from '../types/providers';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';

interface ProvidersViewProps {
  providers: ProviderConfigSummary[];
  activeProjectId?: string | null;
  projectBudget?: ProjectBudgetSummary | null;
  spendLedger?: ProjectSpendLedger | null;
  onConfigureProvider: (payload: ConfigureProviderPayload) => Promise<ProviderConfigSummary>;
  onTestProvider: (providerId: string) => Promise<void>;
  onSelectModel: (providerId: string, model: string) => Promise<void>;
  onDeleteProvider: (providerId: string) => Promise<void>;
  onUpdateProjectBudget?: (projectId: string, budgetLimitUsd: number) => Promise<void>;
  onReconcileRequest?: (projectId: string, requestKey: string) => Promise<void>;
}

const DEFAULT_URLS: Record<ProviderType, string> = {
  gemini: 'https://generativelanguage.googleapis.com',
  openai_compatible: 'https://api.openai.com/v1',
  local_ollama: 'http://127.0.0.1:11434',
};

const PROVIDER_LABELS: Record<ProviderType, string> = {
  gemini: 'Google Gemini API',
  openai_compatible: 'OpenAI-Compatible API',
  local_ollama: 'Local Ollama',
};

export const ProvidersView: React.FC<ProvidersViewProps> = ({
  providers,
  activeProjectId,
  projectBudget,
  spendLedger,
  onConfigureProvider,
  onTestProvider,
  onSelectModel,
  onDeleteProvider,
  onUpdateProjectBudget,
  onReconcileRequest,
}) => {
  const [name, setName] = useState('');
  const [providerType, setProviderType] = useState<ProviderType>('gemini');
  const [baseUrl, setBaseUrl] = useState(DEFAULT_URLS.gemini);
  const [apiKey, setApiKey] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [budgetInput, setBudgetInput] = useState(
    projectBudget ? String(projectBudget.budget_limit_usd) : '10'
  );
  const [isSavingBudget, setIsSavingBudget] = useState(false);

  const nameId = useId();
  const typeId = useId();
  const urlId = useId();
  const keyId = useId();
  const budgetId = useId();

  const handleTypeChange = (nextType: ProviderType) => {
    setProviderType(nextType);
    setBaseUrl(DEFAULT_URLS[nextType]);
  };

  const handleSaveProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving) return;
    if (!name.trim()) {
      setError('Provider name is required.');
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      const secretToStore = apiKey.trim() || null;
      await onConfigureProvider({
        name: name.trim(),
        provider_type: providerType,
        base_url: baseUrl.trim() || DEFAULT_URLS[providerType],
        api_key: secretToStore,
      });
      // Immediately clear secret from component state after submission
      setName('');
      setApiKey('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save provider configuration.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async (providerId: string) => {
    setTestingId(providerId);
    setError(null);
    try {
      await onTestProvider(providerId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Provider connection test failed.');
    } finally {
      setTestingId(null);
    }
  };

  const handleSaveBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProjectId || !onUpdateProjectBudget || isSavingBudget) return;
    const parsed = Number(budgetInput);
    if (!Number.isFinite(parsed) || parsed < 0) {
      setError('Project budget limit must be a non-negative USD amount.');
      return;
    }
    setIsSavingBudget(true);
    setError(null);
    try {
      await onUpdateProjectBudget(activeProjectId, parsed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update project budget.');
    } finally {
      setIsSavingBudget(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-[#191919] p-6 text-neutral-200">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#2a2a2a] pb-4">
          <div>
            <h1 className="flex items-center gap-2 text-lg font-semibold text-white">
              <Plug className="h-4 w-4 text-emerald-400" />
              Providers &amp; Protected Credentials
            </h1>
            <p className="mt-1 text-xs text-neutral-400">
              Secrets are encrypted with Windows protected storage (DPAPI) outside SQLite and never shown in logs or read APIs.
            </p>
          </div>
          <Badge variant="outline" className="gap-1.5 border-emerald-700/40 text-emerald-300">
            <ShieldCheck className="h-3 w-3" />
            DPAPI Vault Active
          </Badge>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-800/50 bg-red-950/30 px-3.5 py-2.5 text-xs text-red-200"
          >
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <form
            onSubmit={handleSaveProvider}
            className="space-y-4 rounded-xl border border-[#2a2a2a] bg-[#202020] p-4 lg:col-span-5"
          >
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neutral-400">
              <Plus className="h-3.5 w-3.5 text-emerald-400" />
              Connect Provider
            </div>

            <div className="space-y-1.5">
              <label htmlFor={nameId} className="block text-xs text-neutral-300">
                Provider Name
              </label>
              <Input
                id={nameId}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Gemini Studio"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor={typeId} className="block text-xs text-neutral-300">
                Provider Type
              </label>
              <select
                id={typeId}
                value={providerType}
                onChange={(e) => handleTypeChange(e.target.value as ProviderType)}
                className="h-8 w-full rounded-lg border border-[#2e2e2e] bg-[#191919] px-2.5 text-xs text-neutral-100 focus:border-emerald-500 focus:outline-none"
              >
                <option value="gemini">Google Gemini API</option>
                <option value="openai_compatible">OpenAI-Compatible API</option>
                <option value="local_ollama">Local Ollama</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor={urlId} className="block text-xs text-neutral-300">
                Endpoint Base URL
              </label>
              <Input
                id={urlId}
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={DEFAULT_URLS[providerType]}
              />
            </div>

            {providerType !== 'local_ollama' && (
              <div className="space-y-1.5">
                <label htmlFor={keyId} className="block text-xs text-neutral-300">
                  API Key (write-only)
                </label>
                <Input
                  id={keyId}
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Paste API key to store in DPAPI vault"
                />
              </div>
            )}

            <Button type="submit" disabled={isSaving} className="w-full">
              <KeyRound className="h-3.5 w-3.5" />
              {isSaving ? 'Saving...' : 'Save Provider'}
            </Button>
          </form>

          <div className="space-y-4 lg:col-span-7">
            <div className="rounded-xl border border-[#2a2a2a] bg-[#202020] p-4">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
                  Configured Providers ({providers.length})
                </span>
              </div>

              {providers.length === 0 ? (
                <p className="py-6 text-center text-xs text-neutral-500">
                  No providers configured yet. Add Gemini, an OpenAI-compatible endpoint, or local Ollama.
                </p>
              ) : (
                <div className="space-y-3">
                  {providers.map((provider) => {
                    const isTesting = testingId === provider.id;
                    return (
                      <div
                        key={provider.id}
                        data-testid={`provider-card-${provider.id}`}
                        className="rounded-lg border border-[#2a2a2a] bg-[#191919] p-3.5"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-white">{provider.name}</span>
                              <Badge variant="secondary">
                                {PROVIDER_LABELS[provider.provider_type]}
                              </Badge>
                              {provider.connection_status === 'verified' ? (
                                <Badge className="gap-1">
                                  <CheckCircle2 className="h-3 w-3" />
                                  Verified
                                </Badge>
                              ) : provider.connection_status === 'failed' ? (
                                <Badge variant="destructive" className="gap-1">
                                  <XCircle className="h-3 w-3" />
                                  Failed
                                </Badge>
                              ) : (
                                <Badge variant="outline">Unverified</Badge>
                              )}
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] text-neutral-400">
                              <span>{provider.base_url}</span>
                              <span>
                                Key:{' '}
                                {provider.credential_preview ??
                                  (provider.credential_status === 'not_required'
                                    ? 'Not required'
                                    : 'Missing')}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={isTesting}
                              onClick={() => handleTest(provider.id)}
                            >
                              <RefreshCw className={`h-3 w-3 ${isTesting ? 'animate-spin' : ''}`} />
                              {isTesting ? 'Testing...' : 'Test Connection'}
                            </Button>
                            <Button
                              type="button"
                              size="icon"
                              variant="ghost"
                              aria-label={`Delete ${provider.name}`}
                              onClick={() => onDeleteProvider(provider.id)}
                            >
                              <Trash2 className="h-3.5 w-3.5 text-neutral-400 hover:text-red-400" />
                            </Button>
                          </div>
                        </div>

                        {provider.supported_capabilities.length > 0 && (
                          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                            {provider.supported_capabilities.map((cap) => (
                              <Badge key={cap} variant="outline" className="text-[10px]">
                                {cap}
                              </Badge>
                            ))}
                          </div>
                        )}

                        {provider.verified_models.length > 0 && (
                          <div className="mt-2.5 flex items-center gap-2">
                            <Cpu className="h-3.5 w-3.5 text-neutral-400" />
                            <label
                              htmlFor={`model-${provider.id}`}
                              className="text-[11px] text-neutral-400"
                            >
                              Model:
                            </label>
                            <select
                              id={`model-${provider.id}`}
                              aria-label={`Model for ${provider.name}`}
                              value={provider.selected_model ?? provider.verified_models[0]}
                              onChange={(e) => onSelectModel(provider.id, e.target.value)}
                              className="h-7 rounded border border-[#2e2e2e] bg-[#202020] px-2 text-xs text-neutral-100 focus:border-emerald-500 focus:outline-none"
                            >
                              {provider.verified_models.map((m) => (
                                <option key={m} value={m}>
                                  {m}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}

                        {provider.last_error && (
                          <p className="mt-2 text-[11px] text-red-400">{provider.last_error}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {activeProjectId && (
              <div className="rounded-xl border border-[#2a2a2a] bg-[#202020] p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-neutral-400">
                    <Wallet className="h-3.5 w-3.5 text-emerald-400" />
                    Project Spending Limit &amp; Ledger
                  </div>
                  {projectBudget && (
                    <span className="text-xs text-neutral-300">
                      Remaining:{' '}
                      <strong className="text-emerald-400">
                        ${projectBudget.remaining_budget_usd.toFixed(2)}
                      </strong>{' '}
                      / ${projectBudget.budget_limit_usd.toFixed(2)}
                    </span>
                  )}
                </div>

                {onUpdateProjectBudget && (
                  <form onSubmit={handleSaveBudget} className="flex items-end gap-2">
                    <div className="flex-1 space-y-1">
                      <label htmlFor={budgetId} className="block text-[11px] text-neutral-400">
                        Project Budget Cap (USD)
                      </label>
                      <Input
                        id={budgetId}
                        type="number"
                        min="0"
                        step="0.01"
                        value={budgetInput}
                        onChange={(e) => setBudgetInput(e.target.value)}
                      />
                    </div>
                    <Button type="submit" size="sm" disabled={isSavingBudget}>
                      {isSavingBudget ? 'Updating...' : 'Save Budget'}
                    </Button>
                  </form>
                )}

                {spendLedger && spendLedger.requests.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <div className="text-[11px] font-medium text-neutral-400">
                      External Requests ({spendLedger.requests.length})
                    </div>
                    {spendLedger.requests.map((req) => (
                      <div
                        key={req.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded border border-[#2a2a2a] bg-[#191919] px-2.5 py-1.5 text-[11px]"
                      >
                        <div className="min-w-0">
                          <span className="font-mono text-neutral-200">{req.request_key}</span>
                          <span className="ml-2 text-neutral-400">{req.operation}</span>
                          {req.external_job_id && (
                            <span className="ml-2 text-neutral-500">{req.external_job_id}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-neutral-300">
                            Est:{' '}
                            {req.estimated_cost_usd !== null
                              ? `$${req.estimated_cost_usd.toFixed(2)}`
                              : 'Unknown'}
                          </span>
                          {req.reported_cost_usd !== null && (
                            <span className="text-emerald-400">
                              Actual: ${req.reported_cost_usd.toFixed(2)}
                            </span>
                          )}
                          <Badge variant="outline">{req.status}</Badge>
                          {(req.status === 'uncertain' || req.status === 'submitted') &&
                            onReconcileRequest && (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => onReconcileRequest(activeProjectId, req.request_key)}
                              >
                                Reconcile
                              </Button>
                            )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
