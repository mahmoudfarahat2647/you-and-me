import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { App } from '../../src/App';
import type { StageId, WorkflowJob, WorkflowSceneItem, WorkflowStageState, WorkflowStateResponse } from '../../src/types';
import type { ProviderConfigSummary, SpendPreflightResult } from '../../src/types/providers';

const project = {
  id: 'workflow-project', name: 'Workflow integration', description: '',
  created_at: '2026-05-02T00:00:00Z', updated_at: '2026-05-02T00:00:00Z',
};

vi.mock('../../src/api/client', async (importOriginal) => ({
  ...await importOriginal<typeof import('../../src/api/client')>(),
  checkBackendHealth: async () => ({ status: 'ok' }),
  listProjects: async () => [project],
  listChannels: async () => [],
  listPresets: async () => [],
  getProjectSettings: async () => null,
  listProjectAssets: async () => [],
  getProjectMedia: async () => ({ project_id: project.id, clips: [], audio: null, latest_export: null }),
}));

const stageIds: StageId[] = ['idea', 'script', 'voice', 'scenes', 'edit', 'export'];
const stageLabels = ['Idea', 'Script', 'Voice', 'Scenes', 'Edit', 'Export'];
const workflowPath = `/projects/${project.id}/workflow`;
const timestamp = '2026-05-02T12:00:00Z';
let clockTick = 0;

function snapshot(status: WorkflowJob['status'], overrides: Partial<Record<StageId, Partial<WorkflowStageState>>> = {}): WorkflowJob {
  return {
    id: 'job-1', project_id: project.id, status, stage_order: stageIds,
    created_at: timestamp, updated_at: new Date(Date.parse(timestamp) + ++clockTick * 1000).toISOString(),
    pause_requested: false, cancel_requested: status === 'canceled',
    stages: stageIds.map((stage_id) => ({
      stage_id, mode: 'auto', status: 'pending', dependencies: [], required: true,
      artifact_type: stage_id, params: {}, attempt_count: 0, items: [], ...overrides[stage_id],
    })),
  };
}

function mockServer(initialJob: WorkflowJob | null = null, providers: ProviderConfigSummary[] = []) {
  let response: WorkflowStateResponse = { project_id: project.id, job: initialJob, logs: [] };
  const handlers = new Map<string, (payload: unknown) => void | Promise<void>>();
  const requests: Array<{ route: string; payload: unknown }> = [];
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    const path = new URL(url).pathname.replace(/^\/api/, '');
    if (path === '/providers') return Response.json(providers);
    if (path === `/projects/${project.id}/spend`) {
      return Response.json({ budget: { project_id: project.id, budget_limit_usd: 10, remaining_budget_usd: 10 }, requests: [] });
    }
    if (path === workflowPath && init?.method === 'GET') return Response.json(response);
    const route = path.slice(workflowPath.length);
    const handler = handlers.get(route);
    if (!path.startsWith(workflowPath) || !handler) return new Response(null, { status: 404 });
    const payload: unknown = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined;
    requests.push({ route, payload });
    await handler(payload);
    return Response.json(response);
  });
  return {
    handlers, requests,
    update(job: WorkflowJob, logs = response.logs) {
      response = { ...response, job, logs };
    },
  };
}

function card(name: string) {
  return within(screen.getByRole('group', { name }));
}

function runButton(name: string) {
  return screen.getByRole('button', { name, exact: true });
}

vi.setConfig({ testTimeout: 15000 });

beforeEach(() => { clockTick = 0; });
afterEach(() => { vi.unstubAllGlobals(); });

