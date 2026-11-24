import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import {
  AgentNodeCard,
  AgentNodeParam,
  AgentNodeParams,
  AgentNodeToggle,
} from '../../src/components/ui/interactive-ai-agent-workflow-node-card'

test('renders the supplied header, body and footer', () => {
  render(
    <AgentNodeCard
      title="Web Scraper"
      subtitle="Collects today's headlines"
      icon={<span data-testid="node-icon" />}
      footer="Ready to run"
    >
      <AgentNodeParams>
        <AgentNodeParam label="Source" value="news.example.com" mono />
      </AgentNodeParams>
    </AgentNodeCard>
  )

  const card = screen.getByRole('group', { name: 'Web Scraper' })
  expect(within(card).getByRole('heading', { name: 'Web Scraper' })).toBeInTheDocument()
  expect(within(card).getByText("Collects today's headlines")).toBeInTheDocument()
  expect(within(card).getByTestId('node-icon')).toBeInTheDocument()
  expect(within(card).getByText('Source')).toBeInTheDocument()
  expect(within(card).getByText('news.example.com')).toBeInTheDocument()
  expect(within(card).getByText('Ready to run')).toBeInTheDocument()
})

test.each([
  ['idle', 'Idle'],
  ['running', 'Running'],
  ['completed', 'Completed'],
  ['error', 'Error'],
] as const)('shows the %s visual state as %s', (status, label) => {
  render(<AgentNodeCard title={`Node ${status}`} status={status} />)

  const card = screen.getByRole('group', { name: `Node ${status}` })
  expect(card).toHaveAttribute('data-status', status)
  expect(within(card).getByRole('status')).toHaveTextContent(label)
})

test('a truthful statusLabel replaces the default state text', () => {
  render(<AgentNodeCard title="Voice" status="running" statusLabel="Generating narration" />)
  expect(screen.getByRole('status')).toHaveTextContent('Generating narration')
})

test('the error panel appears only for an error with a message', () => {
  const { rerender } = render(
    <AgentNodeCard title="Slack Publisher" status="error" errorMessage="Slack returned 403." />
  )
  expect(screen.getByRole('alert')).toHaveTextContent('Slack returned 403.')

  rerender(<AgentNodeCard title="Slack Publisher" status="completed" errorMessage="Slack returned 403." />)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()

  rerender(<AgentNodeCard title="Slack Publisher" status="error" />)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('selected and unselected cards are distinguishable', () => {
  const { rerender } = render(<AgentNodeCard title="Idea" selected />)
  expect(screen.getByRole('group', { name: 'Idea' })).toHaveAttribute('data-selected', 'true')

  rerender(<AgentNodeCard title="Idea" />)
  expect(screen.getByRole('group', { name: 'Idea' })).not.toHaveAttribute('data-selected')
})

test.each([
  ['idle', 'Run node'],
  ['running', 'Running…'],
  ['completed', 'Run again'],
  ['error', 'Retry'],
] as const)('the %s run button is labelled %s', (status, label) => {
  render(<AgentNodeCard title="Node" status={status} footer="Status footer" onRunNode={() => {}} />)
  expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
})

test('run, run again and retry call the run handler, while running cannot run', async () => {
  const user = userEvent.setup()
  const onRunNode = vi.fn()

  const { rerender } = render(
    <AgentNodeCard title="Node" status="idle" footer="Ready" onRunNode={onRunNode} />
  )
  await user.click(screen.getByRole('button', { name: 'Run node' }))
  expect(onRunNode).toHaveBeenCalledTimes(1)

  rerender(<AgentNodeCard title="Node" status="completed" footer="Done" onRunNode={onRunNode} />)
  await user.click(screen.getByRole('button', { name: 'Run again' }))
  expect(onRunNode).toHaveBeenCalledTimes(2)

  rerender(<AgentNodeCard title="Node" status="error" footer="Failed" onRunNode={onRunNode} />)
  await user.click(screen.getByRole('button', { name: 'Retry' }))
  expect(onRunNode).toHaveBeenCalledTimes(3)

  rerender(<AgentNodeCard title="Node" status="running" footer="Working" onRunNode={onRunNode} />)
  const running = screen.getByRole('button', { name: 'Running…' })
  expect(running).toBeDisabled()
  expect(running).toHaveAttribute('aria-busy', 'true')
})

test('disabled prevents running an idle node', async () => {
  const user = userEvent.setup()
  const onRunNode = vi.fn()
  render(<AgentNodeCard title="Export" status="idle" disabled onRunNode={onRunNode} />)

  const run = screen.getByRole('button', { name: 'Run node' })
  expect(run).toBeDisabled()
  await user.click(run)
  expect(onRunNode).not.toHaveBeenCalled()
})

test('the run button is hidden when no handler is supplied but the footer remains', () => {
  render(<AgentNodeCard title="Idea" footer="Auto mode" />)
  expect(screen.getByText('Auto mode')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /run node|run again|retry|running/i })).not.toBeInTheDocument()
})

