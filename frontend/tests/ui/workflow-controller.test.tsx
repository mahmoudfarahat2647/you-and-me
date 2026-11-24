import { renderHook } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { AGENT_NODE_WIDTH, useWorkflowController } from '../../src/components/workflow/useWorkflowController'
import type { StageRuntimeState } from '../../src/types'

test('builds the six approved stages in order with w-80 width, staggered Y and Bezier connectors', () => {
  const { result } = renderHook(() =>
    useWorkflowController({ selectedStage: 'idea', onSelectStage: () => {} })
  )

  expect(AGENT_NODE_WIDTH).toBe(320)
  expect(result.current.nodes.map((node) => node.data.title)).toEqual([
    'Idea',
    'Script',
    'Voice',
    'Scenes',
    'Edit',
    'Export',
  ])

  const xs = result.current.nodes.map((node) => node.position.x)
  expect(xs).toEqual([...xs].sort((a, b) => a - b))
  expect(new Set(xs).size).toBe(xs.length)

  const ys = result.current.nodes.map((node) => node.position.y)
  expect(new Set(ys).size).toBeGreaterThan(1)

  for (const node of result.current.nodes) {
    expect(node.style?.width).toBe(320)
    expect(node.data.params?.length).toBe(3)
    expect(node.data.toggles?.some((t) => t.id === 'autoMode' && t.label === 'Auto mode')).toBe(true)
  }

  expect(result.current.edges.map((edge) => `${edge.source}->${edge.target}`)).toEqual([
    'idea->script',
    'script->voice',
    'voice->scenes',
    'scenes->edit',
    'edit->export',
  ])
  for (const edge of result.current.edges) {
    expect(edge.type).toBe('default')
    expect(edge.markerEnd).toBeUndefined()
  }
})

test('ports follow the approved stage order without duplicates', () => {
  const { result } = renderHook(() =>
    useWorkflowController({ selectedStage: 'idea', onSelectStage: () => {} })
  )
  const [idea, script, , , , exportNode] = result.current.nodes

  expect(idea.data.showInputPort).toBe(false)
  expect(idea.data.showOutputPort).toBe(true)
  expect(script.data.showInputPort).toBe(true)
  expect(script.data.inputLabel).toBe('Topic')
  expect(script.data.outputLabel).toBe('Script')
  expect(exportNode.data.showInputPort).toBe(true)
  expect(exportNode.data.showOutputPort).toBe(false)
})

test('maps richer stage states, animates running edges, and wires run/auto handlers', () => {
  const onRunStage = vi.fn()
  const onToggleStageAuto = vi.fn()
  const stageStates: Partial<Record<'idea' | 'script' | 'voice' | 'scenes', StageRuntimeState>> = {
    idea: { status: 'running' },
    script: { status: 'completed' },
    voice: { status: 'failed', errorMessage: 'Provider returned 500.' },
    scenes: { status: 'pending', mode: 'off' },
  }

  const { result } = renderHook(() =>
    useWorkflowController({
      selectedStage: 'idea',
      stageStates,
      onSelectStage: () => {},
      onRunStage,
      onToggleStageAuto,
    })
  )
  const [idea, script, voice, scenes, edit, exportNode] = result.current.nodes

  expect(idea.data).toMatchObject({ status: 'running', statusLabel: 'Running', footer: 'Auto mode' })
  expect(script.data).toMatchObject({ status: 'completed', statusLabel: 'Completed' })
  expect(voice.data).toMatchObject({
    status: 'error',
    statusLabel: 'Failed',
    errorMessage: 'Provider returned 500.',
  })
  expect(scenes.data).toMatchObject({ status: 'idle', statusLabel: 'Idle', disabled: true, footer: 'Execution off' })
  expect(edit.data).toMatchObject({ status: 'idle', statusLabel: 'Idle' })
  expect(exportNode.data).toMatchObject({ status: 'idle', statusLabel: 'Idle' })

  expect(result.current.edges[0].animated).toBe(true)
  expect(result.current.edges[1].animated).toBe(false)
  expect(result.current.edges[1].style?.strokeDasharray).toBeUndefined()
  expect(result.current.edges[2].style?.stroke).toBe('#f43f5e')

  script.data.onRunNode?.()
  expect(onRunStage).toHaveBeenCalledWith('script')

  const scenesAutoToggle = scenes.data.toggles?.find((t) => t.id === 'autoMode')
  expect(scenesAutoToggle?.checked).toBe(false)
  scenesAutoToggle?.onCheckedChange(true)
  expect(onToggleStageAuto).toHaveBeenCalledWith('scenes', true)
})

test('selection is sourced from the controller and clicking a card selects its stage', () => {
  const onSelectStage = vi.fn()
  const { result } = renderHook(() =>
    useWorkflowController({ selectedStage: 'voice', onSelectStage })
  )

  expect(result.current.nodes.filter((node) => node.data.selected).map((node) => node.id)).toEqual(['voice'])

  result.current.nodes[3].data.onSelect?.()
  expect(onSelectStage).toHaveBeenCalledWith('scenes')
})

test('nodes omit per-node draggable override so canvas interaction mode controls dragging', () => {
  const { result } = renderHook(() =>
    useWorkflowController({ selectedStage: 'idea', onSelectStage: () => {} })
  )

  for (const node of result.current.nodes) {
    expect(node.draggable).toBeUndefined()
  }
})
