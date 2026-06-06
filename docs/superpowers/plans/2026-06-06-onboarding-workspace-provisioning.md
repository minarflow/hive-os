# Onboarding Workspace Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-provision a per-install team identity + first shared project, a private project per user, and automatic membership in every shared project — all at the DB level with plain folders on disk.

**Architecture:** A new pure module `provisioning.py` holds all orchestration and filesystem scaffolding (no FastAPI imports, takes `conn` + `cfg`). `main.py` wires it into three sites: `setup_bootstrap`, `create_user`, and app startup (backfill). Access is DB-only (`project_members`); folders are created directly in Python because the running deployment stubs `projectctl`. No POSIX ACL.

**Tech Stack:** Python 3.13, FastAPI, SQLite, pytest.

**Conventions:**
- Backend is TDD: write the pytest first, watch it fail, implement, watch it pass, commit.
- Run tests: `cd apps/api && uv run pytest -q`
- All work happens in the worktree `/home/kuya/storage/projects/hive-os-onboarding` on branch `onboarding-provisioning`.
- When editing `main.py`, locate anchors by **function name / code content**, not line numbers — `main.py` is being edited concurrently by another workstream, so line numbers will drift.

---

## File Structure

**New files:**
- `apps/api/hive_os_api/provisioning.py` — all provisioning orchestration + `scaffold_project_dir`. Pure: takes `sqlite3.Connection` + `cfg` dict. One responsibility.
- `apps/api/tests/test_provisioning.py` — unit tests against in-memory SQLite + temp workspace.

**Modified files:**
- `apps/api/hive_os_api/db.py` — add `app_settings` table to `SCHEMA`.
- `apps/api/hive_os_api/settings.py` — add `default_team_name`, `provision_starter_dirs`, `auto_provision` to `DEFAULT_CONFIG`.
- `apps/api/hive_os_api/main.py` — add request fields; wire provisioning into `setup_bootstrap`, `create_user`, `create_project`, startup, and `setup_status`.

---

## Task 1: `app_settings` table + team-name helpers

**Files:**
- Modify: `apps/api/hive_os_api/db.py` (the `SCHEMA` string)
- Create: `apps/api/hive_os_api/provisioning.py`
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_provisioning.py`:

```python
from __future__ import annotations

import pytest

from hive_os_api import db as dbmod
from hive_os_api import provisioning
from hive_os_api.auth import hash_password, iso_now


def make_db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn)
    return conn


def make_cfg(tmp_path):
    return {
        "workspace_root": str(tmp_path),
        "provision_starter_dirs": ["wiki", "tasks", "artifacts"],
        "default_team_name": "Team",
        "auto_provision": True,
    }


