# Hive OS — Chat Flow Fix + Right-Sidebar File Explorer (Design)

Date: 2026-06-06
Status: Approved, ready for implementation plan

## Goal

Make the core chat actually work end-to-end and replace the right sidebar's
static info cards with a fully functional, project-scoped file explorer
(navigate, view, edit, and full CRUD). Hermes is the only runner in scope;
multi-runner is explicitly deferred.

## Scope (today)

Two areas only:

- **A. Chat flow** — fix "(no output)", surface errors, wire slash commands
  (especially `/new`), make the layout responsive.
- **B. Right sidebar** — full file explorer (CRUD + edit file content),
  jailed to the active project and ACL-enforced.

Everything else (invite-based registration, per-user/project wiki, tasks,
artifacts, workflows, multi-runner) is decided at the model level (see
Appendix) but **deferred** to later specs.

---

## A. Chat flow

### A1. Seed Hermes credentials into new profile homes

**Problem (root cause of "(no output)"):** every profile gets an isolated,
empty `HERMES_HOME`. Running `hermes -z "<prompt>" --ignore-rules -t ""` against
an empty home fails with `agent failed: No inference provider configured`
(exit 1). stdout is empty, so the backend stores the answer as `"(no output)"`.

Confirmed: the same command against the real `~/.hermes` returns output and
exit 0.

**Decision:** when a profile is created, seed its `HERMES_HOME` from a source
Hermes home (default `~/.hermes`).

- Seed **credential + model config** files: `.env`, model/provider config
  (e.g. `config.*`, model selection, auth/secrets files that Hermes reads at
  startup). Inspect the real `~/.hermes` layout at implementation time and copy
  the minimal set that makes `hermes -z` authenticate.
- Do **not** copy conversation state: `sessions/`, `checkpoints/`, `logs/`,
  `backups/` — per-profile conversation isolation is preserved.
- Idempotent: only seed files that are missing in the target.
- Configurable: new config key `source_hermes_home` (default
  `os.path.expanduser("~/.hermes")`). If the source does not exist, skip
  silently (profile still created).
- Apply on all profile-creation paths: first-run bootstrap, admin-created
  users' first profile, and `POST /api/profiles`.

### A2. Surface runner errors instead of silent "(no output)"

- When a run fails (exit ≠ 0) or stdout is empty, the chat must display the
  actual error text (from stderr / the `run.failed` / `warning` / `error`
  events), as a visible error bubble — not a silent `"(no output)"`.
- `ChatThread` renders `run.failed`, `error`, and `warning` (stderr) events
  visibly (error styling), interleaved in the thread.
- Keep storing the assistant message, but if empty/failed, the stored content
  should reflect the error rather than `"(no output)"`.

### A3. Slash commands in the composer

**Problem (root cause of `/new` doing nothing):** `Composer` sends all text
through `onSubmit`, which always creates a Hermes run. Slash commands are never
intercepted, even though the backend has a command catalog
(`/api/commands/catalog`) and executor (`/api/commands/execute`).

**Decision:** intercept slash commands client-side in the chat composer.

- `/new` → create a new session draft, switch the active session to it, and the
  left sidebar reflects/highlights the new session automatically. (User-
  confirmed expected behavior.)
- `/help`, `/status`, `/session`, `/project`, `/runner` → handle as local info
  responses and/or via `/api/commands/execute`; render result in the thread.
- Slash popover autocomplete: when input starts with `/`, show matching
  commands from `/api/commands/catalog` (styling `.slash-popover` already
  exists in `styles.css`).
- `//` prefix forces the text to be sent as a raw Hermes prompt (backend
  `normalize_command` already supports `force_raw`).
- Unavailable commands (`/model`, `/clear`, `/tools`) show their
  `unavailableMessage` from the catalog.

### A4. Responsive layout

- `AppShell` right rail auto-hides (or toggles) on narrow widths per breakpoints
  in `docs/ui-adaptation-spec.md` (`<768` mobile, `768–1023` tablet, `≥1024`
  desktop panes, `≥1280` + file browser).
- Left sidebar already behaves as a drawer on mobile; verify it works.
- Chat thread + composer must not overflow on phone widths; composer stays
  sticky at the bottom.

---

## B. Right sidebar — project-scoped file explorer (CRUD + edit)

Replaces the current `RightRail` info cards with a real file explorer, matching
the Hermes Desktop right-sidebar file-browser pattern
(`docs/desktop-feature-map.md`).

### B1. Backend API

All endpoints are scoped to a project and enforce:

- **ACL:** caller must be a member of the project (`visible_project`).
- **Path jail:** the requested relative path is resolved with `realpath` and
  must stay within the project root; reject `..` traversal and symlinks that
  escape the root. Never accept absolute server paths from the client.
- **Audit:** every write/destructive operation writes an `audit_log` row
  (actor, action, project, path).

Endpoints:

- `GET  /api/projects/{slug}/tree?path=<rel>` — list a directory: entries with
  `name`, `type` (`dir`/`file`), `size`. Lazy (one level per call).
- `GET  /api/projects/{slug}/file?path=<rel>` — read a text file's content.
  Size limit (~1MB); reject binary files with a clear error.
- `PUT  /api/projects/{slug}/file?path=<rel>` — write/save file content; create
  the file if missing (parent dir must already exist or be created via mkdir).
- `POST /api/projects/{slug}/fs/mkdir` — create a folder (`{path}`).
- `POST /api/projects/{slug}/fs/rename` — rename/move (`{from, to}`), both
  jailed.
- `DELETE /api/projects/{slug}/fs?path=<rel>` — delete a file or folder
  (recursive for folders).

### B2. Frontend file explorer

- Replace `RightRail` content with a `WorkspaceTree` explorer scoped to the
  active project.
- Tree with expand/collapse and lazy loading; VSCode/Hermes-Desktop-style rows
  (chevron + file/folder icon), reuse existing tokens/styles.
- Context actions: new file, new folder, rename, delete (delete requires a
  confirm dialog).
- Clicking a file opens a mini editor (center pane or sheet) with the file
  content; **Save** issues `PUT …/file`.
- Mobile: the explorer is not a side pane; open it as a sheet/route.

---

## Verification (end of day)

1. Login → select project + profile → send "say hi" → Hermes's answer appears
   in chat (or the real error is readable if it fails).
2. `/new` → immediately switches to a new session and the left sidebar follows.
3. Layout is clean and does not overflow on a phone width.
4. File tree: navigate folders, open a file, edit and save it, create/rename/
   delete folders and files — all confined to the project.

Implementation priority if time-constrained: A1 → A2 → A3 → A4 → B.

---

## Appendix — decided models, deferred implementation

These were agreed during brainstorming but are **not** built in this spec:

- **Admin = a normal user** with extra powers; the first admin is created by
  first-run setup.
- **Registration via invite link/code:** admin generates an invite that sets
  **role (member/admin) + expiry**; the user fills **username + password +
  first Hermes profile name** when redeeming it.
- **Wiki:** a personal (per-agent) wiki plus project wikis; access follows
  project visibility — private project wiki = owner only, shared project wiki =
  all members can read and edit.
- **Out of scope entirely for now:** multi-runner (Claude Code/Codex/etc.),
  tasks, artifacts, workflows, POSIX ACL secure mode.
