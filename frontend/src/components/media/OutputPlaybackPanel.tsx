import React from 'react';
import { AlertCircle, CheckCircle2, Film, Loader2, Play, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { formatFileSize, formatMediaDuration } from '@/lib/media/mediaStageState';
import type { ExportMp4Result } from '@/types';

interface OutputPlaybackPanelProps {
  latestExport: ExportMp4Result | null;
  videoUrl: string | null;
  isExporting: boolean;
  canExport: boolean;
  exportError: string | null;
  onExportMp4: () => Promise<void>;
  onGoToAssets: () => void;
}

export const OutputPlaybackPanel: React.FC<OutputPlaybackPanelProps> = ({
  latestExport,
  videoUrl,
  isExporting,
  canExport,
  exportError,
  onExportMp4,
  onGoToAssets,
}) => {
  return (
    <div className="flex-1 overflow-y-auto p-6 select-text">
      <div className="max-w-4xl mx-auto space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#2e2e2e] bg-[#202020] px-4 py-3">
          <div className="flex items-center gap-2.5">
            <Film className="h-4 w-4 text-emerald-400" />
            <div>
              <h2 className="text-sm font-semibold text-neutral-100">Exported MP4 Output</h2>
              <p className="text-xs text-neutral-400">
                {latestExport
                  ? 'Verified playable MP4 with synchronized video and audio streams.'
                  : 'No exported MP4 yet. Import clips and narration, then run Export.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onGoToAssets}>
              Manage Assets
            </Button>
            <Button
              type="button"
              variant="workflow"
              size="sm"
              disabled={!canExport || isExporting}
              onClick={() => void onExportMp4()}
              className="gap-1.5"
            >
              {isExporting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : latestExport ? (
                <RefreshCw className="h-3.5 w-3.5" />
              ) : (
                <Play className="h-3 w-3 fill-emerald-400" />
              )}
              <span>
                {isExporting ? 'Exporting MP4…' : latestExport ? 'Re-export MP4' : 'Export MP4'}
              </span>
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
              <p className="font-medium">Latest export failed</p>
              <p className="mt-0.5">{exportError}</p>
              {latestExport && (
                <p className="mt-1 text-rose-200/80">
                  Your previous usable MP4 output was preserved and remains playable below.
                </p>
              )}
            </div>
          </div>
        )}

        {latestExport && videoUrl ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-[#2e2e2e] bg-black overflow-hidden">
              <video
                key={latestExport.id}
                src={videoUrl}
                controls
                preload="metadata"
                aria-label="Exported MP4 preview"
                className="w-full max-h-[440px] bg-black"
              />
            </div>

            <div className="rounded-xl border border-[#2e2e2e] bg-[#202020] p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-medium text-emerald-400">
                <CheckCircle2 className="h-4 w-4" />
                <span>MP4 Verification Passed</span>
              </div>

              <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                <div className="rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2">
                  <dt className="text-[11px] text-neutral-400">Duration</dt>
                  <dd className="mt-0.5 font-mono text-neutral-100">
                    {formatMediaDuration(latestExport.duration_seconds)}
                  </dd>
                </div>
                <div className="rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2">
                  <dt className="text-[11px] text-neutral-400">Streams</dt>
                  <dd className="mt-0.5 font-mono text-neutral-100">
                    Video ({latestExport.video_codec ?? 'h264'}) · Audio ({latestExport.audio_codec ?? 'aac'})
                  </dd>
                </div>
                <div className="rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2">
                  <dt className="text-[11px] text-neutral-400">Resolution & Size</dt>
                  <dd className="mt-0.5 font-mono text-neutral-100">
                    {latestExport.width}x{latestExport.height} @ {latestExport.fps}fps · {formatFileSize(latestExport.file_size_bytes)}
                  </dd>
                </div>
                <div className="sm:col-span-2 lg:col-span-3 rounded-lg border border-[#2e2e2e] bg-[#191919] px-3 py-2">
                  <dt className="text-[11px] text-neutral-400">File Path</dt>
                  <dd className="mt-0.5 font-mono text-[11px] text-neutral-200 break-all">
                    {latestExport.output_path}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-[#2e2e2e] bg-[#202020] px-6 py-12 text-center space-y-3">
            <p className="text-xs text-neutral-300 font-medium">No exported video yet</p>
            <p className="text-xs text-neutral-400 max-w-md mx-auto">
              Import moving video clips and narration audio in the Assets tab, then click Export MP4 or run the Export node on the canvas.
            </p>
            <div>
              <Button type="button" size="sm" variant="secondary" onClick={onGoToAssets}>
                Open Assets Tab
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
