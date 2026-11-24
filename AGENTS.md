## Agent skills

### Issue tracker

Issues and specs are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Phase workflow

1. Use GitHub milestones as the phases of delivery. Resolve blockers from outside the phase before opening its pull request.
2. Before implementing a phase, open one draft pull request targeting `main` and include a separate `Closes #<number>` line for each issue in the milestone. For a standalone issue, use the same workflow with one issue.
3. Implement dependencies within the phase in order in the same pull request. Verify the acceptance criteria for every linked issue before merging.
4. After merging, confirm that each issue links to the pull request and is closed as completed. Start the next phase or standalone issue after those checks pass.

### Triage labels

Use the default triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository. See `docs/agents/domain.md`.
