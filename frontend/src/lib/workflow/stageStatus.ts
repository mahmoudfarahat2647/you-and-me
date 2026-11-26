import type { NodeStatus } from '@/components/ui/interactive-ai-agent-workflow-node-card';
import type { StageExecutionMode, StageRunStatus, StageRuntimeState } from '@/types';

export interface MappedStageState {
  /** One of the four approved visual states. */
  status: NodeStatus;
  /** Truthful label for the richer engine status. */
  statusLabel: string;
  mode: StageExecutionMode;
  disabled: boolean;
  footer: string;
  errorMessage?: string;
}

const STATUS_MAP: Record<StageRunStatus, { visual: NodeStatus; label: string }> = {
  pending: { visual: 'idle', label: 'Idle' },
  queued: { visual: 'idle', label: 'Queued' },
  running: { visual: 'running', label: 'Running' },
  in_progress: { visual: 'running', label: 'Running' },
  waiting_manual: { visual: 'idle', label: 'Waiting manual' },
  awaiting_approval: { visual: 'idle', label: 'Awaiting approval' },
  completed: { visual: 'completed', label: 'Completed' },
  failed: { visual: 'error', label: 'Failed' },
  error: { visual: 'error', label: 'Error' },
  cancelled: { visual: 'idle', label: 'Cancelled' },
  canceled: { visual: 'idle', label: 'Canceled' },
  skipped: { visual: 'idle', label: 'Skipped' },
  stale: { visual: 'idle', label: 'Stale' },
  unknown_outcome: { visual: 'idle', label: 'Unknown outcome' },
};

const MODE_LABEL: Record<StageExecutionMode, string> = {
  auto: 'Auto mode',
  manual: 'Manual input',
  approval: 'Approval mode',
  off: 'Execution off',
};

/** Statuses where starting a node directly would contradict the engine state. */
const RUN_BLOCKED_STATUSES: ReadonlySet<StageRunStatus> = new Set([
  'queued',
  'waiting_manual',
  'awaiting_approval',
  'unknown_outcome',
]);

export const DEFAULT_STAGE_STATE: StageRuntimeState = { status: 'pending' };

/**
 * Map a rich backend status onto the four approved visual states without
 * letting the execution mode change the reported status.
 */
export function mapStageRuntimeState(state: StageRuntimeState = DEFAULT_STAGE_STATE): MappedStageState {
  const mode = state.mode ?? 'auto';
  const mapped = STATUS_MAP[state.status] ?? STATUS_MAP.pending;
  const isError = mapped.visual === 'error';

  return {
    status: mapped.visual,
    statusLabel: mapped.label,
    mode,
    disabled: mode === 'off' || RUN_BLOCKED_STATUSES.has(state.status),
    footer: state.footer ?? MODE_LABEL[mode],
    errorMessage: isError ? state.errorMessage : undefined,
  };
}
