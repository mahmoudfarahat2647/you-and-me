import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ActionableError } from '../../src/components/ActionableError';

it('offers troubleshooting without developer-specific commands or port claims', () => {
  render(<ActionableError error="Missing runtime" onRetry={vi.fn()} isRetrying={false} />);
  expect(screen.getByText(/Missing runtime/)).toBeInTheDocument();
  expect(screen.queryByText(/you-and-me|8000/i)).not.toBeInTheDocument();
  expect(screen.getByText(/backend dependencies/i)).toBeInTheDocument();
});
