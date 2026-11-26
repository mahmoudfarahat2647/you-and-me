import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  deleteProjectMediaItem,
  exportProjectMp4,
  getOutputVideoUrl,
  getProjectMedia,
  registerProjectAudioPath,
  registerProjectClipPath,
  reorderProjectClips,
  uploadProjectAudio,
  uploadProjectClip,
} from '@/api/client';
import { deriveMediaStageStates } from '@/lib/media/mediaStageState';
import type { ExportMp4Result, ProjectMediaItem, StageId, StageRuntimeState } from '@/types';

export interface MediaLogEntry {
  id: string;
  timestamp: string;
  stage: StageId;
  level: 'info' | 'error';
  message: string;
}

export interface ProjectMediaController {
  clips: ProjectMediaItem[];
  audio: ProjectMediaItem | null;
  latestExport: ExportMp4Result | null;
  videoUrl: string | null;
  isLoading: boolean;
  isImportingClip: boolean;
  isImportingAudio: boolean;
  isExporting: boolean;
  voiceError: string | null;
  scenesError: string | null;
  exportError: string | null;
  logs: MediaLogEntry[];
  stageStates: Partial<Record<StageId, StageRuntimeState>>;
  importClipFiles: (files: FileList | File[]) => Promise<void>;
  importClipPath: (sourcePath: string) => Promise<void>;
  importAudioFile: (file: File) => Promise<void>;
  importAudioPath: (sourcePath: string) => Promise<void>;
  moveClip: (clipId: string, direction: 'up' | 'down') => Promise<void>;
  removeItem: (itemId: string) => Promise<void>;
  triggerExport: () => Promise<ExportMp4Result | null>;
  refresh: () => Promise<void>;
  clearErrors: () => void;
}

function getErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

