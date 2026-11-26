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
  isStopping: boolean;
  workflowError: string | null;
  stageStates: Partial<Record<StageId, StageRuntimeState>> | undefined;
  runWorkflow: (options?: {
    stage_modes?: Partial<Record<StageId, StageExecutionMode>>;
    force_new?: boolean;
  }) => Promise<WorkflowStateResponse | null>;
  runStage: (stageId: StageId) => Promise<WorkflowStateResponse | null>;
  pause: () => Promise<WorkflowStateResponse | null>;
  cancel: () => Promise<WorkflowStateResponse | null>;
  resume: (approveBudgetRequestKey?: string) => Promise<WorkflowStateResponse | null>;
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
  setStageMode: (stageId: StageId, mode: StageExecutionMode) => Promise<WorkflowStateResponse | null>;
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
    if (job.budget_block?.stage_id === stage.stage_id) {
      footer = job.budget_block.preflight.decision === 'pause_unknown_cost'
        ? 'Budget blocked · unknown cost'
        : 'Budget blocked · estimated overrun';
    } else if (stage.status === 'stale') {
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
  const [isStopping, setIsStopping] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const sessionToken = useMemo(() => Symbol(projectId), [projectId]);
  const sessionRef = useRef<{
    token: symbol;
    response: WorkflowStateResponse | null;
    submitting: boolean;
    stopping: boolean;
  } | null>(null);
  const onExportMayHaveChanged = options?.onExportMayHaveChanged;

  const applyResponse = useCallback(
    (res: WorkflowStateResponse) => {
      const session = sessionRef.current;
      if (session?.token !== sessionToken) return;
      const previous = session.response?.job;
      if (previous && (!res.job || previous.updated_at > res.job.updated_at)) return;
      session.response = res;
      setJob(res.job);
      setLogs(res.logs ?? []);
      const previousExport = previous?.stages.find((s) => s.stage_id === 'export');
      const exportStage = res.job?.stages.find((s) => s.stage_id === 'export');
      if (exportStage?.status === 'completed' &&
          (previousExport?.status !== 'completed' || previousExport.artifact?.artifact_id !== exportStage.artifact?.artifact_id)) {
        void onExportMayHaveChanged?.();
      }
    },
    [sessionToken, onExportMayHaveChanged]
  );

  const refresh = useCallback(async () => {
    if (!projectId || sessionRef.current?.token !== sessionToken) return;
    setIsLoading(true);
    try {
      applyResponse(await getProjectWorkflow(projectId));
    } catch (err) {
      if (sessionRef.current?.token === sessionToken) {
        setWorkflowError(getErrorMessage(err, 'Failed to load workflow state.'));
      }
    } finally {
      if (sessionRef.current?.token === sessionToken) setIsLoading(false);
    }
  }, [projectId, sessionToken, applyResponse]);

  useEffect(() => {
    sessionRef.current = { token: sessionToken, response: null, submitting: false, stopping: false };
    setJob(null);
    setLogs([]);
    setIsLoading(false);
    setIsSubmitting(false);
    setIsStopping(false);
    setWorkflowError(null);
    void refresh();
    return () => { sessionRef.current = null; };
  }, [sessionToken, refresh]);

  useEffect(() => {
    if (!projectId || (!isSubmitting && job?.status !== 'running')) return;
    let polling = false;
    const timer = window.setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        applyResponse(await getProjectWorkflow(projectId));
      } catch {
        // The next poll or action response can reconnect.
      } finally {
        polling = false;
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, [applyResponse, isSubmitting, job?.status, projectId]);

  const executeAction = useCallback(
    async (
      fn: (targetProjectId: string) => Promise<WorkflowStateResponse>,
      fallbackErr: string,
      stop = false
    ): Promise<WorkflowStateResponse | null> => {
      const session = sessionRef.current;
      if (!projectId || session?.token !== sessionToken || session.stopping || (!stop && session.submitting)) return null;
      if (stop) {
        session.stopping = true;
        setIsStopping(true);
      } else {
        session.submitting = true;
        setIsSubmitting(true);
      }
      setWorkflowError(null);
      try {
        const res = await fn(projectId);
        applyResponse(res);
        return res;
      } catch (err: unknown) {
        if (sessionRef.current === session) {
          setWorkflowError(getErrorMessage(err, fallbackErr));
        }
        return null;
      } finally {
        if (stop) session.stopping = false;
        else session.submitting = false;
        if (sessionRef.current === session) {
          if (stop) setIsStopping(false);
          else setIsSubmitting(false);
        }
      }
    },
    [projectId, sessionToken, applyResponse]
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
    () => executeAction((pid) => pauseProjectWorkflow(pid), 'Failed to pause workflow.', true),
    [executeAction]
  );

  const cancel = useCallback(
    () => executeAction((pid) => cancelProjectWorkflow(pid), 'Failed to cancel workflow.', true),
    [executeAction]
  );

  const resume = useCallback(
    (requestKey?: string) => executeAction((pid) => resumeProjectWorkflow(pid, requestKey), 'Failed to resume workflow.'),
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
    (stageId: StageId, mode: StageExecutionMode) =>
      executeAction(
        (pid) => updateWorkflowStageMode(pid, stageId, mode),
        `Failed to update mode for "${stageId}".`
      ),
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

  const projectJob = job?.project_id === projectId ? job : null;
  const stageStates = useMemo(() => deriveWorkflowStageStates(projectJob), [projectJob]);

  return {
    job: projectJob,
    logs: projectJob ? logs : [],
    isLoading,
    isSubmitting,
    isStopping,
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
