import type { ReactNode } from 'react';
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react';
import {
  AgentNodeCard,
  AgentNodeParam,
  AgentNodeParams,
  AgentNodeToggle,
  type NodeStatus,
} from '@/components/ui/interactive-ai-agent-workflow-node-card';
import type { StageParamDefinition } from '@/lib/workflow/stages';
import type { StageId } from '@/types';

export interface AgentNodeToggleItem {
  id: string;
  label: string;
  description?: string;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (checked: boolean) => void;
}

/**
 * Data carried by a typed React Flow node that renders the shared
 * AgentNodeCard. Status is already mapped to one of the four visual states.
 */
export interface AgentNodeCardNodeData extends Record<string, unknown> {
  stageId: StageId;
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  status: NodeStatus;
  statusLabel?: string;
  selected: boolean;
  disabled?: boolean;
  params?: readonly StageParamDefinition[];
  toggles?: readonly AgentNodeToggleItem[];
  footer?: ReactNode;
  errorMessage?: string;
  inputLabel?: string;
  outputLabel?: string;
  inputConnected?: boolean;
  outputConnected?: boolean;
  showInputPort?: boolean;
  showOutputPort?: boolean;
  portOffset?: number;
  onSelect?: () => void;
  onRunNode?: () => void;
  runLabel?: string;
}

export type AgentNodeCardFlowNode = Node<AgentNodeCardNodeData, 'agentNodeCard'>;

/**
 * React Flow wrapper around the owner-supplied AgentNodeCard.
 *
 * The card keeps its own visible, labelled port markers. The React Flow handles
 * are transparent and sit exactly on those markers, so an edge attaches to the
 * same point without rendering a second visible dot.
 */
export function AgentNodeCardNode({ data }: NodeProps<AgentNodeCardFlowNode>) {
  const portOffset = data.portOffset ?? 36;
  const inputLabel = data.inputLabel ?? 'Input';
  const outputLabel = data.outputLabel ?? 'Output';
  const hasParams = Boolean(data.params && data.params.length > 0);
  const hasToggles = Boolean(data.toggles && data.toggles.length > 0);

  return (
    <div className="relative w-full">
      <AgentNodeCard
        title={data.title}
        subtitle={data.subtitle}
        icon={data.icon}
        status={data.status}
        statusLabel={data.statusLabel}
        selected={data.selected}
        disabled={data.disabled}
        footer={data.footer}
        errorMessage={data.errorMessage}
        onSelect={data.onSelect}
        onRunNode={data.onRunNode}
        runLabel={data.runLabel}
        inputLabel={inputLabel}
        outputLabel={outputLabel}
        inputConnected={data.inputConnected}
        outputConnected={data.outputConnected}
        showInputPort={data.showInputPort}
        showOutputPort={data.showOutputPort}
        portOffset={portOffset}
      >
        {(hasParams || hasToggles) && (
          <>
            {hasParams && (
              <AgentNodeParams>
                {data.params!.map((param) => (
                  <AgentNodeParam
                    key={param.label}
                    label={param.label}
                    value={param.value}
                    mono={param.mono}
                  />
                ))}
              </AgentNodeParams>
            )}
            {hasToggles && (
              <div className={hasParams ? 'mt-3 space-y-2 border-t border-border pt-3' : 'space-y-2'}>
                {data.toggles!.map((toggle) => (
                  <AgentNodeToggle
                    key={toggle.id}
                    label={toggle.label}
                    description={toggle.description}
                    checked={toggle.checked}
                    disabled={toggle.disabled}
                    onCheckedChange={toggle.onCheckedChange}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </AgentNodeCard>

      {data.showInputPort !== false && (
        <Handle
          type="target"
          position={Position.Left}
          isConnectable={false}
          aria-label={`Input port: ${inputLabel}`}
          title={`Input: ${inputLabel}`}
          data-connected={data.inputConnected ? 'true' : 'false'}
          className="agent-node-handle !h-3.5 !w-3.5 !border-0 !bg-transparent"
          style={{ top: portOffset }}
        />
      )}

      {data.showOutputPort !== false && (
        <Handle
          type="source"
          position={Position.Right}
          isConnectable={false}
          aria-label={`Output port: ${outputLabel}`}
          title={`Output: ${outputLabel}`}
          data-connected={data.outputConnected ? 'true' : 'false'}
          className="agent-node-handle !h-3.5 !w-3.5 !border-0 !bg-transparent"
          style={{ top: portOffset }}
        />
      )}
    </div>
  );
}