def add_user(conn, username, role="member"):
    cur = conn.execute(
        "INSERT INTO users(username, os_user, role, password_hash, password_set_at) VALUES (?, ?, ?, ?, ?)",
        (username, username, role, hash_password("pw"), iso_now()),
    )
    return dict(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


def test_team_name_round_trip_and_fallback(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    assert provisioning.get_team_name(conn, cfg) == "Team"  # fallback to cfg
    provisioning.set_team_name(conn, "Linc")
    assert provisioning.get_team_name(conn, cfg) == "Linc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'hive_os_api.provisioning'` (and/or `no such table: app_settings`).

- [ ] **Step 3a: Add the `app_settings` table to `db.py`**

In `apps/api/hive_os_api/db.py`, inside the `SCHEMA` string, add this block right after the `CREATE TABLE IF NOT EXISTS audit_log (...)` statement (before the `CREATE INDEX` lines):

```sql
CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 3b: Create `provisioning.py` with the team-name helpers**

Create `apps/api/hive_os_api/provisioning.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("hive_os.provisioning")


def get_team_name(conn, cfg: dict[str, Any]) -> str:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'team_name'").fetchone()
    if row and row["value"]:
        return row["value"]
    return cfg.get("default_team_name") or "Team"


def set_team_name(conn, name: str) -> None:
    conn.execute(
        "INSERT INTO app_settings(key, value) VALUES ('team_name', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
        (name,),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/db.py apps/api/hive_os_api/provisioning.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): app_settings table + team-name helpers"
```

---

## Task 2: `scaffold_project_dir` + `ensure_member`

**Files:**
- Modify: `apps/api/hive_os_api/provisioning.py`
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_scaffold_project_dir_creates_folders_and_readme(tmp_path):
    cfg = make_cfg(tmp_path)
    path = provisioning.scaffold_project_dir(cfg, "demo")
    assert path == tmp_path / "projects" / "demo"
    assert (path / "wiki").is_dir()
    assert (path / "tasks").is_dir()
    assert (path / "artifacts").is_dir()
    assert (path / "README.md").read_text().startswith("# demo")


def test_scaffold_is_idempotent(tmp_path):
    cfg = make_cfg(tmp_path)
    provisioning.scaffold_project_dir(cfg, "demo")
    provisioning.scaffold_project_dir(cfg, "demo")  # must not raise
    assert (tmp_path / "projects" / "demo" / "wiki").is_dir()


def test_ensure_member_idempotent(tmp_path):
    conn = make_db()
    user = add_user(conn, "alice")
    conn.execute(
        "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES ('p', 'P', '/x', ?, 'private')",
        (user["id"],),
    )
    pid = conn.execute("SELECT id FROM projects WHERE slug = 'p'").fetchone()["id"]
    provisioning.ensure_member(conn, pid, user["id"], "owner")
    provisioning.ensure_member(conn, pid, user["id"], "owner")  # no duplicate
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM project_members WHERE project_id = ? AND user_id = ?", (pid, user["id"])
    ).fetchone()["c"]
    assert count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: FAIL — `AttributeError: module 'hive_os_api.provisioning' has no attribute 'scaffold_project_dir'`.

- [ ] **Step 3: Implement**

Add to `apps/api/hive_os_api/provisioning.py` (after the imports, before `get_team_name`):

```python
def _projects_root(cfg: dict[str, Any]) -> Path:
    return Path(cfg["workspace_root"]) / "projects"


def scaffold_project_dir(cfg: dict[str, Any], slug: str) -> Path:
    """Create projects/<slug>/ with starter subdirs + README. Idempotent, no ACL."""
    path = _projects_root(cfg) / slug
    path.mkdir(parents=True, exist_ok=True)
    for sub in cfg.get("provision_starter_dirs") or ["wiki", "tasks", "artifacts"]:
        (path / sub).mkdir(parents=True, exist_ok=True)
    readme = path / "README.md"
    if not readme.exists():
        readme.write_text(f"# {slug}\n\nHive OS project workspace.\n", encoding="utf-8")
    return path


def ensure_member(conn, project_id: int, user_id: int, role: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO project_members(project_id, user_id, role) VALUES (?, ?, ?)",
        (project_id, user_id, role),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/provisioning.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): project folder scaffolder + ensure_member helper"
```

---

## Task 3: `provision_private_project` (with slug-collision guard)

**Files:**
- Modify: `apps/api/hive_os_api/provisioning.py`
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_provision_private_project(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    user = add_user(conn, "alice")
    project = provisioning.provision_private_project(conn, cfg, user)
    assert project["slug"] == "alice"
    assert project["visibility"] == "private"
    assert project["owner_user_id"] == user["id"]
    # owner membership
    role = conn.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?", (project["id"], user["id"])
    ).fetchone()["role"]
    assert role == "owner"
    # folder + audit
    assert (tmp_path / "projects" / "alice" / "wiki").is_dir()
    actions = [r["action"] for r in conn.execute("SELECT action FROM audit_log").fetchall()]
    assert "workspace.provision.private" in actions


def test_provision_private_idempotent(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    user = add_user(conn, "alice")
    provisioning.provision_private_project(conn, cfg, user)
    provisioning.provision_private_project(conn, cfg, user)
    count = conn.execute("SELECT COUNT(*) AS c FROM projects WHERE owner_user_id = ?", (user["id"],)).fetchone()["c"]
    assert count == 1


def test_provision_private_slug_collision_uses_home_suffix(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    # a shared project already owns the slug "team"
    conn.execute(
        "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES ('team', 'Team', '/x', ?, 'shared')",
        (admin["id"],),
    )
    user = add_user(conn, "team")  # username collides with the shared slug
    project = provisioning.provision_private_project(conn, cfg, user)
    assert project["slug"] == "team-home"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'provision_private_project'`.

- [ ] **Step 3: Implement**

Add to `apps/api/hive_os_api/provisioning.py`:

```python
def _audit(conn, actor_user_id, action: str, slug: str, metadata: str = "{}") -> None:
    conn.execute(
        "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, metadata) "
        "VALUES (?, ?, 'project', ?, ?)",
        (actor_user_id, action, slug, metadata),
    )


def provision_private_project(conn, cfg: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    slug = user["username"]
    existing = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    # If the slug is taken by someone else (e.g. a shared project named like this user), use a suffix.
    if existing and existing["owner_user_id"] != user["id"]:
        slug = f"{user['username']}-home"
        existing = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if existing:
        scaffold_project_dir(cfg, slug)
        ensure_member(conn, existing["id"], user["id"], "owner")
        return dict(existing)
    path = str(scaffold_project_dir(cfg, slug))
    cur = conn.execute(
        "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES (?, ?, ?, ?, 'private')",
        (slug, f"{user['username']} (private)", path, user["id"]),
    )
    project_id = cur.lastrowid
    ensure_member(conn, project_id, user["id"], "owner")
    _audit(conn, user["id"], "workspace.provision.private", slug)
    return dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/provisioning.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): provision per-user private project with collision guard"
```

---

## Task 4: `provision_shared_project` (enrolls all users)

**Files:**
- Modify: `apps/api/hive_os_api/provisioning.py`
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_provision_shared_enrolls_all_users(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    bob = add_user(conn, "bob")
    project = provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    assert project["visibility"] == "shared"
    members = {
        r["user_id"]: r["role"]
        for r in conn.execute("SELECT user_id, role FROM project_members WHERE project_id = ?", (project["id"],)).fetchall()
    }
    assert members[admin["id"]] == "owner"
    assert members[bob["id"]] == "collaborator"
    assert (tmp_path / "projects" / "linc" / "wiki").is_dir()


def test_provision_shared_idempotent(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    count = conn.execute("SELECT COUNT(*) AS c FROM projects WHERE slug = 'linc'").fetchone()["c"]
    assert count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'provision_shared_project'`.

- [ ] **Step 3: Implement**

Add to `apps/api/hive_os_api/provisioning.py`:

```python
def provision_shared_project(conn, cfg: dict[str, Any], slug: str, name: str, owner: dict[str, Any]) -> dict[str, Any]:
    existing = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if existing:
        project = dict(existing)
    else:
        path = str(scaffold_project_dir(cfg, slug))
        cur = conn.execute(
            "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES (?, ?, ?, ?, 'shared')",
            (slug, name, path, owner["id"]),
        )
        project = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (cur.lastrowid,)).fetchone())
        _audit(conn, owner["id"], "workspace.provision.shared", slug)
    for row in conn.execute("SELECT id FROM users").fetchall():
        role = "owner" if row["id"] == owner["id"] else "collaborator"
        ensure_member(conn, project["id"], row["id"], role)
    return project
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/provisioning.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): provision shared project enrolling all users"
```

---

## Task 5: `provision_user_workspace` (private + join all shared, error-isolated)

**Files:**
- Modify: `apps/api/hive_os_api/provisioning.py`
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_user_workspace_joins_existing_shared(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    # bob onboards AFTER the shared project exists
    bob = add_user(conn, "bob")
    provisioning.provision_user_workspace(conn, cfg, bob)
    # bob has a private project
    assert conn.execute("SELECT COUNT(*) AS c FROM projects WHERE slug = 'bob'").fetchone()["c"] == 1
    # bob is a member of the shared project
    shared_id = conn.execute("SELECT id FROM projects WHERE slug = 'linc'").fetchone()["id"]
    assert conn.execute(
        "SELECT COUNT(*) AS c FROM project_members WHERE project_id = ? AND user_id = ?", (shared_id, bob["id"])
    ).fetchone()["c"] == 1


def test_user_workspace_error_is_isolated(tmp_path, monkeypatch):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    bob = add_user(conn, "bob")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(provisioning, "scaffold_project_dir", boom)
    # must NOT raise
    provisioning.provision_user_workspace(conn, cfg, bob)
    actions = [r["action"] for r in conn.execute("SELECT action FROM audit_log").fetchall()]
    assert "workspace.provision.error" in actions


def test_auto_provision_disabled_is_noop(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    cfg["auto_provision"] = False
    bob = add_user(conn, "bob")
    provisioning.provision_user_workspace(conn, cfg, bob)
    assert conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'provision_user_workspace'`.

- [ ] **Step 3: Implement**

Add to `apps/api/hive_os_api/provisioning.py`:

```python
def provision_user_workspace(conn, cfg: dict[str, Any], user: dict[str, Any]) -> None:
    """Provision a user's private project and join all shared projects. Never raises."""
    if not cfg.get("auto_provision", True):
        return
    try:
        provision_private_project(conn, cfg, user)
        for row in conn.execute("SELECT id FROM projects WHERE visibility = 'shared'").fetchall():
            ensure_member(conn, row["id"], user["id"], "collaborator")
    except Exception as exc:  # provisioning is a side effect; never break onboarding
        logger.exception("provision_user_workspace failed for user %s", user.get("username"))
        try:
            _audit(conn, user.get("id"), "workspace.provision.error", str(user.get("username")), metadata="{}")
        except Exception:
            pass
```

Note: `boom` in the test replaces `provisioning.scaffold_project_dir`; because `provision_private_project` calls the module-level name, monkeypatch takes effect and the `OSError` is caught here.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/provisioning.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): provision_user_workspace with error isolation"
```

---

## Task 6: `backfill`

**Files:**
- Modify: `apps/api/hive_os_api/provisioning.py`
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_backfill_all_users(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    add_user(conn, "bob")
    add_user(conn, "carol")
    provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    summary = provisioning.backfill(conn, cfg)
    assert summary["users"] == 3
    # every user has a private project
    assert conn.execute("SELECT COUNT(*) AS c FROM projects WHERE visibility = 'private'").fetchone()["c"] == 3
    # every user is a member of the shared project
    shared_id = conn.execute("SELECT id FROM projects WHERE slug = 'linc'").fetchone()["id"]
    assert conn.execute(
        "SELECT COUNT(*) AS c FROM project_members WHERE project_id = ?", (shared_id,)
    ).fetchone()["c"] == 3


def test_backfill_idempotent(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    add_user(conn, "bob")
    provisioning.backfill(conn, cfg)
    provisioning.backfill(conn, cfg)
    assert conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'backfill'`.

