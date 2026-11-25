import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Play,
  MoreHorizontal,
  MousePointer,
  Hand,
  Maximize2,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import type { Project, StageExecutionMode, StageId, StageRuntimeState } from '../types';
import type { ProjectMediaController } from '../hooks/useProjectMedia';
import { WORKFLOW_STAGES } from '../lib/workflow/stages';
import { Button } from './ui/button';
import { AgentNodeCardNode, type AgentNodeCardFlowNode } from './workflow/AgentNodeCardNode';
import { useWorkflowController } from './workflow/useWorkflowController';
import { MediaAssetsPanel } from './media/MediaAssetsPanel';
import { OutputPlaybackPanel } from './media/OutputPlaybackPanel';

export type WorkspaceTab = 'workflow' | 'assets' | 'output' | 'logs';

interface WorkflowCanvasProps {
  project: Project;
  onOpenProjectsModal: () => void;
  selectedStage: string;
  onSelectStage: (stage: string) => void;
  /** Caller-supplied engine state. Missing stages are truthfully shown as idle. */
  stageStates?: Partial<Record<StageId, StageRuntimeState>>;
  /** Optional externally managed execution modes per stage. */
  stageModes?: Partial<Record<StageId, StageExecutionMode>>;
  onStageModeChange?: (stage: StageId, mode: StageExecutionMode) => void;
  onRunStage?: (stage: StageId) => void;
  onRunWorkflow?: () => void;
  isInspectorOpen?: boolean;
  activeTab?: WorkspaceTab;
  onTabChange?: (tab: WorkspaceTab) => void;
  mediaController?: ProjectMediaController;
}

const nodeTypes = {
  agentNodeCard: AgentNodeCardNode,
} satisfies NodeTypes;

type InteractionMode = 'select' | 'pan';

const FIT_VIEW_OPTIONS = { padding: 0.12, maxZoom: 1 } as const;
const PREVIEW_STEP_DURATION_MS = 1400;

interface WorkflowSurfaceProps {
  selectedStage: string;
  onSelectStage: (stage: string) => void;
  stageStates?: Partial<Record<StageId, StageRuntimeState>>;
  stageToggles?: Partial<Record<StageId, Record<string, boolean>>>;
  onRunStage: (stage: StageId) => void;
  onToggleStageAuto: (stage: StageId, enabled: boolean) => void;
  onToggleStageOption: (stage: StageId, toggleId: string, checked: boolean) => void;
  isInspectorOpen?: boolean;
}

