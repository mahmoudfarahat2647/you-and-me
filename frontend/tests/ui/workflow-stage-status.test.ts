import { expect, test } from 'vitest'
import { mapStageRuntimeState } from '../../src/lib/workflow/stageStatus'
import type { StageRunStatus } from '../../src/types'

test.each([
  ['pending', 'idle', 'Idle'],
  ['queued', 'idle', 'Queued'],
  ['running', 'running', 'Running'],
  ['in_progress', 'running', 'Running'],
  ['awaiting_approval', 'idle', 'Awaiting approval'],
  ['completed', 'completed', 'Completed'],
  ['failed', 'error', 'Failed'],
  ['error', 'error', 'Error'],
  ['cancelled', 'idle', 'Cancelled'],
  ['skipped', 'idle', 'Skipped'],
] as const)('maps backend status %s to visual %s with the truthful label %s', (runStatus, visual, label) => {
  const mapped = mapStageRuntimeState({ status: runStatus })
  expect(mapped.status).toBe(visual)
  expect(mapped.statusLabel).toBe(label)
})

test('a missing stage state is truthfully idle', () => {
  expect(mapStageRuntimeState()).toMatchObject({
    status: 'idle',
    statusLabel: 'Idle',
    mode: 'auto',
    disabled: false,
    footer: 'Auto mode',
  })
})

test('execution mode never changes the reported status', () => {
  const modes = ['auto', 'manual', 'approval', 'off'] as const

  for (const mode of modes) {
    const mapped = mapStageRuntimeState({ status: 'completed', mode })
    expect(mapped.status).toBe('completed')
    expect(mapped.statusLabel).toBe('Completed')
  }
})

test('off mode disables running without pretending the node failed', () => {
  expect(mapStageRuntimeState({ status: 'pending', mode: 'off' })).toMatchObject({
    status: 'idle',
    disabled: true,
    footer: 'Execution off',
  })
})

test.each(['queued', 'awaiting_approval'] as const)('%s blocks an immediate rerun', (status) => {
  expect(mapStageRuntimeState({ status }).disabled).toBe(true)
})

test('error messages are only surfaced for error visuals', () => {
  expect(mapStageRuntimeState({ status: 'failed', errorMessage: 'Provider returned 500.' }).errorMessage).toBe(
    'Provider returned 500.'
  )
  expect(mapStageRuntimeState({ status: 'error', errorMessage: 'Provider returned 500.' }).errorMessage).toBe(
    'Provider returned 500.'
  )
  expect(mapStageRuntimeState({ status: 'completed', errorMessage: 'Stale message.' }).errorMessage).toBeUndefined()
  expect(mapStageRuntimeState({ status: 'running', errorMessage: 'Stale message.' }).errorMessage).toBeUndefined()
})

test('a caller-supplied footer replaces the mode label', () => {
  expect(mapStageRuntimeState({ status: 'completed', footer: '312 words' }).footer).toBe('312 words')
})

test('every backend status is mapped exactly once', () => {
  const statuses: StageRunStatus[] = [
    'pending',
    'queued',
    'running',
    'in_progress',
    'awaiting_approval',
    'completed',
    'failed',
    'error',
    'cancelled',
    'skipped',
  ]

  for (const status of statuses) {
    const mapped = mapStageRuntimeState({ status })
    expect(['idle', 'running', 'completed', 'error']).toContain(mapped.status)
    expect(mapped.statusLabel.length).toBeGreaterThan(0)
  }
})
