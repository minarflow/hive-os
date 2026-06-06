# Onboarding Workspace Provisioning — Design

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:writing-plans` next to turn this
> spec into a task-by-task implementation plan. Backend is TDD: write the pytest first, watch it
> fail, implement, watch it pass, commit.

**Goal:** Every Hive OS installation and every onboarded user gets a usable workspace automatically.
On first-run the admin names the team and creates the first **shared** team project; every user then
gets their own **private** project and automatic membership in all shared projects — no manual setup,
no empty file explorer.

**Status of the running system (why this design looks the way it does):**
- Access control is **DB-level only** (`project_members`). POSIX ACL / `hiveosctl` is **not** used by
  the running server: the runtime workspace is `~/.local/share/hive-os/workspace` (not `/srv`), and
  `HIVEOS_PROJECTCTL_COMMAND` is stubbed to `/usr/bin/true` (a no-op). The `/srv/hive-os-demo` ACL
  prototype is legacy and out of scope.
- Consequence: `run_projectctl(...)` does nothing in the current deployment, so projects created today
  have **no folders on disk**. This design creates folders directly in Python under the server-owned
  workspace. ACL/`hiveosctl` remains a future deployment concern, not part of this feature.

**Tech stack:** Python 3.13, FastAPI, SQLite, pytest, FastAPI `TestClient`. No new dependencies.

**Out of scope:** POSIX ACL / unix groups / `hiveosctl` changes; frontend sidebar label wiring (a
follow-up coordinated with the file-explorer work — backend exposes the team name, frontend reads it
later); the file explorer itself (separate workstream).

---

## Concepts

- **Team identity** — a single installation-level name (e.g. "Linc") set by the admin at bootstrap.
  Drives the project slug naming and the (future) sidebar bucket label. Stored in a new key-value
  `app_settings` table.
- **Shared project** — `visibility='shared'`. The team's collaborative workspace. There can be
  **many**. Invariant: **a shared project ⟺ every user is a member of it.**
- **Private project** — `visibility='private'`, one per user, slug = the username, owner = that user.
- **Access** — purely the `project_members` join (matches how `list_projects` already gates access).
  `visibility` is only a UI bucket hint; it does not grant access by itself.

---

## File structure

**Backend — new files:**
- `apps/api/hive_os_api/provisioning.py` — pure orchestration + filesystem scaffold. No FastAPI
  imports; takes a `sqlite3.Connection`, the resolved `cfg` dict, and plain values so it is
  unit-testable. One responsibility: provisioning workspaces.
- `apps/api/tests/test_provisioning.py` — unit/integration tests against an in-memory SQLite DB and a
  temp workspace dir.

**Backend — changed files:**
- `apps/api/hive_os_api/db.py` — add `app_settings` table to `SCHEMA` (idempotent `CREATE TABLE IF
  NOT EXISTS`); no migration needed beyond the existing `migrate_existing` pattern.
- `apps/api/hive_os_api/settings.py` — add `default_team_name` to `DEFAULT_CONFIG` (fallback when the
  admin does not supply one) and `provision_starter_dirs` (the scaffold folder list).
- `apps/api/hive_os_api/main.py` — wire provisioning into three call sites (bootstrap, create_user,
  startup) and make `create_project` scaffold real folders. Keep handlers thin: they call
  `provisioning.*`, they do not contain the logic.

---

## `provisioning.py` — public interface

All functions take `conn` (sqlite3.Connection) and `cfg` (resolved config dict) explicitly. They never
import FastAPI. They never raise on filesystem-already-exists (idempotent).

```text
scaffold_project_dir(cfg, slug) -> Path
    Create workspace_root/projects/<slug>/ plus starter subdirs (wiki/, tasks/, artifacts/)
    and a README.md if missing. mkdir(parents, exist_ok). Returns the project path.
    No ownership/ACL changes. Idempotent.

ensure_member(conn, project_id, user_id, role) -> None
    INSERT OR IGNORE into project_members. Idempotent.

provision_private_project(conn, cfg, user) -> dict | None
    If a project with slug == user['username'] already exists, ensure membership + folders and return
    it. Else: create project row (visibility='private', owner=user), scaffold folders, add owner
    membership, write audit_log('workspace.provision.private'). Returns the project row dict.
    Slug collision guard: if the username equals an existing shared/team slug, use '<username>-home'.

provision_shared_project(conn, cfg, slug, name, owner) -> dict
    Create (or return existing) a shared project (visibility='shared'), scaffold folders, then enroll
    EVERY existing user as a member (owner role for `owner`, 'collaborator' for the rest).
    audit_log('workspace.provision.shared'). Idempotent.

provision_user_workspace(conn, cfg, user) -> None
    provision_private_project(user) + ensure the user is a member of EVERY existing shared project.
    Called on each onboarding.

backfill(conn, cfg) -> dict
    For every user: provision_private_project + membership in all shared projects. Idempotent; safe to
    run on every startup. Returns a small summary {users, private_created, memberships_added}.

get_team_name(conn, cfg) -> str
set_team_name(conn, name) -> None
    Read/write the 'team_name' key in app_settings. get_* falls back to cfg['default_team_name'].
