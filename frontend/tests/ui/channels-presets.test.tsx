import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, test, vi } from 'vitest';
import { App } from '../../src/App';
import { CreateProjectDialog } from '../../src/components/CreateProjectDialog';
import * as apiClient from '../../src/api/client';
import type {
  ChannelProfile,
  Project,
  ProjectAsset,
  ProjectSettings,
  WorkflowPreset,
} from '../../src/types';

vi.mock('../../src/api/client', async () => {
  const actual = await vi.importActual<typeof import('../../src/api/client')>('../../src/api/client');
  return {
    ...actual,
    checkBackendHealth: vi.fn().mockResolvedValue({ status: 'ok', app: 'test', version: '1' }),
    getTauriBackendStatus: vi.fn().mockResolvedValue(null),
    restartTauriBackend: vi.fn().mockResolvedValue(null),
    listProjects: vi.fn(),
    createProject: vi.fn(),
    listChannels: vi.fn(),
    createChannel: vi.fn(),
    updateChannel: vi.fn(),
    listPresets: vi.fn(),
    getProjectSettings: vi.fn(),
    updateProjectSettings: vi.fn(),
    listProjectAssets: vi.fn(),
    createProjectAsset: vi.fn(),
    deleteProjectAsset: vi.fn(),
  };
});

const presetFullAuto: WorkflowPreset = {
  id: 'preset-full-auto',
  name: 'Full Auto',
  description: 'Run every stage automatically.',
  default_stage_modes: {
    idea: 'auto',
    script: 'auto',
    voice: 'auto',
    scenes: 'auto',
    edit: 'auto',
    export: 'auto',
  },
  default_stage_params: {
    script: { provider: 'ChatGPT', model: 'GPT-4o', script_length: '~ 8 minutes' },
  },
  is_builtin: true,
};

const presetReview: WorkflowPreset = {
  id: 'preset-review-before-publish',
  name: 'Review Before Publish',
  description: 'Require approval before script lock and export.',
  default_stage_modes: {
    idea: 'auto',
    script: 'approval',
    voice: 'auto',
    scenes: 'auto',
    edit: 'auto',
    export: 'approval',
  },
  default_stage_params: {
    script: { provider: 'Claude', model: 'Claude-3-5-Sonnet', script_length: '~ 8 minutes' },
  },
  is_builtin: true,
};

