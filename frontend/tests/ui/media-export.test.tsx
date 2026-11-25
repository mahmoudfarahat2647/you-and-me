import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { App } from '../../src/App';
import {
  exportProjectMp4,
  getProjectMedia,
  listProjects,
  reorderProjectClips,
  uploadProjectAudio,
  uploadProjectClip,
} from '../../src/api/client';
import type { ExportMp4Result, Project, ProjectMediaItem } from '../../src/types';

vi.mock('../../src/api/client', () => ({
  checkBackendHealth: vi.fn().mockResolvedValue({ status: 'ok', app: 'test', version: '1' }),
  listProjects: vi.fn(),
  listChannels: vi.fn().mockResolvedValue([]),
  listPresets: vi.fn().mockResolvedValue([]),
  getProjectSettings: vi.fn().mockResolvedValue(null),
  listProjectAssets: vi.fn().mockResolvedValue([]),
  createChannel: vi.fn(),
  updateChannel: vi.fn(),
  updateProjectSettings: vi.fn(),
  createProjectAsset: vi.fn(),
  deleteProjectAsset: vi.fn(),
  getTauriBackendStatus: vi.fn().mockResolvedValue(null),
  restartTauriBackend: vi.fn().mockResolvedValue(null),
  getProjectMedia: vi.fn(),
  uploadProjectClip: vi.fn(),
  registerProjectClipPath: vi.fn(),
  uploadProjectAudio: vi.fn(),
  registerProjectAudioPath: vi.fn(),
  reorderProjectClips: vi.fn(),
  deleteProjectMediaItem: vi.fn(),
  exportProjectMp4: vi.fn(),
  getOutputVideoUrl: vi.fn(
    (projectId: string, exportId?: string) =>
      `http://127.0.0.1:8000/api/projects/${projectId}/output/video${exportId ? `?v=${exportId}` : ''}`
  ),
}));

const sampleProject: Project = {
  id: 'proj-media-1',
  name: 'Giza Clips Project',
  description: 'Moving clips + narration export test',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const clip1: ProjectMediaItem = {
  id: 'clip-1',
  project_id: 'proj-media-1',
  kind: 'clip',
  file_path: 'C:/media/red_clip.mp4',
  original_filename: 'red_clip.mp4',
  position: 0,
  duration_seconds: 1.5,
  has_video: true,
  has_audio: false,
  created_at: '2026-01-01T00:00:01Z',
  width: 640,
  height: 360,
  fps: 24,
  video_codec: 'h264',
};

const clip2: ProjectMediaItem = {
  id: 'clip-2',
  project_id: 'proj-media-1',
  kind: 'clip',
  file_path: 'C:/media/blue_clip.mp4',
  original_filename: 'blue_clip.mp4',
  position: 1,
  duration_seconds: 2.0,
  has_video: true,
  has_audio: false,
  created_at: '2026-01-01T00:00:02Z',
  width: 1280,
  height: 720,
  fps: 30,
  video_codec: 'h264',
};

const narrationAudio: ProjectMediaItem = {
  id: 'audio-1',
  project_id: 'proj-media-1',
  kind: 'audio',
  file_path: 'C:/media/narration.wav',
  original_filename: 'narration.wav',
  position: 0,
  duration_seconds: 3.5,
  has_video: false,
  has_audio: true,
  created_at: '2026-01-01T00:00:03Z',
  audio_codec: 'pcm_s16le',
};

const exportResult: ExportMp4Result = {
  id: 'exp-1',
  project_id: 'proj-media-1',
  output_path: 'C:/media/proj-media-1/output/export.mp4',
  duration_seconds: 3.5,
  width: 1280,
  height: 720,
  fps: 30,
  has_video: true,
  has_audio: true,
  file_size_bytes: 245760,
  clip_ids: ['clip-2', 'clip-1'],
  created_at: '2026-01-01T00:00:04Z',
  video_codec: 'h264',
  audio_codec: 'aac',
  audio_id: 'audio-1',
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listProjects).mockResolvedValue([sampleProject]);
  vi.mocked(getProjectMedia).mockResolvedValue({
    project_id: sampleProject.id,
    clips: [],
    audio: null,
    latest_export: null,
  });
});

