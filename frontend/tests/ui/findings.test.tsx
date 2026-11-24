import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { CreateProjectDialog } from '../../src/components/CreateProjectDialog'
import { ProjectListModal } from '../../src/components/ProjectListModal'
import { WorkflowCanvas } from '../../src/components/WorkflowCanvas'
import { Inspector } from '../../src/components/Inspector'
import type { Project } from '../../src/types'

const project: Project = {
  id: '12345678-long-id',
  name: 'A very long project name for keyboard selection',
  description: 'A description',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

afterEach(() => vi.unstubAllGlobals())

test('project open and copy are separate keyboard-accessible actions', async () => {
  const user = userEvent.setup()
  const selected = vi.fn()
  render(<ProjectListModal isOpen onClose={() => {}} projects={[project]} onSelectProject={selected} onOpenCreateDialog={() => {}} />)
  const copy = screen.getByRole('button', { name: /copy.*id.*A very long project/i })
  copy.focus()
  await user.keyboard('{Enter}')
  expect(await navigator.clipboard.readText()).toBe(project.id)
  expect(selected).not.toHaveBeenCalled()
  const open = screen.getByRole('button', { name: /open.*A very long project/i })
  open.focus()
  await user.keyboard('{Enter}')
  expect(selected).toHaveBeenCalledWith(project)
  expect(screen.getByRole('textbox', { name: /search projects/i })).toBeInTheDocument()
})

test('failed creation retains labelled input and reports unknown errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(null))
  const user = userEvent.setup()
  render(<CreateProjectDialog isOpen onClose={() => {}} onProjectCreated={() => {}} />)
  const name = screen.getByRole('textbox', { name: /project name/i })
  const description = screen.getByRole('textbox', { name: /description/i })
  await user.type(name, 'My project')
  await user.type(description, 'My notes')
  await user.click(screen.getByRole('button', { name: /create project/i }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/failed to create project/i)
  expect(name).toHaveValue('My project')
  expect(description).toHaveValue('My notes')
})

test('pending creation cannot submit twice even via form submission', async () => {
  let rejectRequest: (reason: Error) => void = () => {}
  const fetcher = vi.fn(() => new Promise<Response>((_, reject) => { rejectRequest = reject }))
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<CreateProjectDialog isOpen onClose={() => {}} onProjectCreated={() => {}} />)
  await user.type(screen.getByRole('textbox', { name: /project name/i }), 'My project')
  const submit = screen.getByRole('button', { name: /create project/i })
  await user.click(submit)
  expect(submit).toBeDisabled()
  fireEvent.submit(submit.closest('form')!)
  expect(fetcher).toHaveBeenCalledTimes(1)
  rejectRequest(new Error('offline'))
  expect(await screen.findByRole('alert')).toHaveTextContent('offline')
})

test('workflow exposes keyboard stage selection without invented progress and names toolbar controls', async () => {
  const user = userEvent.setup()
  const selected = vi.fn()
  render(<WorkflowCanvas project={project} onOpenProjectsModal={() => {}} selectedStage="idea" onSelectStage={selected} />)
  const script = screen.getByRole('group', { name: 'Script' })
  script.focus()
  await user.keyboard('{Enter}')
  expect(selected).toHaveBeenCalledWith('script')
  expect(screen.queryByLabelText(/completed|in progress/i)).not.toBeInTheDocument()
  expect(screen.getByText(/no workflow progress/i)).toBeInTheDocument()
  for (const name of ['Select', 'Pan', 'Fit view', 'Zoom out', 'Zoom in']) {
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  }
})

test('inspector settings are labelled and logs do not claim an event occurred', async () => {
  const user = userEvent.setup()
  render(<Inspector onClose={() => {}} />)
  expect(screen.getByRole('button', { name: /close inspector/i })).toBeInTheDocument()
  for (const name of ['Provider', 'Model', 'Script Length']) {
    expect(screen.getByRole('combobox', { name })).toBeInTheDocument()
  }
  await user.click(screen.getByRole('button', { name: /advanced options/i }))
  expect(screen.getByRole('textbox', { name: /tone & audience/i })).toBeInTheDocument()
  expect(screen.getByRole('slider', { name: /temperature/i })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'logs' }))
  await waitFor(() => expect(screen.getByText(/no logs/i)).toBeInTheDocument())
  expect(screen.queryByText(/stage initialized/i)).not.toBeInTheDocument()
})
