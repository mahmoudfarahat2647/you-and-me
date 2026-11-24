import React, { useEffect, useState } from 'react';
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
import type { Project, StageId, StageRuntimeState } from '../types';
import { Button } from './ui/button';
import { AgentNodeCardNode, type AgentNodeCardFlowNode } from './workflow/AgentNodeCardNode';
import { useWorkflowController } from './workflow/useWorkflowController';

interface WorkflowCanvasProps {
  project: Project;
  onOpenProjectsModal: () => void;
  selectedStage: string;
  onSelectStage: (stage: string) => void;
  /** Caller-supplied engine state. Missing stages are truthfully shown as idle. */
  stageStates?: Partial<Record<StageId, StageRuntimeState>>;
}

const nodeTypes = {
  agentNodeCard: AgentNodeCardNode,
} satisfies NodeTypes;

type InteractionMode = 'select' | 'pan';

const FIT_VIEW_OPTIONS = { padding: 0.08, maxZoom: 1 } as const;

const WorkflowSurface: React.FC<Pick<WorkflowCanvasProps, 'selectedStage' | 'onSelectStage' | 'stageStates'>> = ({
  selectedStage,
  onSelectStage,
  stageStates,
}) => {
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('select');
  const [zoom, setZoom] = useState(100);
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const { nodes: controllerNodes, edges } = useWorkflowController({
    selectedStage,
    stageStates,
    onSelectStage,
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
}) => {
  const [activeTab, setActiveTab] = useState<'workflow' | 'assets' | 'output' | 'logs'>('workflow');

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

          <Button variant="workflow" className="gap-2">
            <Play className="h-3 w-3 fill-emerald-400" />
            <span>Run Workflow</span>
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

      {/* Main Canvas View */}
      <ReactFlowProvider>
        <WorkflowSurface
          selectedStage={selectedStage}
          onSelectStage={onSelectStage}
          stageStates={stageStates}
        />
      </ReactFlowProvider>
    </div>
  );
};
