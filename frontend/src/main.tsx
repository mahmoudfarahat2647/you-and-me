import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const root = createRoot(document.getElementById('root')!)

// Dev-only fixture preview: http://localhost:5173/?fixture=agent-node-card
// The branch is statically disabled in production builds, so the fixture is
// never part of the shipped application.
const fixture = import.meta.env.DEV
  ? new URLSearchParams(window.location.search).get('fixture')
  : null

if (fixture === 'agent-node-card') {
  void import('./fixtures/agent-node-card/AgentNodeCardDemo').then(({ default: AgentNodeCardDemo }) => {
    root.render(
      <StrictMode>
        <AgentNodeCardDemo />
      </StrictMode>,
    )
  })
} else {
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
