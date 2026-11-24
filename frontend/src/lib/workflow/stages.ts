import { Film, FileText, Image, Lightbulb, Mic, Upload } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { StageId } from '@/types';

export interface StageParamDefinition {
  label: string;
  value: string;
  mono?: boolean;
}

export interface StageToggleDefinition {
  id: string;
  label: string;
  description?: string;
  defaultChecked: boolean;
  kind?: 'autoMode' | 'option';
}

export interface WorkflowStageDefinition {
  id: StageId;
  label: string;
  subtitle: string;
  /** The artifact this stage hands to the next node. */
  outputLabel: string;
  icon: LucideIcon;
  /** Vertical offset on the canvas so connectors form gentle Bezier curves. */
  topOffset: number;
  params: readonly StageParamDefinition[];
  toggles: readonly StageToggleDefinition[];
}

/** The six approved stages, in their approved order. */
export const WORKFLOW_STAGES: readonly WorkflowStageDefinition[] = [
  {
    id: 'idea',
    label: 'Idea',
    subtitle: 'Choose the topic and sources',
    outputLabel: 'Topic',
    icon: Lightbulb,
    topOffset: 0,
    params: [
      { label: 'Sources', value: 'YouTube + Web', mono: true },
      { label: 'Language', value: 'Arabic' },
      { label: 'Max sources', value: '12' },
    ],
    toggles: [
      {
        id: 'autoMode',
        label: 'Auto mode',
        description: 'Run this phase automatically',
        defaultChecked: true,
        kind: 'autoMode',
      },
      {
        id: 'preflightCheck',
        label: 'Preflight risk check',
        defaultChecked: true,
        kind: 'option',
      },
    ],
  },
  {
    id: 'script',
    label: 'Script',
    subtitle: 'Draft the Arabic script',
    outputLabel: 'Script',
    icon: FileText,
    topOffset: 64,
    params: [
      { label: 'Provider', value: 'ChatGPT' },
      { label: 'Model', value: 'gpt-4o', mono: true },
      { label: 'Length', value: '~ 8 minutes' },
    ],
    toggles: [
      {
        id: 'autoMode',
        label: 'Auto mode',
        description: 'Run this phase automatically',
        defaultChecked: true,
        kind: 'autoMode',
      },
      {
        id: 'includeCitations',
        label: 'Include citations',
        description: 'Link claims to verified sources',
        defaultChecked: true,
        kind: 'option',
      },
    ],
  },
  {
    id: 'voice',
    label: 'Voice',
    subtitle: 'Generate the narration',
    outputLabel: 'Narration',
    icon: Mic,
    topOffset: 20,
    params: [
      { label: 'Provider', value: 'ElevenLabs' },
      { label: 'Voice', value: 'arabic-narrator-v2', mono: true },
      { label: 'Format', value: 'WAV · 48kHz', mono: true },
    ],
    toggles: [
      {
        id: 'autoMode',
        label: 'Auto mode',
        description: 'Run this phase automatically',
        defaultChecked: true,
        kind: 'autoMode',
      },
      {
        id: 'wordTimings',
        label: 'Word-level timings',
        defaultChecked: true,
        kind: 'option',
      },
    ],
  },
  {
    id: 'scenes',
    label: 'Scenes',
    subtitle: 'Plan and generate scenes',
    outputLabel: 'Scene clips',
    icon: Image,
    topOffset: 64,
    params: [
      { label: 'Mode', value: 'Full-motion' },
      { label: 'Aspect', value: '16:9', mono: true },
      { label: 'Clip length', value: '5s / scene' },
    ],
    toggles: [
      {
        id: 'autoMode',
        label: 'Auto mode',
        description: 'Run this phase automatically',
        defaultChecked: true,
        kind: 'autoMode',
      },
      {
        id: 'visualContinuity',
        label: 'Visual continuity',
        description: 'Preserve style across shots',
        defaultChecked: true,
        kind: 'option',
      },
    ],
  },
  {
    id: 'edit',
    label: 'Edit',
    subtitle: 'Sync voice, scenes and music',
    outputLabel: 'Edited video',
    icon: Film,
    topOffset: 20,
    params: [
      { label: 'Engine', value: 'ffmpeg-7', mono: true },
      { label: 'Resolution', value: '1920x1080', mono: true },
      { label: 'Frame rate', value: '30 fps' },
    ],
    toggles: [
      {
        id: 'autoMode',
        label: 'Auto mode',
        description: 'Run this phase automatically',
        defaultChecked: true,
        kind: 'autoMode',
      },
      {
        id: 'burnSubtitles',
        label: 'Burn-in subtitles',
        defaultChecked: true,
        kind: 'option',
      },
    ],
  },
  {
    id: 'export',
    label: 'Export',
    subtitle: 'Review and export the final video',
    outputLabel: 'Final video',
    icon: Upload,
    topOffset: 48,
    params: [
      { label: 'Target', value: 'Local MP4' },
      { label: 'Visibility', value: 'Private', mono: true },
      { label: 'Codec', value: 'H.264 / AAC', mono: true },
    ],
    toggles: [
      {
        id: 'autoMode',
        label: 'Auto mode',
        description: 'Run this phase automatically',
        defaultChecked: true,
        kind: 'autoMode',
      },
      {
        id: 'uploadYoutube',
        label: 'Upload to YouTube',
        defaultChecked: false,
        kind: 'option',
      },
    ],
  },
];

export function isStageId(value: string): value is StageId {
  return WORKFLOW_STAGES.some((stage) => stage.id === value);
}

export function getStageDefinition(stageId: StageId): WorkflowStageDefinition {
  return WORKFLOW_STAGES.find((stage) => stage.id === stageId) ?? WORKFLOW_STAGES[0];
}