const WorkflowSurface: React.FC<WorkflowSurfaceProps> = ({
  selectedStage,
  onSelectStage,
  stageStates,
  stageToggles,
  onRunStage,
  onToggleStageAuto,
  onToggleStageOption,
  isInspectorOpen,
}) => {
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('select');
  const [zoom, setZoom] = useState(100);
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const prevInspectorOpenRef = useRef(isInspectorOpen);
  const { nodes: controllerNodes, edges } = useWorkflowController({
    selectedStage,
    stageStates,
    stageToggles,
    onSelectStage,
    onRunStage,
    onToggleStageAuto,
    onToggleStageOption,
  });

  const [nodes, setNodes, onNodesChange] = useNodesState<AgentNodeCardFlowNode>(controllerNodes);

  // Keep React Flow's dragged positions while controller data stays authoritative.
  useEffect(() => {
    setNodes((current) =>
      controllerNodes.map((node) => {
        const existing = current.find((candidate) => candidate.id === node.id);
        return existing ? { ...node, position: existing.position } : node;
      })
    );
  }, [controllerNodes, setNodes]);

  // Refit the workflow nodes when the right inspector panel opens or closes.
  useEffect(() => {
    if (prevInspectorOpenRef.current === isInspectorOpen) return;
    prevInspectorOpenRef.current = isInspectorOpen;
    const frameId = window.requestAnimationFrame(() => {
      void fitView(FIT_VIEW_OPTIONS);
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [isInspectorOpen, fitView]);

  const hasProgress = stageStates !== undefined && Object.values(stageStates).some(
    (s) => s !== undefined && s.status !== 'pending' && s.status !== 'cancelled' && s.status !== 'skipped',
  );

  return (
    <div className="flex-1 relative overflow-hidden canvas-dots">
      {!hasProgress && (
        <p className="pointer-events-none absolute top-3 left-4 z-10 text-xs text-neutral-400">
          No workflow progress available yet.
        </p>
      )}

      <ReactFlow<AgentNodeCardFlowNode, Edge>
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onMove={(_event, viewport) => setZoom(Math.round(viewport.zoom * 100))}
        fitView
        fitViewOptions={FIT_VIEW_OPTIONS}
        minZoom={0.15}
        maxZoom={2}
        nodesDraggable={interactionMode === 'select'}
        nodesConnectable={false}
        nodesFocusable={false}
        elementsSelectable={false}
        panOnDrag={interactionMode === 'pan'}
        selectionOnDrag={interactionMode === 'select'}
        className="agent-workflow-canvas"
      >
        {/* The dotted paper comes from the existing canvas-dots background. */}
      </ReactFlow>

      {/* Floating bottom canvas toolbar */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 rounded-xl border border-[#2e2e2e] bg-[#202020] px-2 py-1.5 shadow-xl text-neutral-400">
        <Button
          aria-label="Select"
          aria-pressed={interactionMode === 'select'}
          variant="ghost"
          size="icon"
          className={`h-6 w-6 ${interactionMode === 'select' ? 'bg-[#2c2c2c] text-neutral-100' : ''}`}
          onClick={() => setInteractionMode('select')}
        >
          <MousePointer className="h-3.5 w-3.5" />
        </Button>
        <Button
          aria-label="Pan"
          aria-pressed={interactionMode === 'pan'}
          variant="ghost"
          size="icon"
          className={`h-6 w-6 ${interactionMode === 'pan' ? 'bg-[#2c2c2c] text-neutral-100' : ''}`}
          onClick={() => setInteractionMode('pan')}
        >
          <Hand className="h-3.5 w-3.5" />
        </Button>
        <Button
          aria-label="Fit view"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => void fitView(FIT_VIEW_OPTIONS)}
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </Button>
        <div className="h-4 w-[1px] bg-[#2e2e2e] mx-1" />
        <Button
          aria-label="Zoom out"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => void zoomOut()}
        >
          <ZoomOut className="h-3.5 w-3.5" />
        </Button>
        <span className="px-1 text-[11px] font-mono text-neutral-300 min-w-[3.5rem] text-center">
          {zoom}%
        </span>
        <Button
          aria-label="Zoom in"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => void zoomIn()}
        >
          <ZoomIn className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
};

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  project,
  onOpenProjectsModal,
  selectedStage,
  onSelectStage,
  stageStates,
  stageModes,
  onStageModeChange,
  onRunStage,
  onRunWorkflow,
  isInspectorOpen = true,
  activeTab: controlledActiveTab,
  onTabChange,
  mediaController,
}) => {
  const [localActiveTab, setLocalActiveTab] = useState<WorkspaceTab>('workflow');
  const activeTab = controlledActiveTab ?? localActiveTab;
  const setActiveTab = (tab: WorkspaceTab) => {
    if (onTabChange) {
      onTabChange(tab);
    } else {
      setLocalActiveTab(tab);
    }
  };
  const [localModes, setLocalModes] = useState<Partial<Record<StageId, StageExecutionMode>>>({});
  const [localToggles, setLocalToggles] = useState<Partial<Record<StageId, Record<string, boolean>>>>({});
  const [localRunStates, setLocalRunStates] = useState<Partial<Record<StageId, StageRuntimeState>>>({});
  const [isRunningWorkflow, setIsRunningWorkflow] = useState(false);

  const mountedRef = useRef(true);
  const timersRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    mountedRef.current = true;
    const timers = timersRef.current;
    return () => {
      mountedRef.current = false;
      for (const id of timers) {
        window.clearTimeout(id);
      }
      timers.clear();
    };
  }, []);

  const waitStep = useCallback((ms: number) => {
    return new Promise<void>((resolve) => {
      const id = window.setTimeout(() => {
        timersRef.current.delete(id);
        resolve();
      }, ms);
      timersRef.current.add(id);
    });
  }, []);

  const getStageMode = useCallback(
    (stageId: StageId): StageExecutionMode =>
      stageModes?.[stageId] ?? localModes[stageId] ?? stageStates?.[stageId]?.mode ?? 'auto',
    [stageModes, localModes, stageStates]
  );

  const handleToggleStageAuto = useCallback(
    (stageId: StageId, enabled: boolean) => {
      const nextMode: StageExecutionMode = enabled ? 'auto' : 'off';
      if (onStageModeChange) {
        onStageModeChange(stageId, nextMode);
      } else {
        setLocalModes((prev) => ({ ...prev, [stageId]: nextMode }));
      }
    },
    [onStageModeChange]
  );

  const handleToggleStageOption = useCallback(
    (stageId: StageId, toggleId: string, checked: boolean) => {
      setLocalToggles((prev) => ({
        ...prev,
        [stageId]: {
          ...(prev[stageId] ?? {}),
          [toggleId]: checked,
        },
      }));
    },
    []
  );

  const runLocalStage = useCallback(
    async (stageId: StageId) => {
      if (getStageMode(stageId) === 'off') return;
      setLocalRunStates((prev) => ({
        ...prev,
        [stageId]: { status: 'running' },
      }));
      await waitStep(PREVIEW_STEP_DURATION_MS);
      if (!mountedRef.current) return;
      setLocalRunStates((prev) => ({
        ...prev,
        [stageId]: { status: 'completed' },
      }));
    },
    [getStageMode, waitStep]
  );

  const handleRunStage = useCallback(
    (stageId: StageId) => {
      if (onRunStage) {
        onRunStage(stageId);
        return;
      }
      void runLocalStage(stageId);
    },
    [onRunStage, runLocalStage]
  );

  const handleRunWorkflow = useCallback(async () => {
    if (onRunWorkflow) {
      onRunWorkflow();
      return;
    }
    if (isRunningWorkflow) return;

    setIsRunningWorkflow(true);
    setLocalRunStates({});
    try {
      for (const stage of WORKFLOW_STAGES) {
        if (!mountedRef.current) return;
        if (getStageMode(stage.id) === 'off') continue;
        await runLocalStage(stage.id);
      }
    } finally {
      if (mountedRef.current) {
        setIsRunningWorkflow(false);
      }
    }
  }, [onRunWorkflow, isRunningWorkflow, getStageMode, runLocalStage]);

  const effectiveStageStates = useMemo<Partial<Record<StageId, StageRuntimeState>> | undefined>(() => {
    const merged: Partial<Record<StageId, StageRuntimeState>> = {};
    let hasAnyEntry = false;

    for (const stage of WORKFLOW_STAGES) {
      const callerState = stageStates?.[stage.id];
      const localRun = localRunStates[stage.id];
      const overrideMode = stageModes?.[stage.id] ?? localModes[stage.id];

      if (callerState || localRun || overrideMode) {
        hasAnyEntry = true;
        merged[stage.id] = {
          ...(localRun ?? {}),
          ...(callerState ?? {}),
          status: callerState?.status ?? localRun?.status ?? 'pending',
          mode: overrideMode ?? callerState?.mode,
        };
      }
    }

    return hasAnyEntry ? merged : undefined;
  }, [stageStates, localRunStates, stageModes, localModes]);

  return (
    <div className="flex-1 flex flex-col bg-[#191919] select-none min-w-0 overflow-hidden">
      {/* Top Header Bar */}
      <div className="border-b border-[#2e2e2e] bg-[#191919] px-6 pt-3.5 pb-0">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1 text-[11px] text-neutral-400">
          <button
            onClick={onOpenProjectsModal}
            className="hover:text-neutral-200 transition-colors"
          >
            〈Projects
          </button>
          <span>/</span>
          <span className="text-neutral-300 font-medium truncate">{project.name}</span>
        </div>

        {/* Project Title and Run Button */}
        <div className="mt-2 flex items-center justify-between pb-3">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="text-base font-bold text-neutral-100 truncate">
              {project.name}
            </h1>
            <Button aria-label="Project options" variant="ghost" size="icon" className="text-neutral-400 shrink-0">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </div>

          <Button
            variant="workflow"
            className="gap-2"
            disabled={isRunningWorkflow}
            onClick={() => void handleRunWorkflow()}
          >
            <Play className="h-3 w-3 fill-emerald-400" />
            <span>{isRunningWorkflow ? 'Running…' : 'Run Workflow'}</span>
          </Button>
        </div>

        {/* Header Tabs */}
        <div className="flex items-center gap-6 text-xs border-t border-[#252525]">
          {(['workflow', 'assets', 'output', 'logs'] as const).map((tab) => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 font-medium capitalize transition-colors relative ${
                  isActive
                    ? 'text-neutral-100'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {tab}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-neutral-100" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Workspace View */}
      {activeTab === 'workflow' && (
        <ReactFlowProvider>
          <WorkflowSurface
            selectedStage={selectedStage}
            onSelectStage={onSelectStage}
            stageStates={effectiveStageStates}
            stageToggles={localToggles}
            onRunStage={handleRunStage}
            onToggleStageAuto={handleToggleStageAuto}
            onToggleStageOption={handleToggleStageOption}
            isInspectorOpen={isInspectorOpen}
          />
        </ReactFlowProvider>
      )}

      {activeTab === 'assets' && mediaController && (
        <MediaAssetsPanel
          clips={mediaController.clips}
          audio={mediaController.audio}
          latestExport={mediaController.latestExport}
          isImportingClip={mediaController.isImportingClip}
          isImportingAudio={mediaController.isImportingAudio}
          isExporting={mediaController.isExporting}
          scenesError={mediaController.scenesError}
          voiceError={mediaController.voiceError}
          exportError={mediaController.exportError}
          onImportClipFiles={mediaController.importClipFiles}
          onImportClipPath={mediaController.importClipPath}
          onImportAudioFile={mediaController.importAudioFile}
          onImportAudioPath={mediaController.importAudioPath}
          onMoveClip={mediaController.moveClip}
          onRemoveItem={mediaController.removeItem}
          onExportMp4={async () => {
            await mediaController.triggerExport();
          }}
          onOpenOutput={() => setActiveTab('output')}
        />
      )}

      {activeTab === 'assets' && !mediaController && (
        <div className="flex-1 flex items-center justify-center p-8 text-xs text-neutral-400">
          Media assets manager is not connected.
        </div>
      )}

      {activeTab === 'output' && mediaController && (
        <OutputPlaybackPanel
          latestExport={mediaController.latestExport}
          videoUrl={mediaController.videoUrl}
          isExporting={mediaController.isExporting}
          canExport={mediaController.clips.length >= 1 && mediaController.audio !== null}
          exportError={mediaController.exportError}
          onExportMp4={async () => {
            await mediaController.triggerExport();
          }}
          onGoToAssets={() => setActiveTab('assets')}
        />
      )}

      {activeTab === 'output' && !mediaController && (
        <div className="flex-1 flex items-center justify-center p-8 text-xs text-neutral-400">
          No exported video output available.
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 font-mono text-xs">
            {mediaController && mediaController.logs.length > 0 ? (
              <ul className="space-y-2">
                {mediaController.logs.map((entry) => (
                  <li
                    key={entry.id}
                    className={`flex items-start gap-3 rounded-lg border px-3 py-2 ${
                      entry.level === 'error'
                        ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                        : 'border-[#2e2e2e] bg-[#191919] text-neutral-300'
                    }`}
                  >
                    <span className="text-neutral-500 shrink-0">{entry.timestamp}</span>
                    <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-[#282828] text-neutral-300 shrink-0">
                      {entry.stage}
                    </span>
                    <span className="break-all">{entry.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-neutral-400">No logs available yet.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