test('runs, pauses an active submission, resumes, reconciles, and cancels using persisted workflow state', async () => {
  const server = mockServer();
  let finishRun: () => void = () => {};
  server.handlers.set('/run', async () => {
    server.update(snapshot('running', { idea: { status: 'running' } }));
    await new Promise<void>((resolve) => { finishRun = resolve; });
  });
  server.handlers.set('/pause', () => {
    server.update({ ...snapshot('paused', { idea: { status: 'completed' } }), pause_requested: true });
    finishRun();
  });
  server.handlers.set('/resume', () => server.update(snapshot('running', { script: { status: 'running' } })));
  server.handlers.set('/reconcile', () => server.update(snapshot('needs_reconciliation', { script: { status: 'unknown_outcome' } })));
  server.handlers.set('/cancel', () => server.update(snapshot('canceled', { script: { status: 'canceled' } })));

  render(<App />);
  await waitFor(() => expect(runButton('Run Workflow')).toBeEnabled());
  await userEvent.click(runButton('Run Workflow'));
  await waitFor(() => expect(server.requests).toEqual([{ route: '/run', payload: {} }]));
  const pause = await within(screen.getByRole('main')).findByRole('button', { name: 'Pause' }, {}, { timeout: 4000 });
  expect(card('Idea').getByRole('status')).toHaveTextContent('Running');
  expect(card('Script').getByRole('button', { name: 'Run node' })).toBeDisabled();
  await userEvent.click(pause);
  await waitFor(() => expect(runButton('Resume Workflow')).toBeEnabled());
  await waitFor(() => expect(card('Idea').getByRole('status')).toHaveTextContent('Completed'));
  await userEvent.click(runButton('Resume Workflow'));
  await userEvent.click(await screen.findByRole('button', { name: 'Reconcile' }));
  await waitFor(() => expect(card('Script').getByRole('status')).toHaveTextContent('Unknown outcome'));
  await userEvent.click(runButton('Cancel'));
  await waitFor(() => expect(card('Script').getByRole('status')).toHaveTextContent('Canceled'));
  expect(server.requests.map(({ route }) => route)).toEqual(['/run', '/pause', '/resume', '/reconcile', '/cancel']);
});

test('persists modes, submits manual output, rejects with a reason, retries, edits and approves', async () => {
  const server = mockServer();
  const manual = { mode: 'manual', status: 'waiting_manual' } as const;
  const approval = {
    mode: 'approval', status: 'awaiting_approval', attempt_count: 1,
    artifact: {
      artifact_id: 'draft-script', stage_id: 'script', artifact_type: 'script',
      data: { text: 'Draft script' }, schema_version: '1.0', compatible: true, stale: false,
    },
  } as const;
  server.handlers.set('/stages/idea/mode', () => {});
  server.handlers.set('/stages/idea/run', () => server.update(snapshot('paused', { idea: manual })));
  server.handlers.set('/stages/idea/manual', () => server.update(snapshot('paused', {
    idea: { mode: 'manual', status: 'completed' }, script: approval,
  })));
  server.handlers.set('/stages/script/approve', (payload) => {
    const rejected = typeof payload === 'object' && payload !== null && 'approved' in payload && !payload.approved;
    server.update(snapshot(rejected ? 'paused' : 'completed', {
      script: { ...approval, status: rejected ? 'failed' : 'completed', ...(rejected && { error: 'Needs a clearer opening' }) },
    }), rejected ? [] : [{
      id: 'persisted-log', job_id: 'job-1', project_id: project.id, stage_id: 'script',
      level: 'info', message: 'Script approval saved.', created_at: timestamp,
    }]);
  });
  server.handlers.set('/stages/script/retry', () => server.update(snapshot('paused', {
    script: { ...approval, attempt_count: 2 },
  })));

  render(<App />);
  fireEvent.keyDown(await screen.findByRole('group', { name: 'Idea' }), { key: 'Enter' });
  await waitFor(() => expect(runButton('Manual')).toBeEnabled());
  await userEvent.click(runButton('Manual'));
  await waitFor(() => expect(server.requests[0]).toEqual({ route: '/stages/idea/mode', payload: { mode: 'manual' } }));
  await waitFor(() => expect(card('Idea').getByRole('button', { name: 'Run node' })).toBeEnabled());
  await userEvent.click(card('Idea').getByRole('button', { name: 'Run node' }));
  const manualOutput = await screen.findByRole('textbox', { name: 'Manual output' });
  expect(runButton('Submit Manual Output')).toBeDisabled();
  fireEvent.change(manualOutput, { target: { value: 'Lighthouse of Alexandria' } });
  await userEvent.click(runButton('Submit Manual Output'));

  const review = await screen.findByRole('textbox', { name: 'Review or edit output' });
  expect(review).toHaveValue('Draft script');
  expect(runButton('Approve')).toBeEnabled();
  expect(runButton('Reject')).toBeDisabled();
  fireEvent.change(screen.getByRole('textbox', { name: 'Rejection reason' }), { target: { value: 'Needs a clearer opening' } });
  await userEvent.click(runButton('Reject'));
  await userEvent.click(await card('Script').findByRole('button', { name: 'Retry' }));
  fireEvent.change(await screen.findByRole('textbox', { name: 'Review or edit output' }), { target: { value: 'Revised script' } });
  await userEvent.click(runButton('Edit & Approve'));
  await waitFor(() => expect(card('Script').getByRole('status')).toHaveTextContent('Completed'));
  await userEvent.click(within(screen.getByRole('complementary', { name: 'Right panel' })).getByRole('button', { name: 'logs' }));
  expect(screen.getByText('Script approval saved.')).toBeInTheDocument();
  expect(server.requests.slice(1)).toEqual([
    { route: '/stages/idea/run', payload: undefined },
    { route: '/stages/idea/manual', payload: { content: 'Lighthouse of Alexandria' } },
    { route: '/stages/script/approve', payload: { approved: false, reason: 'Needs a clearer opening' } },
    { route: '/stages/script/retry', payload: undefined },
    { route: '/stages/script/approve', payload: { approved: true, edited_content: 'Revised script' } },
  ]);
});

