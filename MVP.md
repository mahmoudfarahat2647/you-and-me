# AI Video Studio — MVP Proposal

> **Status:** Review-only draft. **UI reference and MVP must be approved before implementation or ticket breakdown.**
>
> **Design source of truth:** ![Approved Workflow Canvas](docs/design/approved-workflow-reference.png)
>
> This exact image, selected by the owner, is the baseline. Keep its spatial organization and restrained visual design; any changes require review.

## 1. Product vision

A **personal, Windows-first desktop video production studio** for useful Arabic YouTube videos and Shorts. The user should be able to type a topic and run a full workflow, or control **each stage independently**. Support multiple channel profiles (history, religion, education, and more) without requiring one content niche for the app.

Primary goals: **flexibility, approachable UI, automation, original/high-quality videos, and cost awareness**. No promise of free unlimited video generation, guaranteed YouTube monetization, or flawless compliance.

## 2. Approved interface — Workflow Canvas

- Notion-inspired minimalist dark UI: charcoal `#191919` and `#202020`, 1px hairline borders, Lucide outline icons, low visual density, modest rounded corners, no neon or glassmorphism.
- **Left sidebar:** Workflow, Projects, Channels, Providers, Templates, Settings, Recent Projects.
- **Main workspace:** breadcrumbs, project name, Run Workflow button, Workflow / Assets / Output / Logs tabs.
- **Canvas:** compact connected nodes across a subtle dotted grid; pan/zoom; selected-node emphasis. Preserve the layout from the screenshot.
- **Right inspector:** selected-node details, tabs Settings / Output / Logs, Mode, Provider, Model, duration and advanced options.
- Advanced features should be discoverable but collapsed by default. A single Run Workflow button must remain obvious.
- Dark theme in first MVP; light-theme support may follow.
- Reference screenshot is a **visual mock**, not proof that named integrations or models are available.

## 3. Confirmed technical stack

| Layer | Technology |
|---|---|
| Windows shell | Tauri 2 |
| Frontend | React, TypeScript, Tailwind CSS, shadcn/ui, Lucide |
| Canvas | React Flow / `@xyflow/react` |
| JS package management | **pnpm only** |
| Local backend | Python 3.12+ and FastAPI |
| Database | SQLite |
| Video/audio processing | FFmpeg and ffprobe |
| Execution | Persisted Python workflow/jobs engine |
| Credential handling | Windows protected credential storage; no plaintext keys in SQLite |

Python and FFmpeg must be packaged/managed so the owner does not have to run a terminal or remote server.

## 4. Core interaction model

Each node independently supports:

- **Auto:** run using the configured supported provider.
- **Manual:** type/import/select the output yourself.
- **Approval:** auto-generate, then pause for owner approval or editing.
- **Off:** disable optional steps; required steps may only be skipped if a compatible saved artifact exists.

Global presets (e.g. Full Auto, Review Before Publish) can set initial defaults, but node-level selections override them. Validate workflow dependencies before running. Persist artifacts, input/output metadata and logs. Support pause, resume, retry, cancel, preview results and rerun only a node plus invalidated downstream steps without regenerating unaffected content.

## 5. Logical production workflow

1. **Idea & Research:** user topic or generated suggestion; collect verifiable sources.
2. **Preflight:** assess factual/source risks, originality, licensing, suitability for YouTube, and estimated API cost **before spending credits**.
3. **Script:** original Arabic script with sources, manual editing/import and target length.
4. **Storyboard:** timed scenes, prompts, visual continuity, aspect ratio and shot plan.
5. **Voice / TTS:** selected provider or imported narration; timings/alignment.
6. **Visual Generation:** full-motion scene video via a configured, actually available provider or imported moving footage. **Never quietly replace requested video with animated still photos.**
7. **Edit & Sync:** align voice and scenes with FFmpeg, compose final MP4, optionally subtitles/music where rights permit.
8. **Quality review:** playback/technical checks and policy/source flags; warnings are not a monetization guarantee.
9. **YouTube export/upload:** local MP4, title/description and optional authorized upload, **Private by default**, with explicit public-upload opt-in.

For UI cleanliness, the main canvas can show six compact stages like the reference image while preflight, timing and QA act as underlying substeps/gates.

## 6. Provider system & authentication

- A **Providers** settings page allows API credentials, supported OAuth, local endpoints, model selection, connection tests and availability/cost information.
- Each node chooses its provider without locking the whole workflow to one service. Support free, paid and local options when real supported adapters exist, plus manual files.
- **ChatGPT Plus/Pro sign-in is not a generic OpenAI API key.** Only offer supported official Codex/ChatGPT integration features after confirming their permitted use. Do not automate browser cookies or session-token extraction.
- **Google AI Pro / Flow credits are not automatically Veo API credits.** Verify real API access, rates, limits and terms before implementing automated generation.
- Project budgets, estimated spend before provider calls, capped retries and user confirmation for overruns. Label unknown costs explicitly rather than invent prices.

## 7. Projects and channels

- Multiple independent channel profiles with name, topic focus, language, video format, default narrator, budget, visual style and upload destination.
- Multiple project workflows per channel; reusable templates/presets.
- Local files, script, scene definitions, audio, generated clips, logs and final exports available per project.
- A channel profile does not imply authorization to upload to YouTube; use official OAuth permissions.

## 8. Delivery milestones

**M0 — UI approval (first, no backend code):** recreate the uploaded reference as a faithful interactive frontend mock including canvas, sidebar, inspector, node modes and provider selectors. Ask for design approval.

**M1 — Functional local pipeline:** Tauri/FastAPI integration, SQLite state, Manual/import path, resumable nodes, FFmpeg output, preview/logs. Validate full local MP4 production using supplied moving clips and voice.

**M2 — Automation:** supported provider adapters for research/script/TTS/video, preflight checks, budget guards, retries and per-node Auto/Manual/Approval. A configured end-to-end run can produce a video with genuine moving scenes.

**M3 — YouTube:** official OAuth, channel select, upload progress, metadata, Private default and optional explicit public publishing, subject to quota and any verification restrictions.

**After MVP:** thumbnail design, richer SEO/title tools, batch production, scheduling, analytics, more provider adapters, plug-in marketplace.

## 9. Acceptance criteria

- Owner reviews and approves visual fidelity before implementation.
- New project/channel and simple preset can be set up without confronting advanced configuration.
- Per-node modes and provider choices work with clear dependency feedback.
- Saved outputs survive application restarts and avoid unnecessary regeneration.
- Before costly calls, estimates and budget cap are shown; no surprise paid fallbacks.
- Final MP4 plays with audio and synchronized **moving** video clips from the user's selected services/assets.
- QA catches technical issues and flags potential source, reuse and policy risks, but does not claim YouTube approval.
- YouTube upload requires legitimate authorization; privacy follows explicit choice, default Private.
- No incorrect promises about ChatGPT subscription, Flow credits, or unavailable API connections.

## 10. Questions for the next formal spec

Confirm the real available models and pricing, adapter contracts, credentials storage, offline/resume behavior, file schemas, audio timing accuracy, duration and aspect ratios, limits of automatic policy review, and whether public auto-publishing should be available in the first release.

**Next step:** approve the UI mock, revise this MVP, produce a detailed spec, then split it into GitHub implementation issues. No implementation yet.
