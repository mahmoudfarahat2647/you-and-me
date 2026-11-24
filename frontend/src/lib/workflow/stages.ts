import { Film, FileText, Image, Lightbulb, Mic, Upload } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { StageId } from '@/types';

export interface WorkflowStageDefinition {
  id: StageId;
  label: string;
  subtitle: string;
  /** The artifact this stage hands to the next node. */
  outputLabel: string;
  icon: LucideIcon;
}

/** The six approved stages, in their approved order. */
export const WORKFLOW_STAGES: readonly WorkflowStageDefinition[] = [
  {
    id: 'idea',
    label: 'Idea',
    subtitle: 'Choose the topic and sources',
    outputLabel: 'Topic',
    icon: Lightbulb,
  },
  {
    id: 'script',
    label: 'Script',
    subtitle: 'Draft the Arabic script',
    outputLabel: 'Script',
    icon: FileText,
  },
  {
    id: 'voice',
    label: 'Voice',
    subtitle: 'Generate the narration',
    outputLabel: 'Narration',
    icon: Mic,
  },
  {
    id: 'scenes',
    label: 'Scenes',
    subtitle: 'Plan and generate scenes',
    outputLabel: 'Scene clips',
    icon: Image,
  },
  {
    id: 'edit',
    label: 'Edit',
    subtitle: 'Sync voice, scenes and music',
    outputLabel: 'Edited video',
    icon: Film,
  },
  {
    id: 'export',
    label: 'Export',
    subtitle: 'Review and export the final video',
    outputLabel: 'Final video',
    icon: Upload,
  },
];

export function isStageId(value: string): value is StageId {
  return WORKFLOW_STAGES.some((stage) => stage.id === value);
}