it('imports two moving clips and narration, reorders clips, exports MP4, and plays it in Output tab', async () => {
  vi.mocked(uploadProjectClip)
    .mockResolvedValueOnce(clip1)
    .mockResolvedValueOnce(clip2);
  vi.mocked(uploadProjectAudio).mockResolvedValueOnce(narrationAudio);
  vi.mocked(reorderProjectClips).mockResolvedValueOnce({
    project_id: sampleProject.id,
    clips: [
      { ...clip2, position: 0 },
      { ...clip1, position: 1 },
    ],
  });
  vi.mocked(exportProjectMp4).mockResolvedValueOnce(exportResult);

  render(<App />);

  // Initial card readiness before importing
  const scenesCard = await screen.findByRole('group', { name: 'Scenes' });
  expect(within(scenesCard).getByText('Needs 2+ moving clips')).toBeInTheDocument();

  // Clicking Run node on Scenes navigates to Assets tab
  fireEvent.click(within(scenesCard).getByRole('button', { name: 'Run node' }));
  expect(await screen.findByText('Project Media Assets')).toBeInTheDocument();

  // Import two clips
  const clipInput = screen.getByLabelText('Import video clips');
  const file1 = new File(['v1'], 'red_clip.mp4', { type: 'video/mp4' });
  const file2 = new File(['v2'], 'blue_clip.mp4', { type: 'video/mp4' });
  fireEvent.change(clipInput, { target: { files: [file1, file2] } });

  expect(await screen.findByText('red_clip.mp4')).toBeInTheDocument();
  expect(await screen.findByText('blue_clip.mp4')).toBeInTheDocument();

  // Import narration audio
  const audioInput = screen.getByLabelText('Import narration audio');
  const audioFile = new File(['a1'], 'narration.wav', { type: 'audio/wav' });
  fireEvent.change(audioInput, { target: { files: [audioFile] } });
  expect(await screen.findByText('narration.wav')).toBeInTheDocument();

  // Reorder clips: move blue_clip.mp4 up
  fireEvent.click(screen.getByRole('button', { name: 'Move blue_clip.mp4 up' }));
  await waitFor(() => {
    expect(reorderProjectClips).toHaveBeenCalledWith(sampleProject.id, ['clip-2', 'clip-1']);
  });

  const clipList = screen.getByRole('list', { name: 'Ordered video clips' });
  const items = within(clipList).getAllByRole('listitem');
  expect(within(items[0]).getByText('blue_clip.mp4')).toBeInTheDocument();
  expect(within(items[1]).getByText('red_clip.mp4')).toBeInTheDocument();

  // Switch back to Workflow tab and check Voice/Scenes/Export readiness, then run Export node
  fireEvent.click(screen.getByRole('button', { name: 'workflow' }));

  const voiceAfter = await screen.findByRole('group', { name: 'Voice' });
  const scenesAfter = screen.getByRole('group', { name: 'Scenes' });
  const exportCard = screen.getByRole('group', { name: 'Export' });
  expect(within(voiceAfter).getByRole('status')).toHaveTextContent('Completed');
  expect(within(scenesAfter).getByRole('status')).toHaveTextContent('Completed');
  expect(within(exportCard).getByText('Ready to export MP4')).toBeInTheDocument();

  fireEvent.click(within(exportCard).getByRole('button', { name: 'Run node' }));
  await waitFor(() => {
    expect(exportProjectMp4).toHaveBeenCalledWith(sampleProject.id);
  });

  expect(await within(exportCard).findByRole('status')).toHaveTextContent('Completed');

  // Open Output tab and verify <video controls> and metadata
  fireEvent.click(within(screen.getByRole('main')).getByRole('button', { name: 'output' }));
  const videoEl = await screen.findByLabelText('Exported MP4 preview');
  expect(videoEl.tagName).toBe('VIDEO');
  expect(videoEl).toHaveAttribute('controls');
  expect(videoEl).toHaveAttribute(
    'src',
    'http://127.0.0.1:8000/api/projects/proj-media-1/output/video?v=exp-1'
  );
  expect(screen.getByText('C:/media/proj-media-1/output/export.mp4')).toBeInTheDocument();
  expect(screen.getByText(/Video \(h264\) · Audio \(aac\)/)).toBeInTheDocument();
});

it('shows actionable error naming offending input on failed re-export and preserves previous output', async () => {
  vi.mocked(getProjectMedia).mockResolvedValueOnce({
    project_id: sampleProject.id,
    clips: [clip1, clip2],
    audio: narrationAudio,
    latest_export: exportResult,
  });
  vi.mocked(exportProjectMp4).mockRejectedValueOnce(
    new Error("Media file 'blue_clip.mp4' (C:/media/blue_clip.mp4) was not found or is missing.")
  );

  render(<App />);

  const exportCard = await screen.findByRole('group', { name: 'Export' });
  await waitFor(() => {
    expect(within(exportCard).getByRole('status')).toHaveTextContent('Completed');
  });

  // Re-export fails
  fireEvent.click(within(exportCard).getByRole('button', { name: 'Run again' }));

  const alert = await within(exportCard).findByRole('alert');
  expect(alert).toHaveTextContent('blue_clip.mp4');
  expect(within(exportCard).getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  expect(within(exportCard).getByText('Prior MP4 preserved')).toBeInTheDocument();

  // Output tab still preserves and plays the previous usable MP4
  fireEvent.click(within(screen.getByRole('main')).getByRole('button', { name: 'output' }));
  const videoEl = await screen.findByLabelText('Exported MP4 preview');
  expect(videoEl).toHaveAttribute(
    'src',
    'http://127.0.0.1:8000/api/projects/proj-media-1/output/video?v=exp-1'
  );
  expect(screen.getByText(/previous usable MP4 output was preserved/i)).toBeInTheDocument();
});