- [ ] **Step 3: Implement**

Add to `apps/api/hive_os_api/provisioning.py`:

```python
def backfill(conn, cfg: dict[str, Any]) -> dict[str, int]:
    """Ensure every user has a private project and membership in all shared projects."""
    if not cfg.get("auto_provision", True):
        return {"users": 0}
    users = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    shared = [dict(r) for r in conn.execute("SELECT id FROM projects WHERE visibility = 'shared'").fetchall()]
    for user in users:
        provision_private_project(conn, cfg, user)
        for s in shared:
            ensure_member(conn, s["id"], user["id"], "collaborator")
    return {"users": len(users)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (14 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/provisioning.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): startup backfill for existing users"
```

---

## Task 7: Config additions

**Files:**
- Modify: `apps/api/hive_os_api/settings.py` (the `DEFAULT_CONFIG` dict)
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_default_config_has_provisioning_keys():
    from hive_os_api.settings import normalize_config

    cfg = normalize_config()
    assert cfg["default_team_name"] == "Team"
    assert cfg["provision_starter_dirs"] == ["wiki", "tasks", "artifacts"]
    assert cfg["auto_provision"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_default_config_has_provisioning_keys -q`
Expected: FAIL — `KeyError: 'default_team_name'`.

- [ ] **Step 3: Implement**

In `apps/api/hive_os_api/settings.py`, add these three keys to the `DEFAULT_CONFIG` dict (anywhere inside the dict literal, e.g. after `"seed_users": []`):

```python
    "default_team_name": "Team",
    "provision_starter_dirs": ["wiki", "tasks", "artifacts"],
    "auto_provision": True,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (15 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/settings.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): default config keys for provisioning"
```

---

## Task 8: Wire `setup_bootstrap` (team name + first shared project)

**Files:**
- Modify: `apps/api/hive_os_api/main.py` (the `BootstrapRequest` model and the `setup_bootstrap` handler)
- Test: `apps/api/tests/test_provisioning.py`

**Anchor note:** Locate `class BootstrapRequest(BaseModel)` and the `def setup_bootstrap(...)` handler by name. At the top of `main.py`, add `from .provisioning import (...)` to the existing imports from this package — find the line `from .profile_seed import seed_hermes_home` (or similar local imports) and add the provisioning import nearby.

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def _client(tmp_path):
    from fastapi.testclient import TestClient
    from hive_os_api.main import create_app

    app = create_app(
        {
            "database_path": str(tmp_path / "db.sqlite"),
            "workspace_root": str(tmp_path / "ws"),
            "hermes_profiles_root": str(tmp_path / "profiles"),
            "projectctl_path": "/usr/bin/true",
            "start_worker": False,
        }
    )
    return TestClient(app)


def test_bootstrap_sets_team_and_shared_project(tmp_path):
    client = _client(tmp_path)
    resp = client.post(
        "/api/setup/bootstrap",
        json={
            "username": "admin",
            "password": "password123",
            "profile_slug": "default",
            "profile_name": "Default",
            "team_name": "Linc",
            "shared_project": {"slug": "linc", "name": "Linc"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["team_name"] == "Linc"
    assert body["shared_project"]["slug"] == "linc"
    # (the /api/setup/status team_name echo is verified in Task 10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_bootstrap_sets_team_and_shared_project -q`
Expected: FAIL — response has no `team_name` key (KeyError / assertion error).

- [ ] **Step 3a: Add request models**

In `apps/api/hive_os_api/main.py`, find `class BootstrapRequest(BaseModel):` and add the two optional fields, plus a small nested model just above it:

```python
class SharedProjectSpec(BaseModel):
    slug: str
    name: str | None = None
```

Inside `class BootstrapRequest(BaseModel):` add:

```python
    team_name: str | None = None
    shared_project: SharedProjectSpec | None = None
```

- [ ] **Step 3b: Add the provisioning import**

Near the other local imports at the top of `main.py`, add:

```python
from .provisioning import (
    backfill,
    get_team_name,
    provision_shared_project,
    provision_user_workspace,
    scaffold_project_dir,
    set_team_name,
)
```

- [ ] **Step 3c: Wire the bootstrap handler**

In `def setup_bootstrap(...)`, after `profile = create_profile_for(user, ...)` and before `token = create_token(user["id"])`, insert:

```python
        team_name = payload.team_name or cfg.get("default_team_name") or "Team"
        set_team_name(db(), team_name)
        provision_user_workspace(db(), cfg, user)
        shared = None
        if payload.shared_project:
            shared_name = payload.shared_project.name or team_name
            shared = provision_shared_project(
                db(), cfg, validate_slug(payload.shared_project.slug), shared_name, user
            )
```

Then change the bootstrap `return {...}` to include the new fields:

```python
        return {
            "token": token,
            "user": public_user(user),
            "profile": profile_payload(profile),
            "team_name": team_name,
            "shared_project": project_payload(shared) if shared else None,
        }
```

(`validate_slug`, `public_user`, `profile_payload`, `project_payload`, `create_profile_for`, `db`, and `cfg` are already in scope in this module.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_bootstrap_sets_team_and_shared_project -q`
Expected: PASS — the response body now carries `team_name` and `shared_project`. (The `/api/setup/status` echo of the team name is added and tested in Task 10.)

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/main.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): bootstrap sets team name and first shared project"
```

---

## Task 9: Wire `create_user`

**Files:**
- Modify: `apps/api/hive_os_api/main.py` (the `create_user` handler)
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_create_user_provisions_workspace_and_joins_shared(tmp_path):
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={
            "username": "admin", "password": "password123",
            "profile_slug": "default", "profile_name": "Default",
            "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"},
        },
    ).json()
    token = boot["token"]
    resp = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "bob", "password": "password123", "role": "member",
              "profile_slug": "default", "profile_name": "Default"},
    )
    assert resp.status_code == 201, resp.text
    # bob can log in and sees BOTH his private project and the shared one
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "password123"}).json()["token"]
    projects = client.get("/api/projects", headers={"Authorization": f"Bearer {bob_token}"}).json()["projects"]
    slugs = {p["slug"] for p in projects}
    assert "bob" in slugs       # private
    assert "linc" in slugs      # shared
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_create_user_provisions_workspace_and_joins_shared -q`
Expected: FAIL — bob's project list is empty (`{"bob", "linc"}` not subset).

- [ ] **Step 3: Implement**

In `def create_user(...)`, after `profile = create_profile_for(created, ...)` and before `return {...}`, insert:

```python
        provision_user_workspace(db(), cfg, created)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_create_user_provisions_workspace_and_joins_shared -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/main.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): onboarding provisions user workspace"
