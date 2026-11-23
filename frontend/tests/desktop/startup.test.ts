import { afterEach, expect, it, vi } from 'vitest';
import { checkBackendHealth } from '../../src/api/client';

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

it('rejects malformed health responses without retrying', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
  );
  await expect(checkBackendHealth()).rejects.toThrow(/invalid/i);
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it('recovers when the backend initially refuses connections', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch')
    .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'ok', app: 'desktop', version: '1' })));
  await expect(checkBackendHealth()).resolves.toMatchObject({ status: 'ok' });
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
