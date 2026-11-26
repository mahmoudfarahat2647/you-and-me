import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  approveWorkflowStage,
  cancelProjectWorkflow,
  getProjectWorkflow,
  pauseProjectWorkflow,
  reconcileProjectWorkflow,
  resumeProjectWorkflow,
  retryWorkflowStage,
  runProjectWorkflow,
  runWorkflowStage,
  submitManualStageResult,
  updateWorkflowScene,
  updateWorkflowStageMode,
} from '@/api/workflowClient';
import type {
  StageExecutionMode,
  StageId,
  StageRuntimeState,
  WorkflowJob,
  WorkflowLogEntry,
  WorkflowStateResponse,
} from '@/types';

export interface ProjectWorkflowController {
  job: WorkflowJob | null;
  logs: WorkflowLogEntry[];
  isLoading: boolean;
  isSubmitting: boolean;
  workflowError: string | null;
  stageStates: Partial<Record<StageId, StageRuntimeState>> | undefined;
  runWorkflow: (options?: {
    stage_modes?: Partial<Record<StageId, StageExecutionMode>>;
    force_new?: boolean;
  }) => Promise<WorkflowStateResponse | null>;
  runStage: (stageId: StageId) => Promise<WorkflowStateResponse | null>;
  pause: () => Promise<WorkflowStateResponse | null>;
  cancel: () => Promise<WorkflowStateResponse | null>;
  resume: () => Promise<WorkflowStateResponse | null>;
  reconcile: () => Promise<WorkflowStateResponse | null>;
  retryStage: (stageId: StageId) => Promise<WorkflowStateResponse | null>;
  submitManual: (
    stageId: StageId,
    payload: { content?: string; uri?: string; auto_resume?: boolean }
  ) => Promise<WorkflowStateResponse | null>;
  approveStage: (
    stageId: StageId,
    payload: {
      approved: boolean;
      edited_content?: string;
      reason?: string;
      rerun?: boolean;
      auto_resume?: boolean;
    }
  ) => Promise<WorkflowStateResponse | null>;
  setStageMode: (stageId: StageId, mode: StageExecutionMode) => Promise<void>;
  updateScene: (
    sceneId: string,
    payload: { prompt?: string; notes?: string; title?: string; reason?: string }
  ) => Promise<WorkflowStateResponse | null>;
  refresh: () => Promise<void>;
  clearError: () => void;
}

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

export function deriveWorkflowStageStates(
  job: WorkflowJob | null
): Partial<Record<StageId, StageRuntimeState>> | undefined {
  if (!job) return undefined;
  const states: Partial<Record<StageId, StageRuntimeState>> = {};
  for (const stage of job.stages) {
    let footer: string | undefined;
    if (stage.status === 'stale') {
      footer = 'Stale · rerun required';
    } else if (stage.status === 'waiting_manual') {
      footer = 'Waiting for manual input';
    } else if (stage.status === 'awaiting_approval') {
      footer = 'Awaiting owner approval';
    } else if (stage.status === 'unknown_outcome') {
      footer = 'Unknown outcome · reconcile';
    } else if (stage.status === 'completed' && stage.items.length > 0) {
      footer = `${stage.items.length} scene item(s) ready`;
    }
    states[stage.stage_id] = {
      status: stage.status,
      mode: stage.mode,
      footer,
      errorMessage: stage.error ?? undefined,
    };
  }
  return states;
}