const channelArabic: ChannelProfile = {
  id: 'chan-ar',
  name: 'Arabic History',
  topic_focus: 'Ancient Egypt',
  language: 'Arabic',
  default_narrator: 'arabic-narrator-v2',
  visual_style: 'Painterly Documentary',
  video_format: '16:9',
  budget_limit_usd: 25,
  upload_destination: 'YouTube',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const channelTech: ChannelProfile = {
  id: 'chan-en',
  name: 'English Tech Shorts',
  topic_focus: 'AI Engineering',
  language: 'English',
  default_narrator: 'en-studio-male',
  visual_style: 'Neon Motion',
  video_format: '9:16',
  budget_limit_usd: 8,
  upload_destination: 'YouTube Shorts',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

beforeEach(() => {
  vi.clearAllMocks();
});

test('CreateProjectDialog selects channel profile and workflow preset to inherit defaults', async () => {
  const user = userEvent.setup();
  const createdProject: Project = {
    id: 'proj-new',
    name: 'Cleopatra',
    description: 'Bio',
    channel_profile_id: channelArabic.id,
    preset_id: presetReview.id,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };
  vi.mocked(apiClient.createProject).mockResolvedValueOnce(createdProject);
  const onCreated = vi.fn();

  render(
    <CreateProjectDialog
      isOpen
      onClose={() => {}}
      onProjectCreated={onCreated}
      channels={[channelArabic, channelTech]}
      presets={[presetFullAuto, presetReview]}
      defaultChannelId={channelArabic.id}
    />
  );

  expect(screen.getByLabelText(/channel profile/i)).toHaveValue(channelArabic.id);
  await user.selectOptions(screen.getByLabelText(/workflow preset/i), presetReview.id);
  expect(screen.getByText(/inherits from/i)).toHaveTextContent('Arabic History');
  expect(screen.getByText(/painterly documentary/i)).toBeInTheDocument();

  await user.type(screen.getByLabelText(/project name/i), 'Cleopatra');
  await user.click(screen.getByRole('button', { name: /create project/i }));

  await waitFor(() =>
    expect(apiClient.createProject).toHaveBeenCalledWith({
      name: 'Cleopatra',
      description: '',
      channel_profile_id: channelArabic.id,
      preset_id: presetReview.id,
    })
  );
  expect(onCreated).toHaveBeenCalledWith(createdProject);
});

test('creating two channels, switching channels, overriding settings, and switching projects refreshes AgentNodeCard without state leakage', async () => {
  const user = userEvent.setup();

  const projA: Project = {
    id: 'proj-a',
    name: 'Giza Pyramids',
    description: '',
    channel_profile_id: channelArabic.id,
    preset_id: presetReview.id,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  };
  const projB: Project = {
    id: 'proj-b',
    name: 'Rust Async',
    description: '',
    channel_profile_id: channelTech.id,
    preset_id: presetFullAuto.id,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };

  let settingsStore: Record<string, ProjectSettings> = {
    'proj-a': {
      project_id: 'proj-a',
      updated_at: '2026-01-02T00:00:00Z',
      channel_profile_id: channelArabic.id,
      preset_id: presetReview.id,
      topic_focus: 'Ancient Egypt',
      language: 'Arabic',
      narrator: 'arabic-narrator-v2',
      visual_style: 'Painterly Documentary',
      video_format: '16:9',
      budget_limit_usd: 25,
      upload_destination: 'YouTube',
      stage_modes: { ...presetReview.default_stage_modes },
      stage_params: {
        script: { provider: 'Claude', model: 'Claude-3-5-Sonnet', script_length: '~ 8 minutes' },
      },
    },
    'proj-b': {
      project_id: 'proj-b',
      updated_at: '2026-01-01T00:00:00Z',
      channel_profile_id: channelTech.id,
      preset_id: presetFullAuto.id,
      topic_focus: 'AI Engineering',
      language: 'English',
      narrator: 'en-studio-male',
      visual_style: 'Neon Motion',
      video_format: '9:16',
      budget_limit_usd: 8,
      upload_destination: 'YouTube Shorts',
      stage_modes: { ...presetFullAuto.default_stage_modes },
      stage_params: {
        script: { provider: 'ChatGPT', model: 'GPT-4o', script_length: '~ 3 minutes' },
      },
    },
  };

  const assetsStore: Record<string, ProjectAsset[]> = {
    'proj-a': [
      {
        id: 'asset-a1',
        project_id: 'proj-a',
        asset_type: 'script',
        name: 'Pyramids Draft Script',
        content: 'Ancient stone blocks...',
        metadata: {},
        created_at: '2026-01-02T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
      },
    ],
    'proj-b': [
      {
        id: 'asset-b1',
        project_id: 'proj-b',
        asset_type: 'export',
        name: 'Rust Short Final.mp4',
        content: 'Ready export',
        file_path: '/out/rust.mp4',
        metadata: {},
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
  };

  const channelsDb: ChannelProfile[] = [];
  vi.mocked(apiClient.listChannels).mockImplementation(async () => [...channelsDb]);
  vi.mocked(apiClient.createChannel).mockImplementation(async (payload) => {
    const next: ChannelProfile = {
      id: channelsDb.length === 0 ? channelArabic.id : channelTech.id,
      name: payload.name,
      topic_focus: payload.topic_focus ?? '',
      language: payload.language ?? 'Arabic',
      default_narrator: payload.default_narrator ?? 'arabic-narrator-v2',
      visual_style: payload.visual_style ?? 'Cinematic',
      video_format: payload.video_format ?? '16:9',
      budget_limit_usd: payload.budget_limit_usd ?? 10,
      upload_destination: payload.upload_destination ?? 'YouTube',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    };
    channelsDb.push(next);
    return next;
  });
  vi.mocked(apiClient.listPresets).mockResolvedValue([presetFullAuto, presetReview]);
  vi.mocked(apiClient.listProjects).mockResolvedValue([projA, projB]);
  vi.mocked(apiClient.getProjectSettings).mockImplementation(async (projectId) => settingsStore[projectId]);
  vi.mocked(apiClient.listProjectAssets).mockImplementation(async (projectId) => assetsStore[projectId] ?? []);
  vi.mocked(apiClient.updateProjectSettings).mockImplementation(async (projectId, patch) => {
    const current = settingsStore[projectId];
    const next: ProjectSettings = {
      ...current,
      ...patch,
      stage_modes: { ...current.stage_modes, ...(patch.stage_modes ?? {}) },
      stage_params: {
        ...current.stage_params,
        ...(patch.stage_params
          ? {
              script: {
                ...(current.stage_params.script ?? {}),
                ...(patch.stage_params.script ?? {}),
              },
            }
          : {}),
      },
      updated_at: '2026-01-03T00:00:00Z',
    };
    settingsStore = { ...settingsStore, [projectId]: next };
    return next;
  });

  render(<App />);

  // Wait for initial load on Project A
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Giza Pyramids' })).toBeInTheDocument());

  // Navigate to Channels view and create two channels
  await user.click(screen.getByRole('button', { name: /channels/i }));
  expect(screen.getByRole('heading', { name: /channel profiles/i })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText(/channel name/i), { target: { value: 'Arabic History' } });
  await user.click(screen.getByRole('button', { name: /create channel profile/i }));
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Arabic History' })).toBeInTheDocument());

  fireEvent.change(screen.getByLabelText(/channel name/i), { target: { value: 'English Tech Shorts' } });
  fireEvent.change(screen.getByLabelText(/^language$/i), { target: { value: 'English' } });
  await user.click(screen.getByRole('button', { name: /create channel profile/i }));
  await waitFor(() => expect(screen.getByRole('heading', { name: 'English Tech Shorts' })).toBeInTheDocument());

  // Switching to English Tech Shorts filters projects to Rust Async and switches workflow to Project B
  await user.click(screen.getByRole('button', { name: /workflow/i }));
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Rust Async' })).toBeInTheDocument());

  // Check Project B AgentNodeCard values & Inspector values
  const ideaCardB = screen.getByRole('group', { name: 'Idea' });
  expect(within(ideaCardB).getByText('English')).toBeInTheDocument();
  const exportCardB = screen.getByRole('group', { name: 'Export' });
  expect(within(exportCardB).getByText('YouTube Shorts')).toBeInTheDocument();
  expect(within(exportCardB).getByText(/Auto mode · 1 asset/i)).toBeInTheDocument();
  expect(screen.getByRole('combobox', { name: 'Provider' })).toHaveValue('ChatGPT');

  // Switch back to Arabic History channel -> switches to Project A cleanly with no leakage
  await user.selectOptions(screen.getByLabelText(/active channel/i), channelArabic.id);
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Giza Pyramids' })).toBeInTheDocument());

  const ideaCardA = screen.getByRole('group', { name: 'Idea' });
  expect(within(ideaCardA).getByText('Arabic')).toBeInTheDocument();
  const scriptCardA = screen.getByRole('group', { name: 'Script' });
  expect(within(scriptCardA).getByText('Claude')).toBeInTheDocument();
  expect(within(scriptCardA).getByText(/Approval mode · 1 asset/i)).toBeInTheDocument();
  expect(screen.getByRole('combobox', { name: 'Provider' })).toHaveValue('Claude');

  // Check Project A Assets tab shows ONLY Project A's asset (not Rust Short Final.mp4)
  const mainArea = screen.getByRole('main');
  await user.click(within(mainArea).getByRole('button', { name: /^assets/i }));
  expect(screen.getByText('Pyramids Draft Script')).toBeInTheDocument();
  expect(screen.queryByText('Rust Short Final.mp4')).not.toBeInTheDocument();

  // Override Project A's language in Inspector and verify Project B remains English when switched
  const langInput = screen.getByLabelText(/project language/i);
  fireEvent.change(langInput, { target: { value: 'Spanish' } });
  await waitFor(() =>
    expect(apiClient.updateProjectSettings).toHaveBeenCalledWith('proj-a', { language: 'Spanish' })
  );

  await user.click(within(mainArea).getByRole('button', { name: /^workflow$/i }));
  await waitFor(() => expect(within(screen.getByRole('group', { name: 'Idea' })).getByText('Spanish')).toBeInTheDocument());

  // Switch back to English Tech Shorts -> Project B still has English (not Spanish!)
  await user.selectOptions(screen.getByLabelText(/active channel/i), channelTech.id);
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Rust Async' })).toBeInTheDocument());
  expect(within(screen.getByRole('group', { name: 'Idea' })).getByText('English')).toBeInTheDocument();
  expect(screen.getByRole('combobox', { name: 'Provider' })).toHaveValue('ChatGPT');

  // Project B Assets tab shows ONLY Project B's asset
  await user.click(within(screen.getByRole('main')).getByRole('button', { name: /^assets/i }));
  expect(screen.getByText('Rust Short Final.mp4')).toBeInTheDocument();
  expect(screen.queryByText('Pyramids Draft Script')).not.toBeInTheDocument();
}, 15_000);
