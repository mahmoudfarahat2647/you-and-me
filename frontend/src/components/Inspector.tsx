import React, { useId, useState } from 'react';
import {
  X,
  Zap,
  Edit3,
  UserCheck,
  PowerOff,
  ChevronDown,
  ChevronRight,
  PanelRightClose,
  PanelRightOpen,
} from 'lucide-react';
import {
  getStageDefinition,
  isStageId,
  STAGE_ASSET_TYPE,
} from '../lib/workflow/stages';
import { formatFileSize, formatMediaDuration } from '../lib/media/mediaStageState';
import type { ProjectMediaController } from '../hooks/useProjectMedia';
import type { ProjectWorkflowController } from '../hooks/useProjectWorkflow';
import type {
  Project,
  ProjectAsset,
  ProjectSettings,
  StageExecutionMode,
  UpdateProjectSettingsPayload,
} from '../types';
import { Button } from './ui/button';

interface InspectorProps {
  onClose?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  selectedStage?: string;
  stageMode?: StageExecutionMode;
  onStageModeChange?: (mode: StageExecutionMode) => void;
  project?: Project | null;
  projectSettings?: ProjectSettings | null;
  onUpdateSettings?: (patch: UpdateProjectSettingsPayload) => void;
  projectAssets?: readonly ProjectAsset[];
  mediaController?: ProjectMediaController;
  workflowController?: ProjectWorkflowController;
  onOpenMediaTab?: (tab: 'assets' | 'output') => void;
}

function readScriptString(
  settings: ProjectSettings | null | undefined,
  key: string,
  fallback: string
): string {
  const val = settings?.stage_params?.script?.[key];
  return val !== undefined ? String(val) : fallback;
}

function readScriptNumber(
  settings: ProjectSettings | null | undefined,
  key: string,
  fallback: number
): number {
  const val = settings?.stage_params?.script?.[key];
  return typeof val === 'number' ? val : fallback;
}

