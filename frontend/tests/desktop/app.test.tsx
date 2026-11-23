import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { App } from '../../src/App';
import { listProjects, restartTauriBackend } from '../../src/api/client';
import { StrictMode } from 'react';
import { checkBackendHealth } from '../../src/api/client';

vi.mock('../../src/api/client', () => ({
  checkBackendHealth: vi.fn().mockResolvedValue({ status: 'ok', app: 'test', version: '1' }),
  listProjects: vi.fn(() => new Promise(() => {})),
  getTauriBackendStatus: vi.fn().mockResolvedValue(null),
  restartTauriBackend: vi.fn().mockResolvedValue(null),
}));

it('stays in the connecting state until projects have loaded', async () => {
  render(<App />);
  await vi.waitFor(() => expect(screen.getByText(/connecting to local backend/i)).toBeInTheDocument());
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(screen.getByText(/connecting to local backend/i)).toBeInTheDocument();
  expect(screen.queryByText(/no project open/i)).not.toBeInTheDocument();
});

it('reports an unknown project-loading failure instead of crashing', async () => {
  vi.mocked(listProjects).mockRejectedValueOnce(null);
  render(<App />);
  expect(await screen.findByText(/failed to connect to local backend/i)).toBeInTheDocument();
});

it('does not start duplicate retries while a restart is pending', async () => {
  vi.mocked(listProjects).mockRejectedValueOnce(new Error('offline'));
  vi.mocked(restartTauriBackend).mockImplementationOnce(() => new Promise(() => {}));
  render(<App />);
  const retry = await screen.findByRole('button', { name: /retry connection/i });
  fireEvent.click(retry);
  fireEvent.click(retry);
  expect(restartTauriBackend).toHaveBeenCalledTimes(1);
});

it('does not start duplicate health checks in strict mode', async () => {
  vi.mocked(checkBackendHealth).mockClear();
  vi.mocked(listProjects).mockImplementation(() => new Promise(() => {}));
  render(<StrictMode><App /></StrictMode>);
  await vi.waitFor(() => expect(listProjects).toHaveBeenCalled());
  expect(checkBackendHealth).toHaveBeenCalledTimes(1);
});