test('saves one scene and asks the existing job to rerun only stages marked stale by the API', async () => {
  const scenes: WorkflowSceneItem[] = [
    { item_id: 'scene-a', status: 'completed', input_data: { title: 'Opening', prompt: 'Wide shot' } },
    { item_id: 'scene-b', status: 'completed', input_data: { title: 'Closing', prompt: 'Fade out' } },
  ];
  const completed = Object.fromEntries(stageIds.map((id) => [id, { status: 'completed', attempt_count: 1 }]));
  const initial = snapshot('completed', { ...completed, scenes: { ...completed.scenes, items: scenes } });
  const server = mockServer(initial);
  const secondScene: WorkflowSceneItem = { ...scenes[1], input_data: { title: 'Closing', prompt: 'Hold on the harbor' } };
  let paused: WorkflowJob;
  server.handlers.set('/scenes/scene-b', () => {
    paused = {
      ...snapshot('paused'),
      stages: initial.stages.map((stage) => {
        if (stage.stage_id === 'scenes') return { ...stage, status: 'stale', items: [scenes[0], { ...secondScene, status: 'stale' }] };
        return ['edit', 'export'].includes(stage.stage_id) ? { ...stage, status: 'stale' } : stage;
      }),
    };
    server.update(paused);
  });
  server.handlers.set('/resume', () => server.update({
    ...snapshot('completed'),
    stages: paused.stages.map((stage) => stage.status === 'stale'
      ? { ...stage, status: 'completed', attempt_count: stage.attempt_count + 1,
          items: stage.stage_id === 'scenes' ? [scenes[0], secondScene] : stage.items }
      : stage),
  }));

  render(<App />);
  await waitFor(() => expect(card('Scenes').getByRole('status')).toHaveTextContent('Completed'));
  fireEvent.keyDown(screen.getByRole('group', { name: 'Scenes' }), { key: 'Enter' });
  const opening = within(await screen.findByRole('group', { name: 'Opening' }));
  const closing = within(screen.getByRole('group', { name: 'Closing' }));
  expect(opening.getByRole('button', { name: 'Save Scene' })).toBeDisabled();
  fireEvent.change(closing.getByRole('textbox', { name: 'Scene prompt' }), { target: { value: 'Hold on the harbor' } });
  await userEvent.click(closing.getByRole('button', { name: 'Save Scene' }));
  const rerun = await screen.findByRole('button', { name: 'Rerun Affected Stages' });
  expect(opening.getByText('completed')).toBeInTheDocument();
  expect(within(screen.getByRole('group', { name: 'Closing' })).getByText('stale')).toBeInTheDocument();
  for (const name of stageLabels.slice(0, 3)) expect(card(name).getByRole('status')).toHaveTextContent('Completed');
  for (const name of stageLabels.slice(3)) expect(card(name).getByRole('status')).toHaveTextContent('Stale');
  await userEvent.click(rerun);
  await waitFor(() => expect(card('Export').getByRole('status')).toHaveTextContent('Completed'));
  expect(server.requests).toEqual([
    { route: '/scenes/scene-b', payload: { prompt: 'Hold on the harbor', notes: '' } },
    { route: '/resume', payload: undefined },
  ]);
  expect(within(screen.getByRole('group', { name: 'Closing' })).getByRole('textbox', { name: 'Scene prompt' }))
    .toHaveValue('Hold on the harbor');
});