test('clicking the card or pressing Enter or Space selects it', async () => {
  const user = userEvent.setup()
  const onSelect = vi.fn()
  render(<AgentNodeCard title="Scenes" onSelect={onSelect} />)

  const card = screen.getByRole('group', { name: 'Scenes' })
  expect(card).toHaveAttribute('tabindex', '0')

  await user.click(within(card).getByRole('heading', { name: 'Scenes' }))
  expect(onSelect).toHaveBeenCalledTimes(1)

  card.focus()
  await user.keyboard('{Enter}')
  expect(onSelect).toHaveBeenCalledTimes(2)

  await user.keyboard(' ')
  expect(onSelect).toHaveBeenCalledTimes(3)
})

test('a card without a select handler stays out of the tab order', () => {
  render(<AgentNodeCard title="Voice" />)
  expect(screen.getByRole('group', { name: 'Voice' })).not.toHaveAttribute('tabindex')
})

test('nested buttons and switches do not also select the card', async () => {
  const user = userEvent.setup()
  const onSelect = vi.fn()
  const onRunNode = vi.fn()
  const onCheckedChange = vi.fn()

  render(
    <AgentNodeCard
      title="Web Scraper"
      status="idle"
      footer="Ready"
      onSelect={onSelect}
      onRunNode={onRunNode}
    >
      <AgentNodeToggle label="Follow links" checked onCheckedChange={onCheckedChange} />
    </AgentNodeCard>
  )

  const toggle = screen.getByRole('switch', { name: 'Follow links' })
  await user.click(toggle)
  expect(onCheckedChange).toHaveBeenCalledWith(false)
  expect(onSelect).not.toHaveBeenCalled()

  await user.click(screen.getByRole('button', { name: 'Run node' }))
  expect(onRunNode).toHaveBeenCalledTimes(1)
  expect(onSelect).not.toHaveBeenCalled()
})

test('the toggle exposes switch semantics and respects disabled', async () => {
  const user = userEvent.setup()
  const onCheckedChange = vi.fn()

  const { rerender } = render(
    <AgentNodeCard title="Node">
      <AgentNodeToggle
        label="Include citations"
        description="Link each point to its story"
        checked={false}
        onCheckedChange={onCheckedChange}
      />
    </AgentNodeCard>
  )

  const toggle = screen.getByRole('switch', { name: 'Include citations' })
  expect(toggle).toHaveAttribute('aria-checked', 'false')
  expect(screen.getByText('Link each point to its story')).toBeInTheDocument()
  await user.click(toggle)
  expect(onCheckedChange).toHaveBeenCalledWith(true)

  rerender(
    <AgentNodeCard title="Node">
      <AgentNodeToggle label="Include citations" checked={false} onCheckedChange={onCheckedChange} disabled />
    </AgentNodeCard>
  )
  expect(screen.getByRole('switch', { name: 'Include citations' })).toBeDisabled()
})

test('ports render labels, connected state and optional click handlers', async () => {
  const user = userEvent.setup()
  const onInputPortClick = vi.fn()
  const onOutputPortClick = vi.fn()

  render(
    <AgentNodeCard
      title="LLM Summarizer"
      inputLabel="Articles"
      outputLabel="Summary"
      inputConnected
      outputConnected
      onInputPortClick={onInputPortClick}
      onOutputPortClick={onOutputPortClick}
    />
  )

  expect(screen.getByRole('button', { name: 'Input port: Articles' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Output port: Summary' })).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Input port: Articles' }))
  expect(onInputPortClick).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('button', { name: 'Output port: Summary' }))
  expect(onOutputPortClick).toHaveBeenCalledTimes(1)
})

test('ports can be hidden and stay visual-only without a click handler', () => {
  const { rerender } = render(
    <AgentNodeCard title="Web Scraper" showInputPort={false} showOutputPort={false} inputLabel="Input" outputLabel="Articles" />
  )
  expect(screen.queryByTitle('Input: Input')).not.toBeInTheDocument()
  expect(screen.queryByTitle('Output: Articles')).not.toBeInTheDocument()

  rerender(<AgentNodeCard title="Web Scraper" showInputPort={false} outputLabel="Articles" />)
  expect(screen.queryByRole('button', { name: /port/i })).not.toBeInTheDocument()
  expect(screen.getByTitle('Output: Articles')).toBeInTheDocument()
})

test('a disabled run button and switch expose disabled semantics', () => {
  render(
    <AgentNodeCard title="Export" status="idle" disabled onRunNode={() => {}}>
      <AgentNodeToggle label="Upload privately" checked onCheckedChange={() => {}} disabled />
    </AgentNodeCard>
  )
  expect(screen.getByRole('button', { name: 'Run node' })).toBeDisabled()
  expect(screen.getByRole('switch', { name: 'Upload privately' })).toBeDisabled()
})

test('running effects are supplied and respect reduced motion', () => {
  const { rerender } = render(<AgentNodeCard title="Node" status="running" />)

  expect(document.querySelector('.agent-ring')).toBeInTheDocument()
  expect(document.querySelector('.agent-glow')).toBeInTheDocument()
  expect(document.querySelector('.agent-sweep')).toBeInTheDocument()
  expect(document.querySelector('style')?.textContent).toContain('@media (prefers-reduced-motion: reduce)')
  expect(document.querySelector('style')?.textContent).toContain('.agent-ring, .agent-glow, .agent-sweep { animation: none; }')

  rerender(<AgentNodeCard title="Node" status="idle" />)
  expect(document.querySelector('.agent-ring')).not.toBeInTheDocument()
  expect(document.querySelector('.agent-glow')).not.toBeInTheDocument()
})