```

---

## Task 10: Wire startup backfill + `setup_status` team name

**Files:**
- Modify: `apps/api/hive_os_api/main.py` (the `create_app` body near `init_db(...)`, and the `setup_status` handler)
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_startup_backfills_existing_users(tmp_path):
    # First app instance: bootstrap admin + shared, then create bob.
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default",
              "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"}},
    ).json()
    # Simulate a pre-existing user with NO workspace by inserting directly + deleting their projects.
    import sqlite3
    conn = sqlite3.connect(tmp_path / "db.sqlite")
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO users(username, os_user, role, password_hash) VALUES ('legacy','legacy','member','x')")
    conn.commit()
    conn.close()

    # Second app instance over the same DB triggers startup backfill.
    from fastapi.testclient import TestClient
    from hive_os_api.main import create_app
    app2 = create_app({
        "database_path": str(tmp_path / "db.sqlite"),
        "workspace_root": str(tmp_path / "ws"),
        "hermes_profiles_root": str(tmp_path / "profiles"),
        "projectctl_path": "/usr/bin/true", "start_worker": False,
    })
    with TestClient(app2) as client2:
        status = client2.get("/api/setup/status").json()
        assert status["team_name"] == "Linc"
        # legacy now has a private project
        import sqlite3 as s2
        c2 = s2.connect(tmp_path / "db.sqlite")
        c2.row_factory = s2.Row
        got = c2.execute("SELECT COUNT(*) AS c FROM projects WHERE slug = 'legacy'").fetchone()["c"]
        c2.close()
        assert got == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_startup_backfills_existing_users -q`
