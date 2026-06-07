# Hive OS UI Adaptation Spec

## Direction locked by user

Hive OS should keep the Hermes Desktop look and interaction model as much as possible.

Desktop:

- same overall desktop layout as Hermes Desktop
- same pane/sidebar/chat/right-rail mental model
- same visual style/tokens/chrome where possible
- add Hive OS menus/features: Projects, Wiki, Tasks, Workflows, Agents, Runners, Access/Audit

Mobile:

- do not invent a new style
- make the desktop system responsive
- clean ChatGPT-mobile-like navigation
- full-screen chat first
- menus collapse into drawers/sheets
- bottom composer remains primary

## Source inspected

Local Hermes Desktop source:

```text
~/.hermes/hermes-agent/apps/desktop
```

Key files inspected:

```text
apps/desktop/src/styles.css
apps/desktop/src/app/desktop-controller.tsx
apps/desktop/src/app/shell/app-shell.tsx
apps/desktop/src/app/chat/sidebar/index.tsx
apps/desktop/src/app/session/hooks/use-message-stream.ts
apps/desktop/src/store/gateway.ts
```

Existing feature map:

```text
/path/to/hive-os/docs/desktop-feature-map.md
```

## Hermes Desktop layout map

Desktop currently has this core shape:

```text
AppShell
  TitlebarControls
  PaneShell
    Pane: chat-sidebar
    PaneMain: routes/chat/main views
    Pane: preview rail
    Pane: file browser/right sidebar
  StatusbarControls
  Overlays
```

From `desktop-controller.tsx`:

- left/right chat sidebar via `<ChatSidebar />`
- center `<ChatView />`
- right preview rail via `<ChatPreviewRail />`
- right file browser/tools via `<RightSidebarPane />`
- persistent terminal mounted globally
- overlays for settings, command center, agents, cron, profiles

Hive OS should retain this desktop composition.

## Hive OS desktop IA

Desktop left sidebar should extend Hermes Desktop's current nav.

Existing Hermes nav:

```text
New session
Skills & Tools
Messaging
Artifacts
Sessions
Profiles/workspaces grouping
```

Hive OS desktop nav should become:

```text
New chat
Projects
Tasks
Wiki
Workflows
Agents
Runners
Artifacts
Audit / Access
Settings
```

Suggested grouping:

```text
Primary
  New chat
  Projects
  Tasks
  Wiki

Operations
  Workflows
  Artifacts
  Audit

System
  Agents
  Runners
  Settings
```

Sessions remain visible inside the current project/agent context.

## Desktop panes

Keep the same pane behavior:

```text
left: navigation/session/project sidebar
center: chat/detail route
right rail: file/wiki/artifact/tool preview
optional far-right: file browser / project explorer
```

Do not replace desktop with card dashboard.

## Desktop style tokens

Use Hermes Desktop `styles.css` token approach:

- Tailwind v4
- CSS variables mapped into Tailwind theme
- light chrome by default
- subtle blue accent
- tinted surfaces
- compact text hierarchy
- codicon-style utility icons

Important tokens/patterns from `styles.css`:

```text
--ui-bg-chrome
--ui-bg-sidebar
--ui-bg-editor
--ui-bg-elevated
--ui-chat-surface-background
--ui-chat-bubble-background
--ui-text-primary/secondary/tertiary
--ui-stroke-primary/secondary/tertiary
--shadow-header
--shadow-composer
--shadow-composer-focus
```

Hive OS web should copy/adapt these tokens into its own CSS rather than create a new palette.

## Mobile target

Mobile should feel like ChatGPT mobile, but visually still Hermes/Hive OS.

Mobile layout:

```text
Top bar
  left: menu button
  center: current project / agent / runner context
  right: new chat / project switcher

Main
  chat thread full-screen

Bottom
  composer fixed/sticky bottom

Drawer
  sessions
  projects
  tasks
  wiki
  agents/runners/settings
```

Mobile drawer:

- slide-in from left
- full-height
- same sidebar surface/token style
- search at top
- project/session rows below
- settings/system menu at bottom

Mobile right rail:

- not visible as side pane
- open previews/files/wiki as bottom sheet or full-screen route
- e.g. tapping artifact opens `/artifacts/:id` or a sheet

## Responsive breakpoints

Suggested:

```text
< 768px      mobile full-screen chat + drawer
768-1023px   tablet: sidebar drawer, optional right sheet
>= 1024px    desktop panes visible
>= 1280px    desktop panes + preview/file browser optional
```

Use responsive classes, but keep component structure close to desktop:

```text
Desktop: Sidebar as Pane
Mobile: same Sidebar content inside Drawer
```

Do not fork all UI into separate mobile app.

## Navigation behavior

Desktop:

- route changes update center pane
- sidebar stays visible
- right rail stays available

Mobile:

- drawer closes after route selection
- top bar shows current context
- bottom composer always reachable in chat
- project switching can be a sheet/dropdown

## Additional Hive OS menu details

### Projects

Project list with:

- project name
- owner/member role
- visibility: private/shared
- runner/context status later
- invite/access shortcut for owners

### Tasks

Task list scoped to selected project.

### Wiki

Markdown file list + reader/editor route. On mobile, wiki opens as full-screen route or sheet.

### Workflows

Templates/automations. MVP can be placeholder menu.

### Agents

Human/agent identities and user mapping.

### Runners

Runner integrations:

```text
Hermes
Claude Code
Codex
OpenCode
Shell
```

Hermes can be first enabled runner; others later.

### Audit / Access

Access log and break-glass history. Environment admin can see system-level audit, but not project contents unless member.

## Chat smoothness requirements

Carry over Hermes Desktop streaming lessons:

- event-driven WebSocket stream
- message delta batching at ~33ms
- compact tool cards
- session-keyed events
- background sessions with attention state
- clarify/approval/sudo/secret prompts per session

See:

```text
docs/desktop-feature-map.md
```

## Do not do

- Do not redesign into a generic dashboard.
- Do not use a separate visual identity from Hermes Desktop for v1.
- Do not hide critical actions on mobile; move them into drawer/sheet.
- Do not make `kuya`/environment admin look like automatic project owner.
- Do not lock UI labels to Hermes; use runner-agnostic terms.

## Implementation approach

1. Copy/adapt Hermes Desktop token system into `apps/web/src/styles.css`.
2. Build a small responsive shell:
   - desktop panes
   - mobile drawer/topbar
   - center chat/project routes
3. Build API client for existing FastAPI endpoints.
4. Implement login + project list/create/invite/remove.
5. Add placeholder route shells for Wiki/Tasks/Workflows/Agents/Runners/Audit.
6. Only then wire chat streaming.

## Acceptance criteria for first PWA shell

Desktop:

- visually close to Hermes Desktop
- left sidebar visible
- center route visible
- right preview placeholder exists or can be toggled
- menus include Hive OS additions

Mobile:

- full-screen route/chat area
- top bar with drawer button
- drawer contains same sidebar menu
- composer/project UI does not overflow
- no new visual style beyond responsive adaptation

