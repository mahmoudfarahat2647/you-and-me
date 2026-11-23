import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'

test('renders a button and updates its label when clicked', async () => {
  function Counter() {
    const [count, setCount] = useState(0)

    return (
      <button onClick={() => setCount(count + 1)}>
        Count: {count}
      </button>
    )
  }

  const user = userEvent.setup()
  render(<Counter />)

  await user.click(screen.getByRole('button', { name: 'Count: 0' }))
  expect(screen.getByRole('button', { name: 'Count: 1' })).toBeInTheDocument()
})