Expected: FAIL — `status["team_name"]` KeyError and/or legacy project count is 0.

- [ ] **Step 3a: Add `team_name` to `setup_status`**

In `def setup_status(...)`, change the returned dict to include the team name:

```python
        return {
            "bootstrap_required": count == 0,
            "mode": "team",
            "team_name": get_team_name(db(), cfg),
            "hermes_profiles_root": cfg["hermes_profiles_root"],
        }
```

- [ ] **Step 3b: Run backfill at startup**

In `create_app`, find the existing `init_db(app.state.db, ...)` call. Immediately after it, add:

```python
    if cfg.get("auto_provision", True):
        try:
            backfill(app.state.db, cfg)
        except Exception:
            logging.getLogger("hive_os.provisioning").exception("startup backfill failed")
```

(If `logging` is not already imported at the top of `main.py`, add `import logging`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py -q`
Expected: PASS (all provisioning tests, including the previously-deferred `status` assertions in Task 8's test — re-enable those two lines now if you commented them out).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/main.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): startup backfill + team name in setup status"
```

---

## Task 11: `create_project` scaffolds folders + enrolls shared

**Files:**
- Modify: `apps/api/hive_os_api/main.py` (the `create_project` handler)
- Test: `apps/api/tests/test_provisioning.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_provisioning.py`:

```python
def test_create_shared_project_enrolls_all_and_scaffolds(tmp_path):
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default",
              "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"}},
    ).json()
    token = boot["token"]
    # add a second user
    client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
                json={"username": "bob", "password": "password123", "role": "member",
                      "profile_slug": "default", "profile_name": "Default"})
    # admin creates ANOTHER shared project
    resp = client.post("/api/projects", headers={"Authorization": f"Bearer {token}"},
                       json={"slug": "ops", "name": "Ops", "visibility": "shared"})
    assert resp.status_code == 201, resp.text
    # folder scaffolded on disk
    assert (tmp_path / "ws" / "projects" / "ops" / "wiki").is_dir()
    # bob is auto-enrolled in the new shared project
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "password123"}).json()["token"]
    slugs = {p["slug"] for p in client.get("/api/projects", headers={"Authorization": f"Bearer {bob_token}"}).json()["projects"]}
    assert "ops" in slugs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_create_shared_project_enrolls_all_and_scaffolds -q`
Expected: FAIL — `ops/wiki` dir missing (projectctl is `/usr/bin/true`) and/or bob not enrolled.

- [ ] **Step 3: Implement**

In `def create_project(...)`, after the existing `run_projectctl("create-project", ...)` line, add a direct scaffold so folders exist regardless of projectctl:

```python
        scaffold_project_dir(cfg, payload.slug)
```

Then, after the owner membership row is inserted and before the `return`, add the shared-enrollment branch:

```python
        if payload.visibility == "shared":
            for row in db().execute("SELECT id FROM users").fetchall():
                if row["id"] != user["id"]:
                    db().execute(
                        "INSERT OR IGNORE INTO project_members(project_id, user_id, role) VALUES (?, ?, 'collaborator')",
                        (project_id, row["id"]),
                    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_provisioning.py::test_create_shared_project_enrolls_all_and_scaffolds -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/main.py apps/api/tests/test_provisioning.py
git commit -m "feat(api): create_project scaffolds folders and enrolls shared members"
```

---

## Final verification (whole feature)

- [ ] **Step 1: Run the entire backend test suite**

Run: `cd apps/api && uv run pytest -q`
Expected: PASS — all existing tests plus the new `test_provisioning.py` (≈17 new tests). No regressions.

- [ ] **Step 2: Sanity-check the module boundary**

Run: `cd apps/api && grep -n "fastapi\|import main" hive_os_api/provisioning.py || echo "clean: no FastAPI/main imports"`
Expected: `clean: no FastAPI/main imports` (provisioning.py stays pure).

- [ ] **Step 3: Confirm no unrelated files changed**

Run: `git diff --name-only main...onboarding-provisioning`
Expected: only `docs/superpowers/specs/...`, `docs/superpowers/plans/...`, `apps/api/hive_os_api/{db,settings,main,provisioning}.py`, `apps/api/tests/test_provisioning.py`. No frontend, no chat/file-explorer files.

- [ ] **Step 4: Final commit if anything is outstanding**

```bash
git add -A && git commit -m "test: full provisioning suite green" || echo "nothing to commit"
```

---

## Self-review notes (author)

- **Spec coverage:** team identity (Tasks 1, 8, 10) · private project (Task 3) · shared project + many-shared (Tasks 4, 11) · shared invariant both directions (Tasks 5, 11) · backfill (Tasks 6, 10) · error isolation (Task 5) · folder scaffold fixes projectctl-stub gap (Tasks 2, 11) · config (Task 7) · setup status team name (Task 10). All spec sections map to a task.
- **Access model:** all gating stays on `project_members`; `visibility` is only a bucket hint — consistent with the existing `list_projects` query.
- **Parallel safety:** only `main.py` (additive wiring) and `db.py` (additive `CREATE TABLE`) are shared with other workstreams; no frontend changes. Anchors are described by function/content because `main.py` is edited concurrently.
- **Naming consistency:** `provision_private_project`, `provision_shared_project`, `provision_user_workspace`, `ensure_member`, `scaffold_project_dir`, `backfill`, `get_team_name`/`set_team_name` are used identically across tasks and call sites.