export function useProjectWorkflow(
  projectId: string | undefined,
  options?: { onExportMayHaveChanged?: () => Promise<void> | void }
): ProjectWorkflowController {
  const [job, setJob] = useState<WorkflowJob | null>(null);
  const [logs, setLogs] = useState<WorkflowLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const activeProjectIdRef = useRef<string | undefined>(projectId);
  const onExportChangedRef = useRef(options?.onExportMayHaveChanged);
  onExportChangedRef.current = options?.onExportMayHaveChanged;

  const applyResponse = useCallback(
    async (targetProjectId: string, res: WorkflowStateResponse) => {
      if (activeProjectIdRef.current !== targetProjectId) return;
      setJob(res.job);
      setLogs(res.logs ?? []);
      const exportStage = res.job?.stages.find((s) => s.stage_id === 'export');
      if (exportStage?.status === 'completed') {
        await onExportChangedRef.current?.();
      }
    },
    []
  );

  const refresh = useCallback(async () => {
    if (!projectId) return;
    const targetProjectId = projectId;
    setIsLoading(true);
    try {
      const res = await getProjectWorkflow(targetProjectId);
      if (activeProjectIdRef.current !== targetProjectId) return;
      setJob(res.job);
      setLogs(res.logs ?? []);
    } catch {
      if (activeProjectIdRef.current !== targetProjectId) return;
      setJob(null);
      setLogs([]);
    } finally {
      if (activeProjectIdRef.current === targetProjectId) {
        setIsLoading(false);
      }
    }
  }, [projectId]);

  useEffect(() => {
    activeProjectIdRef.current = projectId;
    setJob(null);
    setLogs([]);
    setWorkflowError(null);
    if (projectId) {
      void refresh();
    }
  }, [projectId, refresh]);

  const executeAction = useCallback(
    async (
      fn: (targetProjectId: string) => Promise<WorkflowStateResponse>,
      fallbackErr: string
    ): Promise<WorkflowStateResponse | null> => {
      if (!projectId) return null;
      const targetProjectId = projectId;
      setIsSubmitting(true);
      setWorkflowError(null);
      try {
        const res = await fn(targetProjectId);
        await applyResponse(targetProjectId, res);
        return res;
      } catch (err: unknown) {
        if (activeProjectIdRef.current === targetProjectId) {
          setWorkflowError(getErrorMessage(err, fallbackErr));
        }
        return null;
      } finally {
        if (activeProjectIdRef.current === targetProjectId) {
          setIsSubmitting(false);
        }
      }
    },
    [projectId, applyResponse]
  );

  const runWorkflow = useCallback(
    (opts?: { stage_modes?: Partial<Record<StageId, StageExecutionMode>>; force_new?: boolean }) =>
      executeAction((pid) => runProjectWorkflow(pid, opts), 'Failed to run workflow.'),
    [executeAction]
  );

  const runStage = useCallback(
    (stageId: StageId) =>
      executeAction((pid) => runWorkflowStage(pid, stageId), `Failed to run stage "${stageId}".`),
    [executeAction]
  );

  const pause = useCallback(
    () => executeAction((pid) => pauseProjectWorkflow(pid), 'Failed to pause workflow.'),
    [executeAction]
  );

  const cancel = useCallback(
    () => executeAction((pid) => cancelProjectWorkflow(pid), 'Failed to cancel workflow.'),
    [executeAction]
  );

  const resume = useCallback(
    () => executeAction((pid) => resumeProjectWorkflow(pid), 'Failed to resume workflow.'),
    [executeAction]
  );

  const reconcile = useCallback(
    () => executeAction((pid) => reconcileProjectWorkflow(pid), 'Failed to reconcile workflow.'),
    [executeAction]
  );

  const retryStage = useCallback(
    (stageId: StageId) =>
      executeAction((pid) => retryWorkflowStage(pid, stageId), `Failed to retry stage "${stageId}".`),
    [executeAction]
  );

  const submitManual = useCallback(
    (stageId: StageId, payload: { content?: string; uri?: string; auto_resume?: boolean }) =>
      executeAction(
        (pid) => submitManualStageResult(pid, stageId, payload),
        `Failed to submit manual output for "${stageId}".`
      ),
    [executeAction]
  );

  const approveStage = useCallback(
    (
      stageId: StageId,
      payload: {
        approved: boolean;
        edited_content?: string;
        reason?: string;
        rerun?: boolean;
        auto_resume?: boolean;
      }
    ) =>
      executeAction(
        (pid) => approveWorkflowStage(pid, stageId, payload),
        `Failed to submit review for "${stageId}".`
      ),
    [executeAction]
  );

  const setStageMode = useCallback(
    async (stageId: StageId, mode: StageExecutionMode) => {
      await executeAction(
        (pid) => updateWorkflowStageMode(pid, stageId, mode),
        `Failed to update mode for "${stageId}".`
      );
    },
    [executeAction]
  );

  const updateScene = useCallback(
    (sceneId: string, payload: { prompt?: string; notes?: string; title?: string; reason?: string }) =>
      executeAction(
        (pid) => updateWorkflowScene(pid, sceneId, payload),
        `Failed to update scene "${sceneId}".`
      ),
    [executeAction]
  );

  const clearError = useCallback(() => setWorkflowError(null), []);

  const stageStates = useMemo(() => deriveWorkflowStageStates(job), [job]);

  return {
    job,
    logs,
    isLoading,
    isSubmitting,
    workflowError,
    stageStates,
    runWorkflow,
    runStage,
    pause,
    cancel,
    resume,
    reconcile,
    retryStage,
    submitManual,
    approveStage,
    setStageMode,
    updateScene,
    refresh,
    clearError,
  };
}
