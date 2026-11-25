import type { ExportMp4Result, ProjectMediaItem, StageId, StageRuntimeState } from '@/types';

export function formatMediaDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0.0s';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs.toString().padStart(2, '0')}s`;
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export interface MediaStageDeriveInput {
  clips: ProjectMediaItem[];
  audio: ProjectMediaItem | null;
  latestExport: ExportMp4Result | null;
  isExporting: boolean;
  voiceError: string | null;
  scenesError: string | null;
  exportError: string | null;
}

/**
 * Derive truthful Voice, Scenes, Edit, and Export AgentNodeCard states from
 * persisted project media and real local export operations.
 */
export function deriveMediaStageStates({
  clips,
  audio,
  latestExport,
  isExporting,
  voiceError,
  scenesError,
  exportError,
}: MediaStageDeriveInput): Partial<Record<StageId, StageRuntimeState>> {
  const totalClipsDuration = clips.reduce((sum, clip) => sum + clip.duration_seconds, 0);
  const canExport = clips.length >= 1 && audio !== null;

  const voiceState: StageRuntimeState = voiceError
    ? {
        status: 'failed',
        errorMessage: voiceError,
        footer: audio ? 'Prior audio preserved' : 'Narration invalid',
      }
    : audio
    ? {
        status: 'completed',
        footer: `${audio.original_filename} · ${formatMediaDuration(audio.duration_seconds)}`,
      }
    : {
        status: 'pending',
        footer: 'Needs narration audio',
      };

  const scenesState: StageRuntimeState = scenesError
    ? {
        status: 'failed',
        errorMessage: scenesError,
        footer: clips.length > 0 ? `${clips.length} clip(s) kept` : 'Clip validation failed',
      }
    : clips.length >= 2
    ? {
        status: 'completed',
        footer: `${clips.length} clips · ${formatMediaDuration(totalClipsDuration)}`,
      }
    : clips.length === 1
    ? {
        status: 'pending',
        footer: `1 clip · add 1+ more`,
      }
    : {
        status: 'pending',
        footer: 'Needs 2+ moving clips',
      };

  let editState: StageRuntimeState;
  let exportState: StageRuntimeState;

  if (isExporting) {
    editState = {
      status: 'running',
      footer: 'Normalizing & syncing…',
    };
    exportState = {
      status: 'running',
      footer: 'Encoding MP4…',
    };
  } else if (exportError) {
    editState = {
      status: 'failed',
      errorMessage: exportError,
      footer: latestExport ? 'Prior output preserved' : 'Assembly failed',
    };
    exportState = {
      status: 'failed',
      errorMessage: exportError,
      footer: latestExport ? 'Prior MP4 preserved' : 'Export failed',
    };
  } else if (latestExport) {
    editState = {
      status: 'completed',
      footer: `${latestExport.width}x${latestExport.height} · ${formatMediaDuration(latestExport.duration_seconds)}`,
    };
    exportState = {
      status: 'completed',
      footer: `${formatFileSize(latestExport.file_size_bytes)} · ${formatMediaDuration(latestExport.duration_seconds)}`,
    };
  } else if (canExport) {
    editState = {
      status: 'pending',
      footer: `Ready (${clips.length} clip${clips.length === 1 ? '' : 's'} + audio)`,
    };
    exportState = {
      status: 'pending',
      footer: 'Ready to export MP4',
    };
  } else {
    editState = {
      status: 'pending',
      footer: 'Waiting for clips & audio',
    };
    exportState = {
      status: 'pending',
      footer: 'Waiting for Edit inputs',
    };
  }

  return {
    voice: voiceState,
    scenes: scenesState,
    edit: editState,
    export: exportState,
  };
}