test.each(['Approve & Submit', 'Switch to Manual'])('shows a paused spend guard and handles %s', async (action) => {
  const provider: ProviderConfigSummary = {
    id: 'provider-a', name: 'Verified Gemini', provider_type: 'gemini', base_url: 'https://example.test',
    credential_ref: 'vault-ref-fixture', credential_preview: 'masked-credential-fixture', credential_status: 'stored',
    connection_status: 'verified', supported_capabilities: ['text_generation'], verified_models: ['gemini-verified'],
    selected_model: 'gemini-verified', last_error: null, last_tested_at: timestamp, created_at: timestamp, updated_at: timestamp,
  };
  const preflight: SpendPreflightResult = {
    allowed: false, decision: 'pause_unknown_cost', requires_user_approval: true, allows_manual_fallback: true,
    message: 'Estimated cost is unknown.', project_id: project.id, stage_run_id: 'job-1:script', request_key: 'job-1:script:1',
    provider_id: provider.id, reservation_id: null, external_request_id: null, external_job_id: null,
    estimated_cost_usd: null, reserved_amount_usd: 0, outstanding_reservations_usd: 0, remaining_budget_usd: 10,
    budget_limit_usd: 10, spent_usd: 0, attempts_used: 0, max_retries: 2, available_actions: ['approve_and_submit', 'switch_to_manual'],
  };
  const server = mockServer({
    ...snapshot('paused', { script: { params: { provider_id: provider.id, api_key: 'never-render-this-fixture' } } }),
    budget_block: { stage_id: 'script', preflight },
  }, [provider]);
  server.handlers.set('/resume', () => server.update(snapshot('completed', { script: { status: 'completed' } })));
  server.handlers.set('/stages/script/mode', () => server.update(snapshot('paused', { script: { mode: 'manual' } })));

  render(<App />);
  expect(await screen.findByText('Spend paused before submission')).toBeInTheDocument();
  expect(await card('Script').findByText('gemini-verified')).toBeInTheDocument();
  expect(card('Script').getByText('Budget blocked · unknown cost')).toBeInTheDocument();
  expect(card('Script').getByRole('button', { name: 'Run node' })).toBeDisabled();
  expect(screen.queryByText(/never-render-this-fixture|vault-ref-fixture|masked-credential-fixture/)).not.toBeInTheDocument();
  await userEvent.click(runButton(action));
  await waitFor(() => expect(screen.queryByText('Spend paused before submission')).not.toBeInTheDocument());
  if (action === 'Switch to Manual') {
    expect(server.requests).toEqual([{ route: '/stages/script/mode', payload: { mode: 'manual' } }]);
    expect(screen.getByRole('textbox', { name: 'Manual output' })).toBeInTheDocument();
  } else {
    expect(server.requests).toEqual([{ route: '/resume', payload: { approve_budget_request_key: preflight.request_key } }]);
    expect(card('Script').getByRole('status')).toHaveTextContent('Completed');
  }
  await userEvent.click(runButton('Providers'));
  expect(screen.getByRole('heading', { name: 'Providers & Protected Credentials' })).toBeInTheDocument();
  expect(screen.getByText(provider.name)).toBeInTheDocument();
});
