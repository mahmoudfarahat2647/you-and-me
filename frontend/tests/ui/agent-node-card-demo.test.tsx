import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import AgentNodeCardDemo from '../../src/fixtures/agent-node-card/AgentNodeCardDemo'

afterEach(() => {
  vi.useRealTimers()
})

function card(name: string) {
  return screen.getByRole('group', { name })
}

test('the isolated fixture demonstrates the supplied three-agent workflow', () => {
  render(<AgentNodeCardDemo />)

  for (const name of ['Web Scraper', 'LLM Summarizer', 'Slack Publisher']) {
    expect(card(name)).toBeInTheDocument()
    expect(within(card(name)).getByRole('status')).toHaveTextContent('Idle')
  }

  expect(card('Web Scraper')).toHaveAttribute('data-selected', 'true')
  expect(within(card('Web Scraper')).getByText('Ready to run')).toBeInTheDocument()
  expect(within(card('LLM Summarizer')).getByText('Waiting for articles')).toBeInTheDocument()
  expect(within(card('Slack Publisher')).getByText('Waiting for the summary')).toBeInTheDocument()
})

test('the fixture demonstrates connected and disconnected ports', () => {
  render(<AgentNodeCardDemo />)

  expect(within(card('Web Scraper')).queryByRole('button', { name: /input port/i })).not.toBeInTheDocument()
  expect(within(card('Web Scraper')).getByRole('button', { name: 'Output port: Articles' })).toBeInTheDocument()

  expect(within(card('LLM Summarizer')).getByRole('button', { name: 'Input port: Articles' })).toBeInTheDocument()
  expect(within(card('LLM Summarizer')).getByTitle('Output: Summary')).toBeInTheDocument()

  expect(within(card('Slack Publisher')).getByTitle('Input: Summary')).toBeInTheDocument()
  expect(within(card('Slack Publisher')).queryByRole('button', { name: /output port/i })).not.toBeInTheDocument()
})

test('the fixture demonstrates switches and header/body/footer content', () => {
  render(<AgentNodeCardDemo />)

  for (const name of ['Follow links', 'Respect robots.txt', 'Include citations', 'Mention the channel']) {
    expect(screen.getByRole('switch', { name })).toBeInTheDocument()
  }
  expect(within(card('Web Scraper')).getByText('Source')).toBeInTheDocument()
  expect(within(card('LLM Summarizer')).getByText('Include citations')).toBeInTheDocument()
  expect(within(card('Slack Publisher')).getByText('#daily-digest')).toBeInTheDocument()
})

test('the simulated workflow shows running, completed and error, and stops at a failure', async () => {
  vi.useFakeTimers()
  render(<AgentNodeCardDemo />)

  fireEvent.click(screen.getByRole('checkbox', { name: /make the last step fail/i }))
  fireEvent.click(screen.getByRole('button', { name: /run workflow/i }))

  expect(within(card('Web Scraper')).getByRole('status')).toHaveTextContent('Running')
  expect(screen.getByRole('button', { name: 'Running…' })).toBeDisabled()

  await act(async () => {
    await vi.advanceTimersByTimeAsync(1800)
  })
  expect(within(card('Web Scraper')).getByRole('status')).toHaveTextContent('Completed')
  expect(within(card('Web Scraper')).getByText('25 articles collected')).toBeInTheDocument()
  expect(within(card('LLM Summarizer')).getByRole('status')).toHaveTextContent('Running')

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2200)
  })
  expect(within(card('LLM Summarizer')).getByRole('status')).toHaveTextContent('Completed')
  expect(within(card('Slack Publisher')).getByRole('status')).toHaveTextContent('Running')

  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500)
  })
  expect(within(card('Slack Publisher')).getByRole('status')).toHaveTextContent('Error')
  expect(within(card('Slack Publisher')).getByRole('alert')).toHaveTextContent('Slack returned 403')
  expect(screen.getByText(/the workflow stopped at the last step/i)).toBeInTheDocument()
})

test('a successful simulated run completes every step', async () => {
  vi.useFakeTimers()
  render(<AgentNodeCardDemo />)

  fireEvent.click(screen.getByRole('button', { name: /run workflow/i }))

  await act(async () => {
    await vi.advanceTimersByTimeAsync(5500)
  })

  for (const name of ['Web Scraper', 'LLM Summarizer', 'Slack Publisher']) {
    expect(within(card(name)).getByRole('status')).toHaveTextContent('Completed')
  }
  expect(screen.getByText(/workflow finished/i)).toBeInTheDocument()
})
