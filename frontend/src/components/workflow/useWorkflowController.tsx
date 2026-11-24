import { useMemo } from 'react';
import { MarkerType, type Edge } from '@xyflow/react';
import { isStageId, WORKFLOW_STAGES } from '@/lib/workflow/stages';
import { mapStageRuntimeState } from '@/lib/workflow/stageStatus';
import type { AgentNodeCardFlowNode } from '@/components/workflow/AgentNodeCardNode';
import type { StageId, StageRuntimeState } from '@/types';

export const AGENT_NODE_WIDTH = 240;
export const AGENT_NODE_GAP = 72;

const EDGE_COLOR = '#3f3f46';

interface WorkflowControllerOptions {
  selectedStage: string;
  stageStates?: Partial<Record<StageId, StageRuntimeState>>;
  onSelectStage: (stage: StageId) => void;
}

export interface WorkflowController {
  nodes: AgentNodeCardFlowNode[];
  edges: Edge[];
}

/**
 * Single source of truth for what the canvas renders. Execution itself stays
 * outside the presentation layer: this hook only turns caller-supplied state
 * into cards and edges.
 */
export function useWorkflowController({
  selectedStage,
  stageStates,
  onSelectStage,
}: WorkflowControllerOptions): WorkflowController {
  const selectedId = isStageId(selectedStage) ? selectedStage : null;

  const nodes = useMemo<AgentNodeCardFlowNode[]>(
    () =>
      WORKFLOW_STAGES.map((stage, index) => {
        const mapped = mapStageRuntimeState(stageStates?.[stage.id]);
        const Icon = stage.icon;
        const previous = index > 0 ? WORKFLOW_STAGES[index - 1] : null;
        const next = index < WORKFLOW_STAGES.length - 1 ? WORKFLOW_STAGES[index + 1] : null;

        return {
          id: stage.id,
          type: 'agentNodeCard',
          position: { x: index * (AGENT_NODE_WIDTH + AGENT_NODE_GAP), y: 0 },
          style: { width: AGENT_NODE_WIDTH },

          data: {
            stageId: stage.id,
            title: stage.label,
            subtitle: stage.subtitle,
            icon: <Icon size={18} aria-hidden="true" />,
            status: mapped.status,
            statusLabel: mapped.statusLabel,
            selected: selectedId === stage.id,
            disabled: mapped.disabled,
            footer: mapped.footer,
            errorMessage: mapped.errorMessage,
            inputLabel: previous?.outputLabel ?? 'Input',
            outputLabel: stage.outputLabel,
            inputConnected: previous !== null,
            outputConnected: next !== null,
            showInputPort: previous !== null,
            showOutputPort: next !== null,
            onSelect: () => onSelectStage(stage.id),
          },
        };
      }),
    [selectedId, stageStates, onSelectStage]
  );

  const edges = useMemo<Edge[]>(
    () =>
      WORKFLOW_STAGES.slice(0, -1).map((stage, index) => {
        const next = WORKFLOW_STAGES[index + 1];

        return {
          id: `${stage.id}-${next.id}`,
          source: stage.id,
          target: next.id,
          type: 'smoothstep',
          style: { stroke: EDGE_COLOR, strokeWidth: 1.5 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: EDGE_COLOR,
            width: 14,
            height: 14,
          },
        };
      }),
    []
  );

  return { nodes, edges };
}