export function useProjectMedia(projectId: string | undefined): ProjectMediaController {
  const [clips, setClips] = useState<ProjectMediaItem[]>([]);
  const [audio, setAudio] = useState<ProjectMediaItem | null>(null);
  const [latestExport, setLatestExport] = useState<ExportMp4Result | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isImportingClip, setIsImportingClip] = useState(false);
  const [isImportingAudio, setIsImportingAudio] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [scenesError, setScenesError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [logs, setLogs] = useState<MediaLogEntry[]>([]);
  const mediaSession = useRef<symbol | null>(null);

  const appendLog = useCallback((stage: StageId, level: 'info' | 'error', message: string) => {
    const entry: MediaLogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: new Date().toLocaleTimeString(),
      stage,
      level,
      message,
    };
    setLogs((prev) => [entry, ...prev].slice(0, 50));
  }, []);

  useEffect(() => {
    mediaSession.current = Symbol(projectId);
    let cancelled = false;

    async function load() {
      if (!projectId) return;
      try {
        const bundle = await getProjectMedia(projectId);
        if (cancelled) return;
        setClips(bundle.clips);
        setAudio(bundle.audio);
        setLatestExport(bundle.latest_export);
        setVoiceError(null);
        setScenesError(null);
        setExportError(null);
        setLogs([]);
      } catch {
        if (cancelled) return;
        setClips([]);
        setAudio(null);
        setLatestExport(null);
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
      mediaSession.current = null;
    };
  }, [projectId]);

  const importClipFiles = useCallback(
    async (files: FileList | File[]) => {
      if (!projectId) return;
      const list = Array.from(files);
      if (list.length === 0) return;

      setIsImportingClip(true);
      setScenesError(null);
      setExportError(null);
      try {
        for (const file of list) {
          const item = await uploadProjectClip(projectId, file);
          setClips((prev) => [...prev, item]);
          appendLog('scenes', 'info', `Imported clip "${item.original_filename}" (${item.duration_seconds.toFixed(1)}s).`);
        }
      } catch (err: unknown) {
        const msg = getErrorMessage(err, 'Failed to import video clip.');
        setScenesError(msg);
        appendLog('scenes', 'error', msg);
      } finally {
        setIsImportingClip(false);
      }
    },
    [projectId, appendLog]
  );

  const importClipPath = useCallback(
    async (sourcePath: string) => {
      if (!projectId || !sourcePath.trim()) return;
      setIsImportingClip(true);
      setScenesError(null);
      setExportError(null);
      try {
        const item = await registerProjectClipPath(projectId, sourcePath.trim());
        setClips((prev) => [...prev, item]);
        appendLog('scenes', 'info', `Registered clip "${item.original_filename}" (${item.duration_seconds.toFixed(1)}s).`);
      } catch (err: unknown) {
        const msg = getErrorMessage(err, `Failed to register clip "${sourcePath}".`);
        setScenesError(msg);
        appendLog('scenes', 'error', msg);
      } finally {
        setIsImportingClip(false);
      }
    },
    [projectId, appendLog]
  );

  const importAudioFile = useCallback(
    async (file: File) => {
      if (!projectId) return;
      setIsImportingAudio(true);
      setVoiceError(null);
      setExportError(null);
      try {
        const item = await uploadProjectAudio(projectId, file);
        setAudio(item);
        appendLog('voice', 'info', `Imported narration "${item.original_filename}" (${item.duration_seconds.toFixed(1)}s).`);
      } catch (err: unknown) {
        const msg = getErrorMessage(err, `Failed to import narration "${file.name}".`);
        setVoiceError(msg);
        appendLog('voice', 'error', msg);
      } finally {
        setIsImportingAudio(false);
      }
    },
    [projectId, appendLog]
  );

  const importAudioPath = useCallback(
    async (sourcePath: string) => {
      if (!projectId || !sourcePath.trim()) return;
      setIsImportingAudio(true);
      setVoiceError(null);
      setExportError(null);
      try {
        const item = await registerProjectAudioPath(projectId, sourcePath.trim());
        setAudio(item);
        appendLog('voice', 'info', `Registered narration "${item.original_filename}" (${item.duration_seconds.toFixed(1)}s).`);
      } catch (err: unknown) {
        const msg = getErrorMessage(err, `Failed to register narration "${sourcePath}".`);
        setVoiceError(msg);
        appendLog('voice', 'error', msg);
      } finally {
        setIsImportingAudio(false);
      }
    },
    [projectId, appendLog]
  );

  const moveClip = useCallback(
    async (clipId: string, direction: 'up' | 'down') => {
      if (!projectId) return;
      const index = clips.findIndex((c) => c.id === clipId);
      if (index === -1) return;
      const targetIndex = direction === 'up' ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= clips.length) return;

      const reordered = [...clips];
      const [moved] = reordered.splice(index, 1);
      reordered.splice(targetIndex, 0, moved);
      const nextIds = reordered.map((c) => c.id);

      setScenesError(null);
      try {
        const res = await reorderProjectClips(projectId, nextIds);
        setClips(res.clips);
        appendLog('scenes', 'info', `Reordered clips (${res.clips.map((c) => c.original_filename).join(' -> ')}).`);
      } catch (err: unknown) {
        const msg = getErrorMessage(err, 'Failed to reorder clips.');
        setScenesError(msg);
        appendLog('scenes', 'error', msg);
      }
    },
    [projectId, clips, appendLog]
  );

  const removeItem = useCallback(
    async (itemId: string) => {
      if (!projectId) return;
      try {
        await deleteProjectMediaItem(projectId, itemId);
        setClips((prev) =>
          prev
            .filter((c) => c.id !== itemId)
            .map((c, idx) => ({ ...c, position: idx }))
        );
        setAudio((prev) => (prev?.id === itemId ? null : prev));
        appendLog('scenes', 'info', 'Removed media item from project.');
      } catch (err: unknown) {
        const msg = getErrorMessage(err, 'Failed to remove media item.');
        setScenesError(msg);
        appendLog('scenes', 'error', msg);
      }
    },
    [projectId, appendLog]
  );

  const triggerExport = useCallback(async (): Promise<ExportMp4Result | null> => {
    if (!projectId) return null;
    setIsExporting(true);
    setExportError(null);
    try {
      const result = await exportProjectMp4(projectId);
      setLatestExport(result);
      appendLog(
        'export',
        'info',
        `Exported MP4 (${result.width}x${result.height}, ${result.duration_seconds.toFixed(1)}s) to ${result.output_path}.`
      );
      return result;
    } catch (err: unknown) {
      const msg = getErrorMessage(err, 'Failed to export MP4.');
      setExportError(msg);
      appendLog('export', 'error', msg);
      return null;
    } finally {
      setIsExporting(false);
    }
  }, [projectId, appendLog]);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    const session = mediaSession.current;
    try {
      const bundle = await getProjectMedia(projectId);
      if (session === null || mediaSession.current !== session) return;
      setClips(bundle.clips);
      setAudio(bundle.audio);
      setLatestExport(bundle.latest_export);
    } catch {
      // keep existing state when refresh is unavailable
    }
  }, [projectId]);

  const clearErrors = useCallback(() => {
    setVoiceError(null);
    setScenesError(null);
    setExportError(null);
  }, []);

  const stageStates = useMemo(
    () =>
      deriveMediaStageStates({
        clips,
        audio,
        latestExport,
        isExporting,
        voiceError,
        scenesError,
        exportError,
      }),
    [clips, audio, latestExport, isExporting, voiceError, scenesError, exportError]
  );

  const videoUrl = useMemo(() => {
    if (!projectId || !latestExport) return null;
    return getOutputVideoUrl(projectId, latestExport.id);
  }, [projectId, latestExport]);

  return {
    clips,
    audio,
    latestExport,
    videoUrl,
    isLoading,
    isImportingClip,
    isImportingAudio,
    isExporting,
    voiceError,
    scenesError,
    exportError,
    logs,
    stageStates,
    importClipFiles,
    importClipPath,
    importAudioFile,
    importAudioPath,
    moveClip,
    removeItem,
    triggerExport,
    refresh,
    clearErrors,
  };
}
