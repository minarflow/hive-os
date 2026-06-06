# Hermes Desktop Feature Map for Hive OS

This document maps useful Hermes Desktop features/patterns that Hive OS can adapt into a runner-agnostic PWA. Source inspected from local Hermes Desktop app:

```text
/home/kuya/.hermes/hermes-agent/apps/desktop
```

## High-level finding

Hermes Desktop is already very close to the UX we want, but its backend model is Electron-specific:

```text
React/Vite renderer
  -> window.hermesDesktop preload bridge
  -> Electron main process
  -> local Hermes backend/gateway/WebSocket/REST
```

Hive OS should reuse the UX/state/event ideas, not the Electron bridge directly. Hive OS needs:

```text
React/Vite PWA
  -> HTTPS + WebSocket API
  -> Hive OS backend
  -> runner adapters (Hermes first, others later)
  -> OS users + project ACL enforcement
```

## Desktop stack observed

From `apps/desktop/package.json`:

- React 19
- Vite
- TypeScript
- Tailwind v4
- Nanostores
- TanStack React Query
- `@assistant-ui/react`
- `@tanstack/react-virtual`
- `@xterm/xterm`
- `node-pty` in Electron main
- Electron 40

## Desktop shell/UI architecture

Entry:

- `src/main.tsx` mounts the app with:
  - `QueryClientProvider`
  - `ThemeProvider`
  - `HapticsProvider`
  - `HashRouter`
  - root `ErrorBoundary`

Main controller:

- `src/app/desktop-controller.tsx`
  - orchestrates gateway boot, chat, settings, profiles, command center, overlays, right rail, terminal, sessions, model controls, route resume, message streaming.

Shell:

- `src/app/shell/app-shell.tsx`
  - pane-based layout
  - titlebar/statusbar controls
  - notification stack
  - resizable side panes/right rail pattern

Hive OS adaptation:

- Keep a shell + pane model, but make it mobile-first.
- Replace desktop titlebar/native drag behavior with PWA top/bottom navigation.
- Keep overlays/drawers for settings, agents, workflows, projects.

## Existing desktop views worth adapting

Desktop lazy-loads these views in `desktop-controller.tsx`:

- `AgentsView`
- `ArtifactsView`
- `CommandCenterView`
- `CronView`
- `MessagingView`
- `ProfilesView`
- `SettingsView`
- `SkillsView`
- Chat view
- Right sidebar with file browser/terminal/preview

Hive OS equivalents:

- `Agents` -> Agent identities + runner config
- `Artifacts` -> project/session artifacts
- `CommandCenter` -> global command palette/search
- `Cron` -> Workflows/schedules later, not MVP
- `Messaging` -> optional Discord/Telegram bridges later
- `Profiles` -> map to runner identities, not just Hermes profiles
- `Settings` -> workspace/server/user/runner settings
- `Skills` -> runner capability packs/plugins later
- Chat -> core chat interface
- Right rail -> project files/wiki/preview/terminal/tool output

## Preload/Electron bridge capabilities

`electron/preload.cjs` exposes `window.hermesDesktop` with key capabilities:

- connection/gateway:
  - `getConnection(profile)`
  - `touchBackend(profile)`
  - `getGatewayWsUrl(profile)`
  - connection config get/save/apply/test/probe/oauth login/logout
- profile:
  - get/set active profile
- REST bridge:
  - `api(request)`
- notifications
- file handling:
  - read file as data URL/text
  - select paths
  - save image from URL/buffer/clipboard
  - get file path
  - read directory
  - git root
- preview:
  - normalize target
  - watch preview file
  - file-change events
- terminal:
  - start/dispose/resize/write
  - onData/onExit events
- boot/update/log events

Hive OS adaptation:

- Replace `window.hermesDesktop.api()` with authenticated REST calls.
- Replace `getGatewayWsUrl()` with Hive OS session WebSocket endpoint.
- Replace file selection with browser upload/file API and project-scoped file browser.
- Replace Electron terminal bridge with backend PTY/session endpoint if needed.
- Replace desktop notification with PWA notifications later.

## Gateway/stream architecture