export const Inspector: React.FC<InspectorProps> = ({
  onClose,
  isCollapsed = false,
  onToggleCollapse,
  selectedStage = 'script',
  stageMode,
  onStageModeChange,
  project,
  projectSettings,
  onUpdateSettings,
  projectAssets = [],
  mediaController,
  workflowController,
  onOpenMediaTab,
}) => {
  const [activeTab, setActiveTab] = useState<'settings' | 'output' | 'logs'>('settings');
  const [localMode, setLocalMode] = useState<StageExecutionMode>('auto');
  const [localProvider, setLocalProvider] = useState('ChatGPT');
  const [localModel, setLocalModel] = useState('GPT-4o');
  const [localScriptLength, setLocalScriptLength] = useState('~ 8 minutes');
  const [localTone, setLocalTone] = useState('Educational Arabic with historical narrative');
  const [localTemperature, setLocalTemperature] = useState(0.7);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [manualContent, setManualContent] = useState('');
  const [manualUri, setManualUri] = useState('');
  const [approvalDraft, setApprovalDraft] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [sceneEdits, setSceneEdits] = useState<Record<string, string>>({});

  const providerId = useId();
  const modelId = useId();
  const lengthId = useId();
  const toneId = useId();
  const temperatureId = useId();
  const languageId = useId();
  const narratorId = useId();
  const styleId = useId();
  const formatId = useId();
  const budgetId = useId();
  const destinationId = useId();

  const stage = getStageDefinition(isStageId(selectedStage) ? selectedStage : 'script');
  const StageIcon = stage.icon;

  const mode = stageMode ?? projectSettings?.stage_modes?.[stage.id] ?? localMode;
  const provider = projectSettings ? readScriptString(projectSettings, 'provider', 'ChatGPT') : localProvider;
  const model = projectSettings ? readScriptString(projectSettings, 'model', 'GPT-4o') : localModel;
  const scriptLength = projectSettings
    ? readScriptString(projectSettings, 'script_length', '~ 8 minutes')
    : localScriptLength;
  const tone = projectSettings
    ? readScriptString(projectSettings, 'tone', 'Educational documentary narrative')
    : localTone;
  const temperature = projectSettings
    ? readScriptNumber(projectSettings, 'temperature', 0.7)
    : localTemperature;

  const setMode = (next: StageExecutionMode) => {
    if (onStageModeChange) {
      onStageModeChange(next);
    } else if (onUpdateSettings) {
      onUpdateSettings({ stage_modes: { [stage.id]: next } });
    } else {
      setLocalMode(next);
    }
  };

  const updateScriptParam = (key: string, value: string | number) => {
    if (onUpdateSettings) {
      onUpdateSettings({
        stage_params: {
          script: { [key]: value },
        },
      });
    }
  };

  const stageAssetType = STAGE_ASSET_TYPE[stage.id];
  const stageOutputs = stageAssetType
    ? projectAssets.filter((asset) => asset.asset_type === stageAssetType)
    : projectAssets;

  if (isCollapsed) {
    return (
      <aside
        aria-label="Right panel"
        className="w-11 shrink-0 border-l border-[#2e2e2e] bg-[#202020] flex flex-col items-center py-3 gap-3 select-none"
      >
        {onToggleCollapse && (
          <button
            type="button"
            aria-label="Expand right panel"
            aria-expanded={false}
            title="Show right panel"
            onClick={onToggleCollapse}
            className="flex h-7 w-7 items-center justify-center rounded-md text-neutral-400 hover:bg-[#282828] hover:text-neutral-100 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
          >
            <PanelRightOpen className="h-4 w-4" />
          </button>
        )}
      </aside>
    );
  }

  return (
    <aside
      aria-label="Right panel"
      className="w-72 shrink-0 border-l border-[#2e2e2e] bg-[#202020] flex flex-col justify-between select-none"
    >
      <div className="flex-1 overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b border-[#2e2e2e]">
          <div className="flex items-start gap-2.5 min-w-0">
            <div className="mt-0.5 text-neutral-300 shrink-0">
              <StageIcon className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <h3 className="text-xs font-semibold text-neutral-100">{stage.label}</h3>
              <p className="text-[11px] text-neutral-400 mt-0.5 truncate">
                {project ? `${project.name} · ${stage.subtitle}` : stage.subtitle}
              </p>
            </div>
          </div>
          {onToggleCollapse ? (
            <button
              type="button"
              aria-label="Collapse right panel"
              aria-expanded={true}
              title="Hide right panel"
              onClick={onToggleCollapse}
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-neutral-400 hover:bg-[#282828] hover:text-neutral-100 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
            >
              <PanelRightClose className="h-4 w-4" />
            </button>
          ) : onClose ? (
            <button
              aria-label="Close inspector"
              onClick={onClose}
              className="text-neutral-400 hover:text-neutral-200 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-400"
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>

        {/* Sub-tabs: Settings / Output / Logs */}
        <div className="flex items-center px-4 border-b border-[#2e2e2e] text-xs">
          {(['settings', 'output', 'logs'] as const).map((tab) => {
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-2 px-2.5 font-medium capitalize transition-colors relative ${
                  isActive
                    ? 'text-neutral-100'
                    : 'text-neutral-400 hover:text-neutral-200'
                }`}
              >
                {tab}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-[1.5px] bg-neutral-100" />
                )}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        {activeTab === 'settings' && (
          <div className="p-4 space-y-4">
            {/* Mode selection */}
            <div>
              <span className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Mode
              </span>
              <div className="grid grid-cols-4 gap-1 rounded-lg border border-[#2e2e2e] bg-[#191919] p-0.5">
                <button
                  type="button"
                  onClick={() => setMode('auto')}
                  className={`flex items-center justify-center gap-1 py-1 px-1 rounded-md text-[11px] font-medium transition-all ${
                    mode === 'auto'
                      ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-500/30'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Zap className="h-3 w-3" />
                  Auto
                </button>
                <button
                  type="button"
                  onClick={() => setMode('manual')}
                  className={`flex items-center justify-center gap-1 py-1 px-1 rounded-md text-[11px] font-medium transition-all ${
                    mode === 'manual'
                      ? 'bg-[#282828] text-neutral-100 border border-[#383838]'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <Edit3 className="h-3 w-3" />
                  Manual
                </button>
                <button
                  type="button"
                  onClick={() => setMode('approval')}
                  className={`flex items-center justify-center gap-1 py-1 px-1 rounded-md text-[11px] font-medium transition-all ${
                    mode === 'approval'
                      ? 'bg-[#282828] text-neutral-100 border border-[#383838]'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <UserCheck className="h-3 w-3" />
                  Approval
                </button>
                <button
                  type="button"
                  onClick={() => setMode('off')}
                  className={`flex items-center justify-center gap-1 py-1 px-1 rounded-md text-[11px] font-medium transition-all ${
                    mode === 'off'
                      ? 'bg-rose-950/40 text-rose-300 border border-rose-500/30'
                      : 'text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  <PowerOff className="h-3 w-3" />
                  Off
                </button>
              </div>
            </div>

            {/* Provider */}
            <div>
              <label htmlFor={providerId} className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Provider
              </label>
              <div className="relative">
                <select
                  id={providerId}
                  value={provider}
                  onChange={(e) => {
                    const next = e.target.value;
                    if (projectSettings && onUpdateSettings) {
                      updateScriptParam('provider', next);
                    } else {
                      setLocalProvider(next);
                    }
                  }}
                  className="w-full appearance-none rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none transition-colors pr-8 cursor-pointer"
                >
                  <option value="ChatGPT">ChatGPT</option>
                  <option value="Claude">Claude</option>
                  <option value="Gemini">Gemini</option>
                  <option value="Local">Local Ollama</option>
                </select>
                <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
              </div>
            </div>

            {/* Model */}
            <div>
              <label htmlFor={modelId} className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Model
              </label>
              <div className="relative">
                <select
                  id={modelId}
                  value={model}
                  onChange={(e) => {
                    const next = e.target.value;
                    if (projectSettings && onUpdateSettings) {
                      updateScriptParam('model', next);
                    } else {
                      setLocalModel(next);
                    }
                  }}
                  className="w-full appearance-none rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none transition-colors pr-8 cursor-pointer"
                >
                  <option value="GPT-4o">GPT-4o</option>
                  <option value="GPT-4o-mini">GPT-4o-mini</option>
                  <option value="Claude-3-5-Sonnet">Claude 3.5 Sonnet</option>
                  <option value="Gemini-2.0-Flash">Gemini 2.0 Flash</option>
                </select>
                <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
              </div>
            </div>

            {/* Script Length */}
            <div>
              <label htmlFor={lengthId} className="block text-[11px] font-medium text-neutral-400 mb-1.5">
                Script Length
              </label>
              <div className="relative">
                <select
                  id={lengthId}
                  value={scriptLength}
                  onChange={(e) => {
                    const next = e.target.value;
                    if (projectSettings && onUpdateSettings) {
                      updateScriptParam('script_length', next);
                    } else {
                      setLocalScriptLength(next);
                    }
                  }}
                  className="w-full appearance-none rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none transition-colors pr-8 cursor-pointer"
                >
                  <option value="~ 1 minute (Short)">~ 1 minute (Short)</option>
                  <option value="~ 3 minutes">~ 3 minutes</option>
                  <option value="~ 5 minutes">~ 5 minutes</option>
                  <option value="~ 8 minutes">~ 8 minutes</option>
                  <option value="~ 12 minutes">~ 12 minutes</option>
                </select>
                <ChevronDown className="absolute right-3 top-2.5 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
              </div>
            </div>

            {/* Project-Specific Channel Defaults & Overrides */}
            {projectSettings && (
              <div className="pt-3 border-t border-[#2e2e2e] space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium text-neutral-300">
                    Project Settings Overrides
                  </span>
                  <span className="text-[10px] text-neutral-500">Isolated</span>
                </div>

                <div>
                  <label htmlFor={languageId} className="block text-[11px] text-neutral-400 mb-1">
                    Project Language
                  </label>
                  <input
                    id={languageId}
                    type="text"
                    value={projectSettings.language}
                    onChange={(e) => onUpdateSettings?.({ language: e.target.value })}
                    className="w-full rounded-md border border-[#2e2e2e] bg-[#191919] px-2.5 py-1.5 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none"
                  />
                </div>

                <div>
                  <label htmlFor={narratorId} className="block text-[11px] text-neutral-400 mb-1">
                    Narrator
                  </label>
                  <input
                    id={narratorId}
                    type="text"
                    value={projectSettings.narrator}
                    onChange={(e) => onUpdateSettings?.({ narrator: e.target.value })}
                    className="w-full rounded-md border border-[#2e2e2e] bg-[#191919] px-2.5 py-1.5 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none"
                  />
                </div>

                <div>
                  <label htmlFor={styleId} className="block text-[11px] text-neutral-400 mb-1">
                    Visual Style
                  </label>
                  <input
                    id={styleId}
                    type="text"
                    value={projectSettings.visual_style}
                    onChange={(e) => onUpdateSettings?.({ visual_style: e.target.value })}
                    className="w-full rounded-md border border-[#2e2e2e] bg-[#191919] px-2.5 py-1.5 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label htmlFor={formatId} className="block text-[11px] text-neutral-400 mb-1">
                      Format
                    </label>
                    <input
                      id={formatId}
                      type="text"
                      value={projectSettings.video_format}
                      onChange={(e) => onUpdateSettings?.({ video_format: e.target.value })}
                      className="w-full rounded-md border border-[#2e2e2e] bg-[#191919] px-2.5 py-1.5 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label htmlFor={budgetId} className="block text-[11px] text-neutral-400 mb-1">
                      Budget ($)
                    </label>
                    <input
                      id={budgetId}
                      type="number"
                      min="0"
                      step="0.5"
                      value={projectSettings.budget_limit_usd}
                      onChange={(e) => {
                        const parsed = Number(e.target.value);
                        if (Number.isFinite(parsed) && parsed >= 0) {
                          onUpdateSettings?.({ budget_limit_usd: parsed });
                        }
                      }}
                      className="w-full rounded-md border border-[#2e2e2e] bg-[#191919] px-2.5 py-1.5 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor={destinationId} className="block text-[11px] text-neutral-400 mb-1">
                    Upload Destination
                  </label>
                  <input
                    id={destinationId}
                    type="text"
                    value={projectSettings.upload_destination}
                    onChange={(e) => onUpdateSettings?.({ upload_destination: e.target.value })}
                    className="w-full rounded-md border border-[#2e2e2e] bg-[#191919] px-2.5 py-1.5 text-xs text-neutral-100 focus:border-emerald-500/50 focus:outline-none"
                  />
                </div>
              </div>
            )}

            {/* Advanced Options Accordion */}
            <div className="pt-2 border-t border-[#2e2e2e]">
              <button
                type="button"
                aria-expanded={advancedOpen}
                onClick={() => setAdvancedOpen(!advancedOpen)}
                className="w-full flex items-center justify-between text-[11px] font-medium text-neutral-400 hover:text-neutral-200 transition-colors py-1"
              >
                <span>Advanced Options</span>
                {advancedOpen ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
              </button>

              {advancedOpen && (
                <div className="mt-2 space-y-2 text-[11px] text-neutral-400 bg-[#191919] p-2.5 rounded-lg border border-[#2e2e2e]">
                  <div>
                    <label htmlFor={toneId} className="block mb-1 text-neutral-500">Tone & Audience</label>
                    <input
                      id={toneId}
                      type="text"
                      value={tone}
                      onChange={(e) => {
                        const next = e.target.value;
                        if (projectSettings && onUpdateSettings) {
                          updateScriptParam('tone', next);
                        } else {
                          setLocalTone(next);
                        }
                      }}
                      className="w-full bg-[#202020] border border-[#2e2e2e] rounded px-2 py-1 text-xs text-neutral-200"
                    />
                  </div>
                  <div>
                    <label htmlFor={temperatureId} className="block mb-1 text-neutral-500">Temperature</label>
                    <input
                      id={temperatureId}
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={temperature}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        if (projectSettings && onUpdateSettings) {
                          updateScriptParam('temperature', next);
                        } else {
                          setLocalTemperature(next);
                        }
                      }}
                      className="w-full accent-emerald-500"
                    />
                  </div>
                </div>
              )}
            </div>
            {/* Media & Export Summary for Voice/Scenes/Edit/Export */}
            {mediaController && (stage.id === 'voice' || stage.id === 'scenes' || stage.id === 'edit' || stage.id === 'export') && (
              <div className="pt-3 border-t border-[#2e2e2e] space-y-2">
                <span className="block text-[11px] font-medium text-neutral-400">
                  Local Media & Export
                </span>
                <div className="rounded-lg border border-[#2e2e2e] bg-[#191919] p-2.5 text-[11px] space-y-1.5 text-neutral-300">
                  {stage.id === 'voice' && (
                    <p>
                      {mediaController.audio
                        ? `Narration: ${mediaController.audio.original_filename} (${formatMediaDuration(mediaController.audio.duration_seconds)})`
                        : 'No narration audio imported yet.'}
                    </p>
                  )}
                  {stage.id === 'scenes' && (
                    <p>
                      {mediaController.clips.length > 0
                        ? `${mediaController.clips.length} video clip(s) ordered`
                        : 'No moving video clips imported yet.'}
                    </p>
                  )}
                  {(stage.id === 'edit' || stage.id === 'export') && (
                    <p>
                      {mediaController.latestExport
                        ? `Latest MP4: ${mediaController.latestExport.width}x${mediaController.latestExport.height} · ${formatFileSize(mediaController.latestExport.file_size_bytes)}`
                        : `${mediaController.clips.length} clip(s), ${mediaController.audio ? 'audio ready' : 'no audio'}`}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {onOpenMediaTab && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onOpenMediaTab('assets')}
                        className="h-7 text-[11px]"
                      >
                        Manage Assets
                      </Button>
                    )}
                    {(stage.id === 'edit' || stage.id === 'export') && (
                      <Button
                        type="button"
                        size="sm"
                        variant="workflow"
                        disabled={mediaController.isExporting || mediaController.clips.length === 0 || mediaController.audio === null}
                        onClick={() => void mediaController.triggerExport()}
                        className="h-7 text-[11px]"
                      >
                        {mediaController.isExporting ? 'Exporting…' : 'Export MP4'}
                      </Button>
                    )}
                    {mediaController.latestExport && onOpenMediaTab && (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        onClick={() => onOpenMediaTab('output')}
                        className="h-7 text-[11px]"
                      >
                        View Output
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'output' && (
          <div className="p-4 text-xs text-neutral-400 space-y-2.5">
            {mediaController?.latestExport && (stage.id === 'edit' || stage.id === 'export') && (
              <div className="rounded-lg border border-[#2e2e2e] bg-[#191919] p-3 space-y-1.5 text-neutral-200">
                <p className="font-medium text-emerald-400">MP4 Ready</p>
                <p className="font-mono text-[11px] text-neutral-400">
                  {formatMediaDuration(mediaController.latestExport.duration_seconds)} · {mediaController.latestExport.width}x{mediaController.latestExport.height}
                </p>
                {onOpenMediaTab && (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => onOpenMediaTab('output')}
                    className="mt-1 h-7 text-[11px]"
                  >
                    Open Video Player
                  </Button>
                )}
              </div>
            )}
            {stageOutputs.map((asset) => (
              <div
                key={asset.id}
                className="rounded-lg border border-[#2e2e2e] bg-[#191919] p-2.5 space-y-1"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-neutral-200 truncate">{asset.name}</span>
                  <span className="rounded bg-[#282828] px-1.5 py-0.5 text-[10px] uppercase text-neutral-400">
                    {asset.asset_type}
                  </span>
                </div>
                {asset.content && (
                  <p className="text-[11px] text-neutral-400 whitespace-pre-wrap break-words">
                    {asset.content}
                  </p>
                )}
                {asset.file_path && (
                  <p className="font-mono text-[10px] text-neutral-500 truncate">
                    {asset.file_path}
                  </p>
                )}
              </div>
            ))}
            {!(mediaController?.latestExport && (stage.id === 'edit' || stage.id === 'export')) &&
              stageOutputs.length === 0 && (
                <p className="italic text-neutral-500">No output generated yet for this stage.</p>
              )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="p-4 text-xs font-mono text-neutral-400 space-y-2">
            {(() => {
              const stageLogs = mediaController?.logs.filter((l) => l.stage === stage.id) ?? [];
              if (stageLogs.length === 0) {
                return <p className="text-neutral-500">No logs available yet for this stage.</p>;
              }
              return stageLogs.map((entry) => (
                <div
                  key={entry.id}
                  className={`rounded border p-2 text-[11px] ${
                    entry.level === 'error'
                      ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                      : 'border-[#2e2e2e] bg-[#191919] text-neutral-300'
                  }`}
                >
                  <span className="block text-[10px] text-neutral-500">{entry.timestamp}</span>
                  <span className="break-all">{entry.message}</span>
                </div>
              ));
            })()}
          </div>
        )}
      </div>
    </aside>
  );
};
