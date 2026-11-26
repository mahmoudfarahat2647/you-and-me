import React, { useId, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Film,
  Loader2,
  Mic,
  Play,
  Trash2,
  Upload,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { formatMediaDuration } from '@/lib/media/mediaStageState';
import type { ExportMp4Result, ProjectMediaItem } from '@/types';

interface MediaAssetsPanelProps {
  clips: ProjectMediaItem[];
  audio: ProjectMediaItem | null;
  latestExport: ExportMp4Result | null;
  isImportingClip: boolean;
  isImportingAudio: boolean;
  isExporting: boolean;
  scenesError: string | null;
  voiceError: string | null;
  exportError: string | null;
  onImportClipFiles: (files: FileList | File[]) => Promise<void>;
  onImportClipPath: (path: string) => Promise<void>;
  onImportAudioFile: (file: File) => Promise<void>;
  onImportAudioPath: (path: string) => Promise<void>;
  onMoveClip: (clipId: string, direction: 'up' | 'down') => Promise<void>;
  onRemoveItem: (itemId: string) => Promise<void>;
  onExportMp4: () => Promise<void>;
  onOpenOutput: () => void;
}

export const MediaAssetsPanel: React.FC<MediaAssetsPanelProps> = ({
  clips,
  audio,
  latestExport,
  isImportingClip,
  isImportingAudio,
  isExporting,
  scenesError,
  voiceError,
  exportError,
  onImportClipFiles,
  onImportClipPath,
  onImportAudioFile,
  onImportAudioPath,
  onMoveClip,
  onRemoveItem,
  onExportMp4,
  onOpenOutput,
}) => {
  const [clipPath, setClipPath] = useState('');
  const [audioPath, setAudioPath] = useState('');
  const clipInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);
  const clipFileId = useId();
  const clipPathId = useId();
  const audioFileId = useId();
  const audioPathId = useId();

  const canExport = clips.length >= 1 && audio !== null && !isExporting;

  const handleClipPathSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clipPath.trim()) return;
    await onImportClipPath(clipPath.trim());
    setClipPath('');
  };

  const handleAudioPathSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!audioPath.trim()) return;
    await onImportAudioPath(audioPath.trim());
    setAudioPath('');
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 select-text">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Summary & Export Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#2e2e2e] bg-[#202020] px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-neutral-100">Project Media Assets</h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Import two or more moving video clips, reorder them, add narration audio, and export a playable MP4.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {latestExport && (
              <Button type="button" variant="outline" size="sm" onClick={onOpenOutput}>
                View Output
              </Button>
            )}
            <Button
              type="button"
              variant="workflow"
              size="sm"
              disabled={!canExport}
              onClick={() => void onExportMp4()}
              className="gap-1.5"
            >
              {isExporting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3 w-3 fill-emerald-400" />
              )}
              <span>{isExporting ? 'Exporting MP4…' : 'Export MP4'}</span>
            </Button>
          </div>
        </div>

        {exportError && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-300"
          >
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Export failed</p>
              <p className="mt-0.5">{exportError}</p>
              {latestExport && (
                <p className="mt-1 text-rose-200/80">
                  Previous valid export ({latestExport.output_path}) was preserved.
                </p>
              )}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Moving Video Clips */}
          <section className="rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Film className="h-4 w-4 text-emerald-400" />
                <h3 className="text-xs font-semibold text-neutral-100">
                  Video Clips ({clips.length})
                </h3>
              </div>
              <div>
                <input
                  ref={clipInputRef}
                  id={clipFileId}
                  type="file"
                  accept="video/*"
                  multiple
                  aria-label="Import video clips"
                  className="sr-only"
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) {
                      void onImportClipFiles(e.target.files);
                      e.target.value = '';
                    }
                  }}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={isImportingClip}
                  onClick={() => clipInputRef.current?.click()}
                  className="gap-1.5"
                >
                  {isImportingClip ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Upload className="h-3.5 w-3.5" />
                  )}
                  <span>Import Video Clips</span>
                </Button>
              </div>
            </div>

            <form onSubmit={(e) => void handleClipPathSubmit(e)} className="flex items-center gap-2">
              <label htmlFor={clipPathId} className="sr-only">
                Local clip file path
              </label>
              <Input
                id={clipPathId}
                type="text"
                value={clipPath}
                onChange={(e) => setClipPath(e.target.value)}
                placeholder="Or register local clip path (e.g. C:\clips\scene1.mp4)"
                className="h-8 text-xs"
              />
              <Button type="submit" size="sm" variant="outline" disabled={isImportingClip || !clipPath.trim()}>
                Add Path
              </Button>
            </form>

            {scenesError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300"
              >
                <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <span>{scenesError}</span>
              </div>
            )}

            {clips.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[#2e2e2e] bg-[#191919] px-4 py-6 text-center text-xs text-neutral-400">
                No moving video clips imported yet. Add at least two clips to control sequence order.
              </div>
            ) : (
              <ol className="space-y-2" aria-label="Ordered video clips">
                {clips.map((clip, index) => (
                  <li
                    key={clip.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2.5"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[#282828] font-mono text-[10px] text-neutral-300">
                          {index + 1}
                        </span>
                        <span className="truncate text-xs font-medium text-neutral-100">
                          {clip.original_filename}
                        </span>
                      </div>
                      <p className="mt-1 pl-7 text-[11px] text-neutral-400 font-mono">
                        {formatMediaDuration(clip.duration_seconds)}
                        {clip.width && clip.height ? ` · ${clip.width}x${clip.height}` : ''}
                        {clip.fps ? ` · ${clip.fps}fps` : ''}
                        {clip.video_codec ? ` · ${clip.video_codec}` : ''}
                      </p>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Move ${clip.original_filename} up`}
                        disabled={index === 0 || isExporting}
                        onClick={() => void onMoveClip(clip.id, 'up')}
                        className="h-7 w-7 text-neutral-400 hover:text-neutral-100"
                      >
                        <ArrowUp className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Move ${clip.original_filename} down`}
                        disabled={index === clips.length - 1 || isExporting}
                        onClick={() => void onMoveClip(clip.id, 'down')}
                        className="h-7 w-7 text-neutral-400 hover:text-neutral-100"
                      >
                        <ArrowDown className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Remove ${clip.original_filename}`}
                        disabled={isExporting}
                        onClick={() => void onRemoveItem(clip.id)}
                        className="h-7 w-7 text-neutral-400 hover:text-rose-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>

          {/* Narration Audio */}
          <section className="rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Mic className="h-4 w-4 text-emerald-400" />
                <h3 className="text-xs font-semibold text-neutral-100">
                  Narration Audio
                </h3>
              </div>
              <div>
                <input
                  ref={audioInputRef}
                  id={audioFileId}
                  type="file"
                  accept="audio/*"
                  aria-label="Import narration audio"
                  className="sr-only"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      void onImportAudioFile(file);
                      e.target.value = '';
                    }
                  }}
                />
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={isImportingAudio}
                  onClick={() => audioInputRef.current?.click()}
                  className="gap-1.5"
                >
                  {isImportingAudio ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Upload className="h-3.5 w-3.5" />
                  )}
                  <span>{audio ? 'Replace Narration' : 'Import Narration'}</span>
                </Button>
              </div>
            </div>

            <form onSubmit={(e) => void handleAudioPathSubmit(e)} className="flex items-center gap-2">
              <label htmlFor={audioPathId} className="sr-only">
                Local narration file path
              </label>
              <Input
                id={audioPathId}
                type="text"
                value={audioPath}
                onChange={(e) => setAudioPath(e.target.value)}
                placeholder="Or register local audio path (e.g. C:\audio\narration.wav)"
                className="h-8 text-xs"
              />
              <Button type="submit" size="sm" variant="outline" disabled={isImportingAudio || !audioPath.trim()}>
                Add Path
              </Button>
            </form>

            {voiceError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300"
              >
                <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <span>{voiceError}</span>
              </div>
            )}

            {audio === null ? (
              <div className="rounded-lg border border-dashed border-[#2e2e2e] bg-[#191919] px-4 py-6 text-center text-xs text-neutral-400">
                No narration audio imported yet. Import a WAV, MP3, or AAC narration file.
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-neutral-100">
                    {audio.original_filename}
                  </p>
                  <p className="mt-1 text-[11px] text-neutral-400 font-mono">
                    {formatMediaDuration(audio.duration_seconds)}
                    {audio.audio_codec ? ` · ${audio.audio_codec}` : ''}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove ${audio.original_filename}`}
                  disabled={isExporting}
                  onClick={() => void onRemoveItem(audio.id)}
                  className="h-7 w-7 text-neutral-400 hover:text-rose-400"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};
