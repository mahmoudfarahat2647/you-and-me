import { useMemo, type CSSProperties } from 'react';
import type { Edge } from '@xyflow/react';
import { isStageId, WORKFLOW_STAGES } from '@/lib/workflow/stages';
import { mapStageRuntimeState } from '@/lib/workflow/stageStatus';
import type { NodeStatus } from '@/components/ui/interactive-ai-agent-workflow-node-card';
import type {
  AgentNodeCardFlowNode,
  AgentNodeToggleItem,
} from '@/components/workflow/AgentNodeCardNode';
import type { StageId, StageRuntimeState } from '@/types';

export const AGENT_NODE_WIDTH = 320;
export const AGENT_NODE_GAP = 112;

function getEdgeStyle(status: NodeStatus): { style: CSSProperties; animated: boolean } {
  if (status === 'error') {
    return {
      style: {
        stroke: '#f43f5e',
        strokeWidth: 2,
        strokeDasharray: '6 6',
        strokeLinecap: 'round',
      },
      animated: false,
    };
  }

  if (status === 'running') {
    return {
      style: {
        stroke: 'var(--color-primary)',
        strokeWidth: 2,
        strokeDasharray: '6 6',
        strokeLinecap: 'round',
      },
      animated: true,
    };
  }

  if (status === 'completed') {
    return {
      style: {
        stroke: 'var(--color-primary)',
        strokeWidth: 2,
        strokeLinecap: 'round',
      },
      animated: false,
    };
  }

  return {
    style: {
      stroke: 'var(--color-muted-foreground)',
      strokeOpacity: 0.45,
      strokeWidth: 2,
      strokeDasharray: '6 6',
      strokeLinecap: 'round',
    },
    animated: false,
  };
}

interface WorkflowControllerOptions {
  selectedStage: string;
  stageStates?: Partial<Record<StageId, StageRuntimeState>>;
  stageToggles?: Partial<Record<StageId, Record<string, boolean>>>;
  onSelectStage: (stage: StageId) => void;
  onRunStage?: (stage: StageId) => void;
  onToggleStageAuto?: (stage: StageId, enabled: boolean) => void;
  onToggleStageOption?: (stage: StageId, toggleId: string, checked: boolean) => void;
}

export interface WorkflowController {
  nodes: AgentNodeCardFlowNode[];
  edges: Edge[];
}

/**
 * Single source of truth for what the canvas renders. Execution itself stays
 * outside the presentation layer: this hook turns caller-supplied state and
 * callbacks into typed cards and Bezier connectors.
 */
export function useWorkflowController({
  selectedStage,
  stageStates,
  stageToggles,
  onSelectStage,
  onRunStage,
  onToggleStageAuto,
  onToggleStageOption,
}: WorkflowControllerOptions): WorkflowController {
  const selectedId = isStageId(selectedStage) ? selectedStage : null;

  const nodes = useMemo<AgentNodeCardFlowNode[]>(
    () =>
      WORKFLOW_STAGES.map((stage, index) => {
        const mapped = mapStageRuntimeState(stageStates?.[stage.id]);
        const Icon = stage.icon;
        const previous = index > 0 ? WORKFLOW_STAGES[index - 1] : null;
        const next = index < WORKFLOW_STAGES.length - 1 ? WORKFLOW_STAGES[index + 1] : null;

        const toggles: AgentNodeToggleItem[] = stage.toggles.map((toggle) => {
          if (toggle.kind === 'autoMode') {
            return {
              id: toggle.id,
              label: toggle.label,
              description: toggle.description,
              checked: mapped.mode === 'auto',
              disabled: mapped.status === 'running',
              onCheckedChange: (checked) => {
                onToggleStageAuto?.(stage.id, checked);
              },
            };
          }

          return {
            id: toggle.id,
            label: toggle.label,
            description: toggle.description,
            checked: stageToggles?.[stage.id]?.[toggle.id] ?? toggle.defaultChecked,
            disabled: mapped.disabled || mapped.status === 'running',
            onCheckedChange: (checked) => {
              onToggleStageOption?.(stage.id, toggle.id, checked);
            },
          };
        });

        return {
          id: stage.id,
          type: 'agentNodeCard',
          position: { x: index * (AGENT_NODE_WIDTH + AGENT_NODE_GAP), y: stage.topOffset },
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
            params: stage.params,
            toggles,
            footer: mapped.footer,
            errorMessage: mapped.errorMessage,
            inputLabel: previous?.outputLabel ?? 'Input',
            outputLabel: stage.outputLabel,
            inputConnected: previous !== null,
            outputConnected: next !== null,
            showInputPort: previous !== null,
            showOutputPort: next !== null,
            onSelect: () => onSelectStage(stage.id),
            onRunNode: onRunStage ? () => onRunStage(stage.id) : undefined,
          },
        };
      }),
    [selectedId, stageStates, stageToggles, onSelectStage, onRunStage, onToggleStageAuto, onToggleStageOption]
  );

  const edges = useMemo<Edge[]>(
    () =>
      WORKFLOW_STAGES.slice(0, -1).map((stage, index) => {
        const next = WORKFLOW_STAGES[index + 1];
        const sourceMapped = mapStageRuntimeState(stageStates?.[stage.id]);
        const { style, animated } = getEdgeStyle(sourceMapped.status);

        return {
          id: `${stage.id}-${next.id}`,
          source: stage.id,
          target: next.id,
          type: 'default',
          animated,
          style,
        };
      }),
    [stageStates]
  );

  return { nodes, edges };
}