```

### Error isolation
Provisioning is a side effect of onboarding, not a precondition. In `create_user` and `setup_bootstrap`,
a provisioning failure MUST NOT fail the user/admin creation: wrap the provisioning call, log the
exception, write `audit_log('workspace.provision.error', metadata={...})`, and continue. The next
startup `backfill` retries. (Exception: bootstrap shared-project creation failure is surfaced to the
admin response as a non-fatal warning field, since the admin explicitly asked for it — the admin row is
still created and a token still returned.)

---

## Data model

New table (in `db.py` `SCHEMA`):

```sql
CREATE TABLE IF NOT EXISTS app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Reused tables (unchanged): `projects`, `project_members`, `audit_log`. New audit actions:
`workspace.provision.private`, `workspace.provision.shared`, `workspace.provision.member`,
`workspace.provision.error`. `target_type='project'`, `target_id=<slug>`.

---

## Config additions (`settings.py` `DEFAULT_CONFIG`)

```python
"default_team_name": "Team",          # fallback if admin supplies none at bootstrap
"provision_starter_dirs": ["wiki", "tasks", "artifacts"],
"auto_provision": True,               # master kill-switch (skips all provisioning when False)
```

---

## Trigger points (`main.py`)

| Site | New behavior |
|------|--------------|
| `POST /api/setup/bootstrap` | Accept optional `team_name` + `shared_project` (slug/name) on `BootstrapRequest`. After the admin row + profile: `set_team_name(...)`, `provision_user_workspace(admin)` (admin's private project), then `provision_shared_project(slug or 'team', name or team_name, owner=admin)`. Return includes `team_name` and the created shared project. |
| `POST /api/users` | After the user + default profile: `provision_user_workspace(user)`. Wrapped so failure does not break user creation. |
| App startup (lifespan in `create_app`) | If `auto_provision`, run `backfill(conn, cfg)` once after `init_db`. No-op on a fresh install with no users. |
| `GET /api/setup/status` | Add `"team_name": get_team_name(...)` so the frontend can later render the bucket label. |
| `POST /api/projects` | When creating any project, call `scaffold_project_dir(cfg, slug)` so folders exist on disk (fixes the stubbed-projectctl gap). When `visibility=='shared'`, enroll all existing users (reuse `provision_shared_project` enrollment) so the shared invariant holds for admin-created shared projects too. |

`BootstrapRequest` gains `team_name: str | None = None` and `shared_project: {slug,name} | None = None`
(validated with the existing `validate_slug`).

---

## Idempotency & invariants

- Re-running `backfill` never duplicates rows: existence is checked by `projects.slug` and
  `INSERT OR IGNORE` on `project_members`; folder creation uses `exist_ok=True`.
- **Shared invariant** is maintained from both directions: a new user joins all shared projects
  (`provision_user_workspace`), and a new shared project enrolls all users (`provision_shared_project`
  / the `create_project` shared branch).
- `run_projectctl` is left in place but NOT relied upon for folders; provisioning scaffolds directly.
  This keeps the design correct whether projectctl is stubbed (now) or real (future /srv deployment).

---

## Testing (`test_provisioning.py`, TDD)

Mirror the existing backend test style (in-memory SQLite via `db.connect(':memory:')` + `init_db`, a
`tmp_path` workspace root in `cfg`). `run_projectctl` is irrelevant here because provisioning does not
call it.

1. `provision_private_project` creates the project row, owner membership, audit row, and the
   `projects/<username>/{wiki,tasks,artifacts}` dirs + README.
2. Idempotent: calling it twice yields one project, one membership, no duplicate folders/audit churn.
3. `provision_shared_project` creates the shared project and enrolls all existing users as members.
4. A user onboarded AFTER a shared project exists is auto-joined to it (`provision_user_workspace`).
5. A shared project created AFTER users exist enrolls all of them.
6. `backfill` over 3 pre-existing users produces 3 private projects + full shared membership; second
   run is a no-op.
7. Slug collision: a user literally named like the shared slug gets `<username>-home` for their private
   project.
8. Error isolation: a forced scaffold failure (e.g. unwritable workspace) does not raise out of
   `provision_user_workspace`; it logs + audits and returns.
9. `set_team_name`/`get_team_name` round-trip; `get_team_name` falls back to `cfg['default_team_name']`.

Endpoint-level (extend existing API tests): bootstrap with `team_name` + `shared_project` returns the
team name and a shared project, and a subsequently created user appears as a member of that shared
project; `GET /api/setup/status` echoes the team name.

---

## Parallel-work boundary

This feature is **backend-only** and shares no files with the in-flight chat (Phase A) or file-explorer
(Phase B) work, except `apps/api/hive_os_api/main.py` (new wiring, additive) and `db.py` (additive
`CREATE TABLE`). The only cross-workstream contract is the on-disk layout `workspace_root/projects/<slug>/`
— which the file explorer reads and this feature creates. The (future) sidebar label change to
`Sidebar.tsx`/`RightRail.tsx` is deliberately deferred and coordinated to avoid colliding with the file
explorer's edits to the right rail.

---

## Dependencies / risks

- `provision_user_workspace` does not require an OS user to exist (no ACL/`pwd.getpwnam`), unlike the
  legacy `hiveosctl` path — so it is safe for app-only users.
- If a future deployment turns on a real `/srv` + `hiveosctl`, folder creation would be duplicated
  between Python scaffold and `hiveosctl create-project`. Resolve then by having `scaffold_project_dir`
  delegate to `run_projectctl` when a real projectctl is configured. Noted, not built now.
