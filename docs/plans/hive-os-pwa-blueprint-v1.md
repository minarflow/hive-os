# Hive OS PWA Blueprint v1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task after user approval.

**Goal:** Build the first working Hive OS prototype: login, private project creation, POSIX ACL invite/remove, project wiki/task scaffolding, and Hermes-first runner chat.

**Architecture:** React/Vite PWA talks to FastAPI backend. Backend stores app ACL/session state in SQLite, manages project filesystem ACL through a controlled `hiveosctl` helper, and streams runner events over WebSocket. Hermes is the first runner, but runner interfaces remain generic.

**Tech Stack:** React, Vite, TypeScript, FastAPI, SQLite, Python 3.11, POSIX ACL (`setfacl/getfacl`), WebSocket.

---

## Locked decisions

1. Source repo: `/home/kuya/projects/hive-os`.
2. Runtime mock workspace: `/srv/hive-os-demo`.
3. Initial laptop users: `kuya` as environment admin, `aris` as member/test collaborator.
4. Project access: app ACL + POSIX ACL.
5. Auth v1: Tailscale/private network + local app login.
6. Frontend v1: React PWA, Flutter later.
7. Runner design: runner-agnostic, Hermes first.
8. Environment admin is not automatic project member.

## Open decisions before implementation

- Exact auth mechanism: password-only local login vs magic dev tokens for prototype.
- Exact backend package manager: uv vs venv/pip.
- Exact frontend package manager: pnpm vs npm.
- Whether first runner should use `hermes chat -q`, `hermes --tui` backend protocol, or a lightweight shell mock until Desktop internals are mapped.

---

## Phase 0: Discovery

### Task 0.1: Map Hermes Desktop features

**Objective:** Identify which Hermes Desktop UI/protocol features should be reused or adapted.

**Files:**
- Read: `/home/kuya/.hermes/hermes-agent/apps/desktop/src/main.tsx`
- Read: `/home/kuya/.hermes/hermes-agent/apps/desktop/src/hermes.ts`
- Read: `/home/kuya/.hermes/hermes-agent/apps/desktop/electron/main.cjs`
- Read: `/home/kuya/.hermes/hermes-agent/apps/desktop/electron/preload.cjs`
- Create: `docs/desktop-feature-map.md`

**Verification:** Document includes chat UI, streaming/backend bridge, session state, tool event handling, and what must be rewritten for PWA.

---

## Phase 1: Workspace + ACL prototype

### Task 1.1: Create workspace initializer

**Objective:** Add a script that creates `/srv/hive-os-demo` skeleton safely.

**Files:**
- Create: `infra/scripts/hiveosctl`
- Create: `templates/workspace/README.md`

**Expected command:**

```bash
sudo ./infra/scripts/hiveosctl init-workspace /srv/hive-os-demo
```

**Verification:**

```bash
test -d /srv/hive-os-demo/projects
test -d /srv/hive-os-demo/shared/wiki
```

### Task 1.2: Implement project create with POSIX ACL

**Objective:** Create a private project owned by a user.

**Command shape:**

```bash
sudo ./infra/scripts/hiveosctl create-project deltapack --owner aris --root /srv/hive-os-demo
```

**Verification:**

```bash
sudo -u aris test -d /srv/hive-os-demo/projects/deltapack
sudo -u kuya test -r /srv/hive-os-demo/projects/deltapack && echo BAD || echo OK_DENIED
getfacl /srv/hive-os-demo/projects/deltapack
```

### Task 1.3: Implement invite/remove

**Objective:** Grant and revoke user access to a project using POSIX ACL.

**Command shape:**

```bash
sudo ./infra/scripts/hiveosctl invite deltapack kuya --root /srv/hive-os-demo
sudo ./infra/scripts/hiveosctl remove deltapack kuya --root /srv/hive-os-demo
```

**Verification:** `kuya` can access after invite and cannot access after remove as normal user.

---

## Phase 2: Backend skeleton

### Task 2.1: Create FastAPI app

**Objective:** Add API app with health endpoint and SQLite initialization.

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/hive_os_api/main.py`
- Create: `apps/api/hive_os_api/db.py`

**Verification:**

```bash
cd apps/api
uv run uvicorn hive_os_api.main:app --host 127.0.0.1 --port 8765
curl http://127.0.0.1:8765/health
```

Expected: `{"ok":true}`.

### Task 2.2: Add users/projects tables

**Objective:** Store users, projects, and project_members.

**Tables:**
- `users(id, username, os_user, role, created_at)`
- `projects(id, slug, name, path, owner_user_id, archived_at, created_at)`
- `project_members(project_id, user_id, role, created_at)`

**Verification:** Unit tests insert `kuya`, `aris`, create `deltapack`, list membership.

### Task 2.3: Add project endpoints

**Objective:** API can create project and invite/remove users by calling controlled helper.

**Endpoints:**
- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{slug}`
- `POST /api/projects/{slug}/invite`
- `POST /api/projects/{slug}/remove`

**Verification:** API project visibility matches DB membership.

---

## Phase 3: Frontend PWA skeleton

### Task 3.1: Create React/Vite app

**Objective:** Add mobile-first PWA shell.

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`

**Verification:**

```bash
cd apps/web
npm install
npm run build
```

### Task 3.2: Add login + project list

**Objective:** Local login and project list filtered by membership.

**Verification:** Login as `aris` shows `deltapack`; login as `kuya` does not until invited.

### Task 3.3: Add project create/invite UI

**Objective:** Members can create private projects and invite collaborators.

**Verification:** UI creates project, ACL works from shell verification, project list updates.

---

## Phase 4: Runner + streaming chat

### Task 4.1: Define runner interface

**Objective:** Add generic Python runner interface and event schema.

**Files:**
- Create: `hive_os/runners/base.py`
- Create: `hive_os/runners/events.py`

**Verification:** Unit tests validate event schemas.

### Task 4.2: Add shell mock runner

**Objective:** Prove WebSocket streaming without Hermes complexity.

**Verification:** Chat sends fake streamed deltas and final event.

### Task 4.3: Add Hermes runner MVP

**Objective:** Run Hermes as selected OS user in project context and stream output.

**Verification:** A project member can ask Hermes to write a file inside project; non-member cannot start session.

---

## Phase 5: Wiki/tasks/workflows

### Task 5.1: Project wiki file API

**Objective:** Read/write markdown files under project wiki only for members.

### Task 5.2: Task folder API

**Objective:** Create task folders from templates.

### Task 5.3: Workflow presets

**Objective:** Add workflow templates: new project, research brief, content draft, dev task, QA task, handoff.

---

## Safety rules

- Do not modify `/home/kuya/projects` current workspaces except this repo.
- Do not move/delete current `linc-ops` or Minarflow data.
- Do not store real tokens/secrets in repo.
- Do not grant `kuya` automatic project membership.
- Keep all runtime writes in `/srv/hive-os-demo` for prototype.
