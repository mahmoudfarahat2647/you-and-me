# M0 reference — interactive AgentNodeCard

This folder retains the owner-supplied snippets exactly as they were provided in [issue #21](https://github.com/mahmoudfarahat2647/you-and-me/issues/21). They are the source of truth for the visual and interaction design of every workflow node.

- `interactive-ai-agent-workflow-node-card.tsx` — Source A, the supplied component.
- `demo.tsx` — Source B, the supplied demo.

The working copy lives in `frontend/src/components/ui/interactive-ai-agent-workflow-node-card.tsx`. The demo is copied to the isolated fixture `frontend/src/fixtures/agent-node-card/AgentNodeCardDemo.tsx`.

## Compatibility-only changes in the working copy

These are the only differences from Source A. They do not change the visual or interaction design.

1. **Class merging** — the supplied local `cn` helper joins class names without resolving Tailwind conflicts. The working copy uses the project's `cn` from `@/lib/utils` (`clsx` + `tailwind-merge`) so a consumer-provided width such as `w-80` correctly overrides the base `w-full`.
2. **React Flow drag guards** — `nodrag nopan` was added to the port buttons, the run/retry button and the toggle switch so nested controls never start a canvas drag or pan. The classes are inert outside React Flow.
3. **Import alias** — the working copy resolves `@/lib/utils` through the project alias configured in `tsconfig.app.json`, `vite.config.ts` and `vitest.config.ts`.
4. **Theme tokens** — the shadcn semantic tokens used by the card (`background`, `foreground`, `card`, `popover`, `muted`, `primary`, `border`, `ring`) are mapped to the approved charcoal workspace palette in `frontend/src/index.css`. The `dark` variant is class-based so the dark-only app gets the supplied dark-mode chip colours.

No external assets, credentials, paid requests or production backend are used.
