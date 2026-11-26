import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { WorkflowCanvas } from '../../src/components/WorkflowCanvas'
import type { Project, StageRuntimeState } from '../../src/types'

const project: Project = {
  id: 'project-1',
  name: 'The Pyramids Mystery',
  description: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const stageStates: Partial<Record<'idea' | 'script' | 'voice' | 'scenes', StageRuntimeState>> = {
  idea: { status: 'running' },
  script: { status: 'completed' },
  voice: { status: 'failed', errorMessage: 'Provider returned 500.' },
  scenes: { status: 'pending', mode: 'off' },
}

function renderCanvas(selectedStage = 'idea', customStates?: Partial<Record<'idea' | 'script' | 'voice' | 'scenes', StageRuntimeState>>, onRunStage = vi.fn()) {
  return render(
    <WorkflowCanvas
      project={project}
      onOpenProjectsModal={() => {}}
      selectedStage={selectedStage}
      onSelectStage={() => {}}
      stageStates={customStates}
      onRunStage={onRunStage}
    />
  )
}

test('renders all six stages with params, Auto mode toggle, and footer run button', () => {
  renderCanvas('idea')

  for (const name of ['Idea', 'Script', 'Voice', 'Scenes', 'Edit', 'Export']) {
    const card = screen.getByRole('group', { name })
    expect(card).toBeInTheDocument()
    expect(within(card).getByRole('switch', { name: 'Auto mode' })).toBeChecked()
    expect(within(card).getByRole('button', { name: 'Run node' })).toBeEnabled()
  }
  expect(document.querySelectorAll('.react-flow__node')).toHaveLength(6)
})

test('toggling Auto mode off disables that phase and updates its footer', () => {
  renderCanvas('idea')

  const scriptCard = screen.getByRole('group', { name: 'Script' })
  const autoSwitch = within(scriptCard).getByRole('switch', { name: 'Auto mode' })

  fireEvent.click(autoSwitch)

  expect(autoSwitch).not.toBeChecked()
  expect(within(scriptCard).getByText('Execution off')).toBeInTheDocument()
  expect(within(scriptCard).getByRole('button', { name: 'Run node' })).toBeDisabled()
})

test('clicking Run node delegates execution and waits for caller-supplied status', () => {
  const onRunStage = vi.fn()
  renderCanvas('idea', undefined, onRunStage)

  const ideaCard = screen.getByRole('group', { name: 'Idea' })
  fireEvent.click(within(ideaCard).getByRole('button', { name: 'Run node' }))

  expect(onRunStage).toHaveBeenCalledOnce()
  expect(onRunStage).toHaveBeenCalledWith('idea')
  expect(within(ideaCard).getByRole('status')).toHaveTextContent('Idle')
})

test('maps richer stage states to the four visual states and truthful labels', () => {
  renderCanvas('idea', stageStates)

  const cases = [
    ['Idea', 'Running'],
    ['Script', 'Completed'],
    ['Voice', 'Failed'],
    ['Scenes', 'Idle'],
    ['Edit', 'Idle'],
    ['Export', 'Idle'],
  ] as const

  for (const [name, label] of cases) {
    const card = screen.getByRole('group', { name })
    expect(within(card).getByRole('status')).toHaveTextContent(label)
  }

  const voice = screen.getByRole('group', { name: 'Voice' })
  expect(voice).toHaveAttribute('data-status', 'error')
  expect(within(voice).getByRole('alert')).toHaveTextContent('Provider returned 500.')
  expect(within(screen.getByRole('group', { name: 'Scenes' })).getByText('Execution off')).toBeInTheDocument()
})

test('the selected stage shows the supplied selection ring and others do not', () => {
  renderCanvas('voice', stageStates)

  expect(screen.getByRole('group', { name: 'Voice' })).toHaveAttribute('data-selected', 'true')
  expect(screen.getByRole('group', { name: 'Voice' })).toHaveAttribute('aria-current', 'step')
  expect(screen.getByRole('group', { name: 'Idea' })).not.toHaveAttribute('data-selected')
  expect(screen.getByRole('group', { name: 'Idea' })).not.toHaveAttribute('aria-current')
})

test('each card exposes React Flow handles aligned to its visible ports with no duplicates', () => {
  renderCanvas('idea', stageStates)

  const expectations: Record<string, { handles: number; ports: number }> = {
    idea: { handles: 1, ports: 1 },
    script: { handles: 2, ports: 2 },
    voice: { handles: 2, ports: 2 },
    scenes: { handles: 2, ports: 2 },
    edit: { handles: 2, ports: 2 },
    export: { handles: 1, ports: 1 },
  }

  for (const [stageId, expected] of Object.entries(expectations)) {
    const node = document.querySelector(`.react-flow__node[data-id="${stageId}"]`)
    expect(node).not.toBeNull()
    const handles = node!.querySelectorAll('.react-flow__handle')
    const visiblePorts = node!.querySelectorAll('[class*="group/port"]')
    expect(handles).toHaveLength(expected.handles)
    expect(visiblePorts).toHaveLength(expected.ports)

    for (const handle of Array.from(handles)) {
      expect(handle.className).toContain('agent-node-handle')
      expect(handle.className).toContain('!bg-transparent')
      expect((handle as HTMLElement).style.top).toBe('36px')
    }
  }
})

test('banner appears when no stage states are supplied and hides when active states exist', () => {
  const { rerender } = render(
    <WorkflowCanvas
      project={project}
      onOpenProjectsModal={() => {}}
      selectedStage="idea"
      onSelectStage={() => {}}
    />
  )
  expect(screen.getByText(/no workflow progress available/i)).toBeInTheDocument()

  rerender(
    <WorkflowCanvas
      project={project}
      onOpenProjectsModal={() => {}}
      selectedStage="idea"
      onSelectStage={() => {}}
      stageStates={stageStates}
    />
  )
  expect(screen.queryByText(/no workflow progress available/i)).not.toBeInTheDocument()
})

test('execution mode is shown independently of status', () => {
  renderCanvas('idea', stageStates)

  const ideaCard = screen.getByRole('group', { name: 'Idea' })
  expect(within(ideaCard.querySelector('footer')!).getByText('Auto mode')).toBeInTheDocument()
  expect(within(screen.getByRole('group', { name: 'Scenes' })).getByText('Execution off')).toBeInTheDocument()
  expect(within(ideaCard).getByRole('status')).toHaveTextContent('Running')
})

test('clicking a stage card dispatches onSelectStage once and pan mode disables node dragging', () => {
  const onSelectStage = vi.fn()
  render(
    <WorkflowCanvas
      project={project}
      onOpenProjectsModal={() => {}}
      selectedStage="idea"
      onSelectStage={onSelectStage}
      stageStates={stageStates}
    />
  )

  fireEvent.click(screen.getByRole('group', { name: 'Script' }))
  expect(onSelectStage).toHaveBeenCalledTimes(1)
  expect(onSelectStage).toHaveBeenCalledWith('script')

  const ideaNode = document.querySelector('.react-flow__node[data-id="idea"]')
  expect(ideaNode?.className).toContain('draggable')

  fireEvent.click(screen.getByRole('button', { name: 'Pan' }))
  expect(screen.getByRole('button', { name: 'Pan' })).toHaveAttribute('aria-pressed', 'true')
  expect(ideaNode?.className).not.toContain('draggable')
})