`src/hermes.ts` defines `HermesGateway extends JsonRpcGatewayClient` from `@hermes/shared`.

Desktop uses JSON-RPC over gateway WebSocket. `src/store/gateway.ts` manages:

- primary gateway socket
- secondary sockets per profile for concurrent background streams
- active gateway switching
- reconnect/backoff
- event fan-in to one handler

Important behavior to adapt:

- Concurrent sessions need concurrent or multiplexed streams.
- Events are session-keyed, so one UI handler can paint multiple sessions.
- Background sessions can keep streaming while user views another session.
- Reconnect/backoff should be explicit.

Hive OS adaptation:

- Use one backend WebSocket per browser client, multiplexed by `session_id`, or separate WebSocket per session.
- Events should include:
  - `session_id`
  - `runner_id`
  - `user_id`
  - `project_id`
  - monotonic `event_id`/`seq`
- Persist events server-side so reconnect can resume.

## Chat state model

`src/store/session.ts` uses Nanostores for core chat/session state:

- connection and gateway state
- sessions list and totals
- working session ids
- active session id
- selected stored session id
- messages
- busy/awaiting response flags
- model/provider/reasoning/service tier
- cwd/branch
- usage stats
- context suggestions
- session attention ids

It also implements a watchdog:

- working sessions remain marked working while stream events continue
- after 8 minutes of silence, a session can be cleared from working state

Hive OS adaptation:

- Keep the distinction between:
  - active session
  - selected stored session
  - working/background sessions
  - attention-needed sessions
- Add project/user/runner scope to session state.
- Keep a stuck-session watchdog.

## Smooth streaming implementation

`src/app/session/hooks/use-message-stream.ts` is the most important file for chat smoothness.

Key ideas:

1. **Delta batching**
   - `STREAM_DELTA_FLUSH_MS = 33`
   - assistant/reasoning deltas are queued and flushed at ~30fps
   - avoids React committing and Markdown reparsing on every token

2. **Separate assistant/reasoning queues**
   - queued per session id
   - `assistant` and `reasoning` deltas batched separately

3. **Stream message mutation**
   - seeds an in-flight assistant message when first payload arrives
   - updates the same message while pending
   - keeps branch/group metadata

4. **Completion handling**
   - flush queued deltas before final
   - replace/dedupe final text
   - handle provider errors embedded as final text
   - hydrate from stored session if no stream payload arrived

5. **Tool rendering**
   - `tool.start`, `tool.progress`, `tool.generating`, `tool.complete`
   - compact/upsert tool parts inside assistant message
   - todo/tool events normalized

6. **Blocking prompts**
   - `clarify.request`
   - `approval.request`
   - `sudo.request`
   - `secret.request`
   - stored per session so background sessions can wait for user input

7. **Subagent progress**
   - `subagent.spawn_requested`
   - `subagent.start`
   - `subagent.thinking`
   - `subagent.tool`
   - `subagent.progress`
   - `subagent.complete`

Hive OS must implement the same smoothness rules:

- batch deltas at ~33ms
- stream events are session-keyed
- compact tool cards; don't dump long tool output into chat
- persist attention-needed prompts per session
- support background sessions and reconnect

## Event types to support in Hive OS v1

Desktop handles these Hermes event types:

- `gateway.ready`
- `session.info`
- `message.start`
- `message.delta`
- `thinking.delta`
- `reasoning.delta`
- `reasoning.available`
- `message.complete`
- `tool.start`
- `tool.progress`
- `tool.generating`
- `tool.complete`
- `subagent.spawn_requested`
- `subagent.start`
- `subagent.thinking`
- `subagent.tool`
- `subagent.progress`
- `subagent.complete`
- `clarify.request`
- `approval.request`
- `sudo.request`
- `secret.request`
- `error`

Hive OS generic runner events should map to this style, but not use Hermes names as product-only contract.

Recommended Hive OS event contract:

```json
{ "type": "session.info", "session_id": "...", "payload": { "cwd": "...", "runner": "hermes" } }
{ "type": "message.start", "session_id": "..." }
{ "type": "message.delta", "session_id": "...", "payload": { "text": "..." } }
{ "type": "reasoning.delta", "session_id": "...", "payload": { "text": "..." } }
{ "type": "tool.start", "session_id": "...", "payload": { "name": "terminal", "preview": "npm run build" } }
{ "type": "tool.complete", "session_id": "...", "payload": { "name": "terminal", "summary": "passed" } }
{ "type": "approval.request", "session_id": "...", "payload": { "approval_id": "...", "description": "..." } }
{ "type": "message.complete", "session_id": "...", "payload": { "text": "..." } }
{ "type": "error", "session_id": "...", "payload": { "message": "..." } }
```

## Chat UI components worth adapting

Files of interest:

- `src/components/assistant-ui/thread.tsx`
- `src/components/assistant-ui/thread-virtualizer.tsx`
- `src/components/assistant-ui/markdown-text.tsx`
- `src/components/assistant-ui/tool-fallback.tsx`
- `src/components/assistant-ui/tool-approval.tsx`
- `src/components/assistant-ui/clarify-tool.tsx`
- `src/app/chat/composer/*`
- `src/components/chat/*`

Important patterns:

- `@assistant-ui/react` runtime/provider architecture
- virtualized thread
- Markdown/code rendering helpers
- tool approval UI
- clarify UI
- rich composer with attachments/context refs
- right rail for previews/file browser/terminal

Hive OS recommendation:

- Use the design patterns and maybe selected code ideas.
- Do not directly vendor large components until licenses/maintenance are reviewed.
- Start with simpler components but preserve event model and delta batching.

## File/project browser patterns

Desktop has right-sidebar file tree:

- `src/app/right-sidebar/files/*`
- `window.hermesDesktop.readDir`
- `window.hermesDesktop.gitRoot`

Hive OS adaptation:

- project-scoped file browser via backend API
- never expose arbitrary server paths to browser
- file tree rooted at project/workspace allowed roots
- backend enforces app ACL + OS ACL

## Terminal patterns

Desktop exposes terminal through Electron/node-pty:

- `window.hermesDesktop.terminal.start`
- `resize`
- `write`
- `onData`
- `onExit`

Hive OS adaptation:

- Terminal should be admin-only or project-scoped with strong approval.
- If implemented, backend uses PTY under selected OS user and project cwd.
- All terminal sessions must be tied to user + project + audit log.

## Settings/features to defer

Desktop has many settings surfaces:

- models/providers
- tools/toolsets
- skills
- profiles
- cron
- messaging platforms
- updates
- logs
- MCP

Hive OS MVP should defer most of these. Keep only:

- users/login
- runner config read-only or minimal
- projects/members
- chat sessions
- wiki/tasks/artifacts
- audit/break-glass

Add runner/tool/profile management after MVP is stable.

## What Hive OS should copy first

1. Streaming event model and 33ms delta batching.
2. Session-keyed event fan-in.
3. Working/background/attention session states.
4. Compact tool-card rendering.
5. Clarify/approval prompt lifecycle.
6. Mobile-adapted chat composer and thread.
7. Project-scoped file/right-rail concept.

## What Hive OS should rewrite

1. Electron preload IPC -> REST/WebSocket API.
2. Hermes profile abstraction -> generic runner identity.
3. Desktop-local filesystem APIs -> project-scoped backend APIs.
4. Electron terminal -> backend PTY with ACL/audit.
5. Desktop-only titlebar/window shell -> PWA navigation.
6. Hermes-only settings -> runner-agnostic settings.

## Immediate implementation implication

Before implementing UI, define the Hive OS event schema and session persistence around the Desktop streaming lessons:

- SQLite `events` table with `event_id`, `session_id`, `seq`, `type`, `payload`, `created_at`.
- WebSocket endpoint supports `last_event_id` resume.
- Frontend batches `message.delta` and `reasoning.delta` every 33ms.
- Tool outputs are card summaries by default.
- Blocking prompt events create attention state and require a response endpoint.

## Verdict

Hermes Desktop confirms the PWA can feel smooth if Hive OS adopts its event-driven architecture and delta batching. The biggest product difference is access control and runner abstraction: Hive OS must put projects/users/ACLs above the runner layer, then map Hermes events into a generic stream contract.
