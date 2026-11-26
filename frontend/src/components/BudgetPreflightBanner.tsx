import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Hand,
  RefreshCw,
  ShieldAlert,
  Wallet,
} from 'lucide-react';
import type {
  ExternalRequestRecord,
  ProjectBudgetSummary,
  SpendPreflightResult,
} from '../types/providers';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

interface BudgetPreflightBannerProps {
  budget: ProjectBudgetSummary | null;
  preflight: SpendPreflightResult | null;
  recentRequests?: ExternalRequestRecord[];
  isBusy?: boolean;
  onApproveOverrun?: (preflight: SpendPreflightResult) => void;
  onSwitchToManual?: (preflight: SpendPreflightResult) => void;
  onReconcileRequest?: (requestKey: string) => void;
}

function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'Unknown';
  return `$${value.toFixed(2)}`;
}

export const BudgetPreflightBanner: React.FC<BudgetPreflightBannerProps> = ({
  budget,
  preflight,
  recentRequests = [],
  isBusy = false,
  onApproveOverrun,
  onSwitchToManual,
  onReconcileRequest,
}) => {
  const uncertainRequests = recentRequests.filter(
    (req) => req.status === 'uncertain' || req.status === 'submitted'
  );

  return (
    <div className="space-y-3">
      {budget && (
        <div
          className="rounded-lg border border-[#2a2a2a] bg-[#202020] p-3 text-xs text-neutral-300"
          data-testid="budget-summary-strip"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 font-medium text-neutral-100">
              <Wallet className="h-3.5 w-3.5 text-emerald-400" />
              <span>Project Budget Guard</span>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-[11px] text-neutral-400">
              <span>
                Cap: <strong className="text-neutral-200">{formatUsd(budget.budget_limit_usd)}</strong>
              </span>
              <span>
                Spent: <strong className="text-neutral-200">{formatUsd(budget.spent_usd)}</strong>
              </span>
              <span>
                Reserved:{' '}
                <strong className="text-amber-300">
                  {formatUsd(budget.outstanding_reservations_usd)}
                </strong>
              </span>
              <span>
                Remaining:{' '}
                <strong className="text-emerald-400">{formatUsd(budget.remaining_budget_usd)}</strong>
              </span>
            </div>
          </div>
        </div>
      )}

      {preflight && !preflight.allowed && (
        <div
          role="alert"
          data-testid="budget-preflight-pause"
          className="rounded-lg border border-amber-700/50 bg-amber-950/25 p-3.5 text-xs text-amber-100"
        >
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-amber-200">
                  Spend paused before submission
                </span>
                <Badge variant="outline" className="border-amber-600/50 text-amber-300">
                  {preflight.decision}
                </Badge>
              </div>
              <p className="text-amber-100/90 leading-relaxed">{preflight.message}</p>
              <div className="flex flex-wrap items-center gap-3 text-[11px] text-amber-200/80">
                <span>Estimated: {formatUsd(preflight.estimated_cost_usd)}</span>
                <span>Reservations: {formatUsd(preflight.outstanding_reservations_usd)}</span>
                <span>Remaining: {formatUsd(preflight.remaining_budget_usd)}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {preflight.requires_user_approval && onApproveOverrun && (
                  <Button
                    type="button"
                    size="sm"
                    disabled={isBusy}
                    onClick={() => onApproveOverrun(preflight)}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Approve &amp; Submit
                  </Button>
                )}
                {preflight.allows_manual_fallback && onSwitchToManual && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={isBusy}
                    onClick={() => onSwitchToManual(preflight)}
                  >
                    <Hand className="h-3.5 w-3.5" />
                    Switch to Manual
                  </Button>
                )}
                {preflight.decision === 'pause_uncertain_outcome' && onReconcileRequest && (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={isBusy}
                    onClick={() => onReconcileRequest(preflight.request_key)}
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Reconcile Status
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {uncertainRequests.length > 0 && (
        <div className="rounded-lg border border-[#2a2a2a] bg-[#202020] p-3 text-xs text-neutral-300">
          <div className="mb-2 flex items-center gap-2 font-medium text-neutral-200">
            <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
            <span>Pending / Uncertain External Requests</span>
          </div>
          <div className="space-y-1.5">
            {uncertainRequests.map((req) => (
              <div
                key={req.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-[#2a2a2a] bg-[#191919] px-2.5 py-1.5"
              >
                <div className="min-w-0">
                  <span className="font-mono text-[11px] text-neutral-200">{req.request_key}</span>
                  {req.external_job_id && (
                    <span className="ml-2 text-[11px] text-neutral-400">
                      Job: {req.external_job_id}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{req.status}</Badge>
                  {onReconcileRequest && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={isBusy}
                      onClick={() => onReconcileRequest(req.request_key)}
                    >
                      Reconcile
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
