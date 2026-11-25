import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
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
  Plus,
  Trash2,
} from 'lucide-react';
import type {
  AssetType,
  ChannelProfile,
  CreateProjectAssetPayload,
  Project,
  ProjectAsset,
  ProjectSettings,
  StageExecutionMode,
  StageId,
  StageRuntimeState,
} from '../types';
import type { ProjectMediaController } from '../hooks/useProjectMedia';
import { WORKFLOW_STAGES } from '../lib/workflow/stages';
import { Button } from './ui/button';
import { Input } from './ui/input';
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
  projectSettings?: ProjectSettings | null;
  projectAssets?: readonly ProjectAsset[];
  onCreateAsset?: (payload: CreateProjectAssetPayload) => Promise<void> | void;
  onDeleteAsset?: (assetId: string) => Promise<void> | void;
  activeChannel?: ChannelProfile | null;
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
  projectSettings?: ProjectSettings | null;
  projectAssets?: readonly ProjectAsset[];
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
  projectSettings,
  projectAssets,
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
    projectSettings,
    projectAssets,
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
  projectSettings = null,
  projectAssets = [],
  onCreateAsset,
  onDeleteAsset,
  activeChannel = null,
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

  const [assetFilter, setAssetFilter] = useState<'all' | AssetType>('all');
  const [assetType, setAssetType] = useState<AssetType>('script');
  const [assetName, setAssetName] = useState('');
  const [assetContent, setAssetContent] = useState('');
  const [isSavingAsset, setIsSavingAsset] = useState(false);
  const assetTypeId = useId();
  const assetNameId = useId();
  const assetContentId = useId();

  const mountedRef = useRef(true);
  const timersRef = useRef<Set<number>>(new Set());

  // Clear local transient stage state whenever switching projects so no state leaks.
  useEffect(() => {
    setLocalModes({});
    setLocalToggles({});
    setLocalRunStates({});
    setAssetName('');
    setAssetContent('');
    setAssetFilter('all');
  }, [project.id]);

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
      stageModes?.[stageId] ??
      localModes[stageId] ??
      stageStates?.[stageId]?.mode ??
      projectSettings?.stage_modes?.[stageId] ??
      'auto',
    [stageModes, localModes, stageStates, projectSettings]
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
      const overrideMode =
        stageModes?.[stage.id] ?? localModes[stage.id] ?? projectSettings?.stage_modes?.[stage.id];

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
  }, [stageStates, localRunStates, stageModes, localModes, projectSettings]);

  const handleCreateAssetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onCreateAsset || !assetName.trim() || isSavingAsset) return;
    setIsSavingAsset(true);
    try {
      await onCreateAsset({
        asset_type: assetType,
        name: assetName.trim(),
        content: assetContent.trim(),
      });
      setAssetName('');
      setAssetContent('');
    } finally {
      setIsSavingAsset(false);
    }
  };

  const filteredAssets =
    assetFilter === 'all'
      ? projectAssets
      : projectAssets.filter((asset) => asset.asset_type === assetFilter);

  const exportAssets = projectAssets.filter((asset) => asset.asset_type === 'export');
  const totalAssetsCount =
    projectAssets.length +
    (mediaController ? mediaController.clips.length + (mediaController.audio ? 1 : 0) : 0);

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
          {activeChannel && (
            <>
              <span>/</span>
              <span className="text-neutral-400 truncate">{activeChannel.name}</span>
            </>
          )}
          <span>/</span>
          <span className="text-neutral-300 font-medium truncate">{project.name}</span>
        </div>

        {/* Project Title and Run Button */}
        <div className="mt-2 flex items-center justify-between pb-3">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="text-base font-bold text-neutral-100 truncate">
              {project.name}
            </h1>
            {projectSettings && (
              <span className="hidden sm:inline-flex items-center rounded-md border border-[#2e2e2e] bg-[#202020] px-2 py-0.5 text-[11px] text-neutral-400">
                {projectSettings.language} · {projectSettings.video_format} · ${projectSettings.budget_limit_usd.toFixed(2)}
              </span>
            )}
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
                {tab === 'assets' && totalAssetsCount > 0 && (
                  <span className="ml-1.5 rounded bg-[#282828] px-1.5 py-0.5 text-[10px] text-neutral-300">
                    {totalAssetsCount}
                  </span>
                )}
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
            projectSettings={projectSettings}
            projectAssets={projectAssets}
            onRunStage={handleRunStage}
            onToggleStageAuto={handleToggleStageAuto}
            onToggleStageOption={handleToggleStageOption}
            isInspectorOpen={isInspectorOpen}
          />
        </ReactFlowProvider>
      )}

      {activeTab === 'assets' && (
        <div className="flex-1 overflow-y-auto">
          {mediaController && (
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

          <div className="p-6 pt-2 space-y-5 max-w-5xl mx-auto">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-neutral-100">
                  Assets for {project.name}
                </h2>
                <p className="text-xs text-neutral-400">
                  Project-isolated scripts, scenes, audio narrations, and exports.
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                {(['all', 'script', 'scene', 'audio', 'export'] as const).map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setAssetFilter(type)}
                    className={`rounded-md px-2.5 py-1 text-xs capitalize transition-colors ${
                      assetFilter === type
                        ? 'bg-[#282828] text-neutral-100 font-medium'
                        : 'text-neutral-400 hover:text-neutral-200 hover:bg-[#222222]'
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            {onCreateAsset && (
              <form
                onSubmit={handleCreateAssetSubmit}
                className="rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 grid grid-cols-1 gap-3 md:grid-cols-12 items-end"
              >
                <div className="md:col-span-2">
                  <label htmlFor={assetTypeId} className="block text-[11px] font-medium text-neutral-400 mb-1">
                    Asset Type
                  </label>
                  <select
                    id={assetTypeId}
                    value={assetType}
                    onChange={(e) => setAssetType(e.target.value as AssetType)}
                    className="w-full rounded-lg border border-[#2e2e2e] bg-[#191919] px-2.5 py-2 text-xs text-neutral-100 focus:outline-none"
                  >
                    <option value="script">script</option>
                    <option value="scene">scene</option>
                    <option value="audio">audio</option>
                    <option value="export">export</option>
                  </select>
                </div>
                <div className="md:col-span-4">
                  <label htmlFor={assetNameId} className="block text-[11px] font-medium text-neutral-400 mb-1">
                    Asset Name
                  </label>
                  <Input
                    id={assetNameId}
                    value={assetName}
                    onChange={(e) => setAssetName(e.target.value)}
                    placeholder="e.g. Opening Hook Script"
                  />
                </div>
                <div className="md:col-span-4">
                  <label htmlFor={assetContentId} className="block text-[11px] font-medium text-neutral-400 mb-1">
                    Content / Notes
                  </label>
                  <Input
                    id={assetContentId}
                    value={assetContent}
                    onChange={(e) => setAssetContent(e.target.value)}
                    placeholder="Script text or asset summary..."
                  />
                </div>
                <div className="md:col-span-2">
                  <Button type="submit" disabled={isSavingAsset || !assetName.trim()} className="w-full gap-1.5">
                    <Plus className="h-3.5 w-3.5" />
                    Add Asset
                  </Button>
                </div>
              </form>
            )}

            {filteredAssets.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#2e2e2e] bg-[#202020] p-8 text-center text-xs text-neutral-400">
                No {assetFilter === 'all' ? '' : `${assetFilter} `}assets saved for this project yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {filteredAssets.map((asset) => (
                  <div
                    key={asset.id}
                    className="rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 flex items-start justify-between gap-3"
                  >
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-[#282828] px-1.5 py-0.5 text-[10px] uppercase text-emerald-400">
                          {asset.asset_type}
                        </span>
                        <h3 className="text-xs font-semibold text-neutral-100 truncate">
                          {asset.name}
                        </h3>
                      </div>
                      {asset.content && (
                        <p className="text-xs text-neutral-400 whitespace-pre-wrap break-words">
                          {asset.content}
                        </p>
                      )}
                      {asset.file_path && (
                        <p className="font-mono text-[10px] text-neutral-500 truncate">
                          {asset.file_path}
                        </p>
                      )}
                    </div>
                    {onDeleteAsset && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${asset.name}`}
                        onClick={() => void onDeleteAsset(asset.id)}
                        className="text-neutral-400 hover:text-rose-400 shrink-0"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'output' && (
        <div className="flex-1 overflow-y-auto">
          {mediaController ? (
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
          ) : null}

          {(exportAssets.length > 0 || !mediaController) && (
            <div className="p-6 max-w-4xl mx-auto space-y-4">
              <h2 className="text-sm font-semibold text-neutral-100">
                Outputs for {project.name}
              </h2>
              {exportAssets.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#2e2e2e] bg-[#202020] p-8 text-center text-xs text-neutral-400">
                  No export outputs generated for {project.name} yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {exportAssets.map((asset) => (
                    <div
                      key={asset.id}
                      className="rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 space-y-1"
                    >
                      <div className="text-xs font-semibold text-neutral-100">{asset.name}</div>
                      {asset.content && <p className="text-xs text-neutral-400">{asset.content}</p>}
                      {asset.file_path && (
                        <p className="font-mono text-[11px] text-emerald-400">{asset.file_path}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
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
              <p className="text-neutral-400">No execution logs recorded for {project.name} yet.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
