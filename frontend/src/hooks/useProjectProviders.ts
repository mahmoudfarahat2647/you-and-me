import { useCallback, useEffect, useState } from 'react';
import {
  configureProvider,
  deleteProvider,
  getProjectSpendLedger,
  listProviders,
  reconcileSpendRequest,
  selectProviderModel,
  setProjectBudget,
  testProviderConnection,
} from '@/api/providersClient';
import type { ConfigureProviderPayload, ProjectSpendLedger, ProviderConfigSummary } from '@/types/providers';

export function useProjectProviders(enabled: boolean, ledgerProjectId: string | undefined) {
  const [providers, setProviders] = useState<ProviderConfigSummary[]>([]);
  const [ledger, setLedger] = useState<ProjectSpendLedger | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [ledgerErrorProject, setLedgerErrorProject] = useState<string | null>(null);

  const refreshProviders = useCallback(async () => setProviders(await listProviders()), []);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    void listProviders().then((result) => {
      if (active) setProviders(result);
    }).catch(() => {
      if (active) setCatalogError('Could not load provider configurations.');
    });
    return () => { active = false; };
  }, [enabled]);

  useEffect(() => {
    if (!ledgerProjectId) return;
    let active = true;
    void getProjectSpendLedger(ledgerProjectId).then((result) => {
      if (active) {
        setLedger(result);
        setLedgerErrorProject(null);
      }
    }).catch(() => {
      if (active) setLedgerErrorProject(ledgerProjectId);
    });
    return () => { active = false; };
  }, [ledgerProjectId]);

  const runProviderAction = async <T,>(action: () => Promise<T>, message: string): Promise<T> => {
    setCatalogError(null);
    try {
      const result = await action();
      await refreshProviders();
      return result;
    } catch {
      throw new Error(message);
    }
  };

  return {
    providers,
    ledger: ledger?.budget.project_id === ledgerProjectId ? ledger : null,
    error: catalogError ?? (ledgerErrorProject === ledgerProjectId ? 'Could not load project spending.' : null),
    configure: (payload: ConfigureProviderPayload) =>
      runProviderAction(() => configureProvider(payload), 'Could not save the provider configuration.'),
    test: async (id: string) => {
      await runProviderAction(() => testProviderConnection(id), 'Could not test the provider connection.');
    },
    selectModel: async (id: string, model: string) => {
      await runProviderAction(() => selectProviderModel(id, model), 'Could not select the provider model.');
    },
    remove: async (id: string) => {
      await runProviderAction(() => deleteProvider(id), 'Could not delete the provider configuration.');
    },
    updateBudget: async (id: string, amount: number) => {
      await setProjectBudget(id, amount);
      setLedger(await getProjectSpendLedger(id));
      setLedgerErrorProject(null);
    },
    reconcile: async (id: string, key: string) => {
      await reconcileSpendRequest(id, key);
      setLedger(await getProjectSpendLedger(id));
      setLedgerErrorProject(null);
    },
  };
}
