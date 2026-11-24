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

it('toggles the right inspector panel open and collapsed from the button inside the right panel', async () => {
  vi.mocked(listProjects).mockResolvedValueOnce([
    {
      id: 'proj-1',
      name: 'Pyramids Documentary',
      description: '',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ]);

  render(<App />);

  const rightPanel = await screen.findByRole('complementary', { name: /right panel/i });
  const collapseButton = screen.getByRole('button', { name: /collapse right panel/i });
  expect(rightPanel).toContainElement(collapseButton);
  expect(collapseButton).toHaveAttribute('aria-expanded', 'true');
  expect(rightPanel.className).toContain('w-72');
  expect(screen.getByRole('combobox', { name: 'Provider' })).toBeInTheDocument();

  fireEvent.click(collapseButton);

  const expandButton = screen.getByRole('button', { name: /expand right panel/i });
  expect(rightPanel).toContainElement(expandButton);
  expect(expandButton).toHaveAttribute('aria-expanded', 'false');
  expect(rightPanel.className).toContain('w-11');
  expect(screen.queryByRole('combobox', { name: 'Provider' })).not.toBeInTheDocument();

  fireEvent.click(expandButton);

  expect(screen.getByRole('button', { name: /collapse right panel/i })).toHaveAttribute('aria-expanded', 'true');
  expect(rightPanel.className).toContain('w-72');
  expect(screen.getByRole('combobox', { name: 'Provider' })).toBeInTheDocument();
});
