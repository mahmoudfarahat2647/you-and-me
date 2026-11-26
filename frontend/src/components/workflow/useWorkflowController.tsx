import { useMemo, type CSSProperties } from 'react';
import type { Edge } from '@xyflow/react';
import {
  getStageParamsForProject,
  isStageId,
  STAGE_ASSET_TYPE,
  WORKFLOW_STAGES,
} from '@/lib/workflow/stages';
import { mapStageRuntimeState } from '@/lib/workflow/stageStatus';
import { isProviderReady, STAGE_PROVIDER_CAPABILITY } from '@/lib/workflow/providers';
import type { NodeStatus } from '@/components/ui/interactive-ai-agent-workflow-node-card';
import type {
  AgentNodeCardFlowNode,
  AgentNodeToggleItem,
} from '@/components/workflow/AgentNodeCardNode';
import type {
  ProjectAsset,
  ProjectSettings,
  StageId,
  StageRuntimeState,
  WorkflowJob,
} from '@/types';
import type { ProviderConfigSummary } from '@/types/providers';

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
  projectSettings?: ProjectSettings | null;
  projectAssets?: readonly ProjectAsset[];
  executionLocked?: boolean;
  modeLocked?: boolean;
  providers?: readonly ProviderConfigSummary[];
  job?: WorkflowJob | null;
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
  projectSettings,
  projectAssets,
  executionLocked,
  modeLocked,
  providers,
  job,
  onSelectStage,
  onRunStage,
  onToggleStageAuto,
  onToggleStageOption,
}: WorkflowControllerOptions): WorkflowController {
  const selectedId = isStageId(selectedStage) ? selectedStage : null;

  const nodes = useMemo<AgentNodeCardFlowNode[]>(
    () =>
      WORKFLOW_STAGES.map((stage, index) => {
        const rawStageState = stageStates?.[stage.id];
        const stageAssetType = STAGE_ASSET_TYPE[stage.id];
        const stageAssetCount =
          stageAssetType && projectAssets
            ? projectAssets.filter((asset) => asset.asset_type === stageAssetType).length
            : 0;
        const isIdleMediaPlaceholder =
          rawStageState?.status === 'pending' &&
          rawStageState.footer !== undefined &&
          (rawStageState.footer.startsWith('Waiting for') || rawStageState.footer.startsWith('Needs '));
        const baseRuntime =
          rawStageState ??
          (projectSettings?.stage_modes?.[stage.id]
            ? { status: 'pending' as const, mode: projectSettings.stage_modes[stage.id] }
            : undefined);
        const runtimeInput: StageRuntimeState | undefined =
          baseRuntime && stageAssetCount > 0 && isIdleMediaPlaceholder
            ? { ...baseRuntime, footer: undefined }
            : baseRuntime;
        const mapped = mapStageRuntimeState(runtimeInput);
        const configuredParams = job?.status !== 'canceled'
          ? job?.stages.find((state) => state.stage_id === stage.id)?.params
          : undefined;
        const providerId = (configuredParams ?? projectSettings?.stage_params?.[stage.id])?.provider_id;
        const provider = providers?.find((config) => config.id === providerId);
        const hasProvider = Boolean(providerId && providers && STAGE_PROVIDER_CAPABILITY[stage.id]);
        const providerReady = provider !== undefined && isProviderReady(provider, stage.id);
        const providerRequired = hasProvider && (mapped.mode === 'auto' || mapped.mode === 'approval');
        let params = getStageParamsForProject(stage, projectSettings);
        if (providers && STAGE_PROVIDER_CAPABILITY[stage.id]) {
          params = params.filter((param) => param.label !== 'Provider' && param.label !== 'Model');
          if (hasProvider) {
            params = [
              { label: 'Provider', value: provider?.name ?? 'Unavailable' },
              { label: 'Model', value: (providerReady && provider?.selected_model) || 'Not verified', mono: true },
              ...params,
            ];
          } else {
            const preference = projectSettings?.stage_params?.[stage.id]?.provider;
            if (typeof preference === 'string' && ['ChatGPT', 'Claude', 'Gemini', 'Local', 'ElevenLabs'].includes(preference)) {
              params = [{ label: 'Preferred provider', value: preference }, ...params];
            }
          }
        }
        const Icon = stage.icon;
        const previous = index > 0 ? WORKFLOW_STAGES[index - 1] : null;
        const next = index < WORKFLOW_STAGES.length - 1 ? WORKFLOW_STAGES[index + 1] : null;
        const footerSummary =
          stageAssetCount > 0 && !(rawStageState?.footer && !isIdleMediaPlaceholder)
            ? `${mapped.footer} · ${stageAssetCount} ${stageAssetCount === 1 ? 'asset' : 'assets'}`
            : mapped.footer;

        const toggles: AgentNodeToggleItem[] = stage.toggles.map((toggle) => {
          if (toggle.kind === 'autoMode') {
            return {
              id: toggle.id,
              label: toggle.label,
              description: toggle.description,
              checked: mapped.mode === 'auto',
              disabled: Boolean(modeLocked || mapped.status === 'running' || rawStageState?.status === 'awaiting_approval'),
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
            disabled: Boolean(modeLocked || mapped.disabled || mapped.status === 'running'),
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
            statusLabel: job?.budget_block?.stage_id === stage.id ? 'Budget blocked' : mapped.statusLabel,
            selected: selectedId === stage.id,
            disabled: Boolean(executionLocked || !onRunStage || mapped.disabled || (providerRequired && !providerReady)),
            runLabel: rawStageState?.status === 'stale' ? 'Run again' : undefined,
            params,
            toggles,
            footer: providerRequired && job?.budget_block?.stage_id !== stage.id
              ? `${footerSummary} · ${providerReady ? 'Provider verified' : 'Provider setup required'}`
              : footerSummary,
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
    [
      selectedId,
      stageStates,
      stageToggles,
      projectSettings,
      projectAssets,
      executionLocked,
      modeLocked,
      providers,
      job,
      onSelectStage,
      onRunStage,
      onToggleStageAuto,
      onToggleStageOption,
    ]
  );

  const edges = useMemo<Edge[]>(
    () =>
      WORKFLOW_STAGES.slice(0, -1).map((stage, index) => {
        const next = WORKFLOW_STAGES[index + 1];
        const runtimeInput: StageRuntimeState | undefined =
          stageStates?.[stage.id] ??
          (projectSettings?.stage_modes?.[stage.id]
            ? { status: 'pending', mode: projectSettings.stage_modes[stage.id] }
            : undefined);
        const sourceMapped = mapStageRuntimeState(runtimeInput);
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
    [stageStates, projectSettings]
  );

  return { nodes, edges };
}
