import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi, afterEach } from 'vitest'
import { CreateProjectDialog } from '../../src/components/CreateProjectDialog'
import { Inspector } from '../../src/components/Inspector'
import { WorkflowCanvas } from '../../src/components/WorkflowCanvas'
import { ProjectListModal } from '../../src/components/ProjectListModal'
import type { Project } from '../../src/types'

const project: Project = {
  id: '12345678-id',
  name: 'Test project',
  description: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

afterEach(() => vi.unstubAllGlobals())

test('repeated form submissions while the request is pending send only one request', () => {
  const fetcher = vi.fn(() => new Promise<Response>(() => {}))
  vi.stubGlobal('fetch', fetcher)
  render(<CreateProjectDialog isOpen onClose={() => {}} onProjectCreated={() => {}} />)
  fireEvent.change(screen.getByPlaceholderText('e.g. The Pyramids Mystery'), { target: { value: 'Project' } })
  const form = screen.getByPlaceholderText('e.g. The Pyramids Mystery').closest('form')!
  fireEvent.submit(form)
  fireEvent.submit(form)
  expect(fetcher).toHaveBeenCalledTimes(1)
})

test('a non-Error failure is shown while entered project details remain', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(null))
  render(<CreateProjectDialog isOpen onClose={() => {}} onProjectCreated={() => {}} />)
  const name = screen.getByPlaceholderText('e.g. The Pyramids Mystery')
  const description = screen.getByPlaceholderText('Brief overview or topic notes...')
  fireEvent.change(name, { target: { value: 'Project' } })
  fireEvent.change(description, { target: { value: 'Notes' } })
  fireEvent.submit(name.closest('form')!)
  expect(await screen.findByText('Failed to create project.')).toBeInTheDocument()
  expect(name).toHaveValue('Project')
  expect(description).toHaveValue('Notes')
})

test('inspector logs do not claim an initialization happened', () => {
  render(<Inspector />)
  fireEvent.click(screen.getByRole('button', { name: 'logs' }))
  expect(screen.getByText(/no logs available/i)).toBeInTheDocument()
  expect(screen.queryByText(/stage initialized/i)).not.toBeInTheDocument()
})

test('workflow communicates unavailable progress rather than fabricated stage status', () => {
  render(<WorkflowCanvas project={project} selectedStage="idea" onSelectStage={() => {}} onOpenProjectsModal={() => {}} />)
  expect(screen.getByText(/no workflow progress available/i)).toBeInTheDocument()
  expect(document.querySelector('.lucide-check-circle-2')).not.toBeInTheDocument()
})

test.each(['Select', 'Pan', 'Fit view', 'Zoom out', 'Zoom in'])('canvas toolbar control %s has an accessible name', (name) => {
  render(<WorkflowCanvas project={project} selectedStage="idea" onSelectStage={() => {}} onOpenProjectsModal={() => {}} />)
  expect(screen.getByRole('button', { name })).toBeInTheDocument()
})

test.each(['Provider', 'Model', 'Script Length'])('inspector %s is labelled', (name) => {
  render(<Inspector />)
  expect(screen.getByRole('combobox', { name })).toBeInTheDocument()
})

test.each([['Tone & Audience', 'textbox'], ['Temperature', 'slider']] as const)('advanced inspector %s is labelled', (name, role) => {
  render(<Inspector />)
  fireEvent.click(screen.getByRole('button', { name: 'Advanced Options' }))
  expect(screen.getByRole(role, { name })).toBeInTheDocument()
})

test('project open is a named button', () => {
  render(<ProjectListModal isOpen onClose={() => {}} projects={[project]} onSelectProject={() => {}} onOpenCreateDialog={() => {}} />)
  expect(screen.getByRole('button', { name: /open test project/i })).toBeInTheDocument()
})

test('project search is named', () => {
  render(<ProjectListModal isOpen onClose={() => {}} projects={[project]} onSelectProject={() => {}} onOpenCreateDialog={() => {}} />)
  expect(screen.getByRole('textbox', { name: /search projects/i })).toBeInTheDocument()
})

test('description is labelled', () => {
  render(<CreateProjectDialog isOpen onClose={() => {}} onProjectCreated={() => {}} />)
  expect(screen.getByRole('textbox', { name: /description/i })).toBeInTheDocument()
})
