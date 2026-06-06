from __future__ import annotations

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
        (username, username, role, hash_password("password1"), iso_now()),
    )
    return dict(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


def test_team_name_round_trip_and_fallback(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    assert provisioning.get_team_name(conn, cfg) == "Team"  # fallback to cfg
    provisioning.set_team_name(conn, "Linc")
    assert provisioning.get_team_name(conn, cfg) == "Linc"


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


def test_provision_private_project(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    user = add_user(conn, "alice")
    project = provisioning.provision_private_project(conn, cfg, user)
    assert project["slug"] == "alice"
    assert project["visibility"] == "private"
    assert project["owner_user_id"] == user["id"]
    role = conn.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?", (project["id"], user["id"])
    ).fetchone()["role"]
    assert role == "owner"
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
    conn.execute(
        "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES ('team', 'Team', '/x', ?, 'shared')",
        (admin["id"],),
    )
    user = add_user(conn, "team")
    project = provisioning.provision_private_project(conn, cfg, user)
    assert project["slug"] == "team-home"


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


def test_user_workspace_joins_existing_shared(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    bob = add_user(conn, "bob")
    provisioning.provision_user_workspace(conn, cfg, bob)
    assert conn.execute("SELECT COUNT(*) AS c FROM projects WHERE slug = 'bob'").fetchone()["c"] == 1
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
    provisioning.provision_user_workspace(conn, cfg, bob)  # must NOT raise
    actions = [r["action"] for r in conn.execute("SELECT action FROM audit_log").fetchall()]
    assert "workspace.provision.error" in actions


def test_auto_provision_disabled_is_noop(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    cfg["auto_provision"] = False
    bob = add_user(conn, "bob")
    provisioning.provision_user_workspace(conn, cfg, bob)
    assert conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"] == 0


def test_backfill_all_users(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    add_user(conn, "bob")
    add_user(conn, "carol")
    provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    summary = provisioning.backfill(conn, cfg)
    assert summary["users"] == 3
    assert conn.execute("SELECT COUNT(*) AS c FROM projects WHERE visibility = 'private'").fetchone()["c"] == 3
    shared_id = conn.execute("SELECT id FROM projects WHERE slug = 'linc'").fetchone()["id"]
    assert conn.execute("SELECT COUNT(*) AS c FROM project_members WHERE project_id = ?", (shared_id,)).fetchone()["c"] == 3


def test_backfill_idempotent(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    add_user(conn, "bob")
    provisioning.backfill(conn, cfg)
    provisioning.backfill(conn, cfg)
    assert conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"] == 1


def test_default_config_has_provisioning_keys():
    from hive_os_api.settings import normalize_config

    cfg = normalize_config()
    assert cfg["default_team_name"] == "Team"
    assert cfg["provision_starter_dirs"] == ["wiki", "tasks", "artifacts"]
    assert cfg["auto_provision"] is True


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


def test_create_user_provisions_workspace_and_joins_shared(tmp_path):
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default",
              "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"}},
    ).json()
    token = boot["token"]
    resp = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "bob", "password": "password123", "role": "member",
              "profile_slug": "default", "profile_name": "Default"},
    )
    assert resp.status_code == 201, resp.text
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "password123"}).json()["token"]
    projects = client.get("/api/projects", headers={"Authorization": f"Bearer {bob_token}"}).json()["projects"]
    slugs = {p["slug"] for p in projects}
    assert "bob" in slugs
    assert "linc" in slugs


def test_startup_backfills_existing_users(tmp_path):
    client = _client(tmp_path)
    client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default",
              "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"}},
    ).json()
    import sqlite3
    conn = sqlite3.connect(tmp_path / "db.sqlite")
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO users(username, os_user, role, password_hash) VALUES ('legacy','legacy','member','x')")
    conn.commit()
    conn.close()

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
        import sqlite3 as s2
        c2 = s2.connect(tmp_path / "db.sqlite")
        c2.row_factory = s2.Row
        got = c2.execute("SELECT COUNT(*) AS c FROM projects WHERE slug = 'legacy'").fetchone()["c"]
        c2.close()
        assert got == 1


def test_create_shared_project_enrolls_all_and_scaffolds(tmp_path):
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default",
              "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"}},
    ).json()
    token = boot["token"]
    client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
                json={"username": "bob", "password": "password123", "role": "member",
                      "profile_slug": "default", "profile_name": "Default"})
    resp = client.post("/api/projects", headers={"Authorization": f"Bearer {token}"},
                       json={"slug": "ops", "name": "Ops", "visibility": "shared"})
    assert resp.status_code == 201, resp.text
    assert (tmp_path / "ws" / "projects" / "ops" / "wiki").is_dir()
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "password123"}).json()["token"]
    slugs = {p["slug"] for p in client.get("/api/projects", headers={"Authorization": f"Bearer {bob_token}"}).json()["projects"]}
    assert "ops" in slugs


def test_bootstrap_bad_shared_slug_is_422_not_partial(tmp_path):
    client = _client(tmp_path)
    resp = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default",
              "team_name": "Linc", "shared_project": {"slug": "Bad Slug!", "name": "X"}},
    )
    assert resp.status_code == 422  # rejected before any DB write
    # bootstrap is still possible (no half-created admin locking it out)
    assert client.get("/api/setup/status").json()["bootstrap_required"] is True


def test_provision_private_when_owns_shared_same_slug_uses_home(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "linc", role="environment_admin")
    provisioning.provision_shared_project(conn, cfg, "linc", "Linc", admin)
    project = provisioning.provision_private_project(conn, cfg, admin)
    assert project["slug"] == "linc-home"
    assert project["visibility"] == "private"


def test_provision_shared_rejects_non_shared_slug(tmp_path):
    conn = make_db()
    cfg = make_cfg(tmp_path)
    alice = add_user(conn, "alice")
    provisioning.provision_private_project(conn, cfg, alice)  # owns private slug 'alice'
    import pytest
    with pytest.raises(ValueError):
        provisioning.provision_shared_project(conn, cfg, "alice", "Alice", alice)


def test_bootstrap_admin_name_equals_shared_slug(tmp_path):
    client = _client(tmp_path)
    boot = client.post("/api/setup/bootstrap", json={
        "username": "linc", "password": "password123",
        "profile_slug": "default", "profile_name": "Default",
        "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"}}).json()
    assert boot["shared_project"]["slug"] == "linc"
    assert boot["shared_project"]["visibility"] == "shared"
    token = boot["token"]
    import sqlite3
    c = sqlite3.connect(tmp_path / "db.sqlite"); c.row_factory = sqlite3.Row
    vis = {r["slug"]: r["visibility"] for r in c.execute("SELECT slug, visibility FROM projects").fetchall()}
    c.close()
    assert vis.get("linc") == "shared"
    assert vis.get("linc-home") == "private"  # admin private took the -home suffix
    client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
                json={"username": "bob", "password": "password123", "role": "member",
                      "profile_slug": "default", "profile_name": "Default"})
    bob_token = client.post("/auth/login", json={"username": "bob", "password": "password123"}).json()["token"]
    slugs = {p["slug"] for p in client.get("/api/projects", headers={"Authorization": f"Bearer {bob_token}"}).json()["projects"]}
    assert "linc" in slugs  # later user enrolled in the shared project


# ---------------------------------------------------------------------------
# FIX 1 — cross-user leak on double slug collision
# ---------------------------------------------------------------------------

def test_private_project_never_joins_another_users_project(tmp_path):
    """User B named 'team' must NOT become owner of user A's 'team-home' project."""
    conn = make_db()
    cfg = make_cfg(tmp_path)

    # User A is named "team-home" and already has their own private project.
    user_a = add_user(conn, "team-home")
    proj_a = provisioning.provision_private_project(conn, cfg, user_a)
    assert proj_a["slug"] == "team-home"

    # A shared project occupies the slug "team" so user B can't use it directly.
    admin = add_user(conn, "admin", role="environment_admin")
    conn.execute(
        "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES ('team', 'Team', '/x', ?, 'shared')",
        (admin["id"],),
    )

    # User B is named "team".
    user_b = add_user(conn, "team")
    proj_b = provisioning.provision_private_project(conn, cfg, user_b)

    # B must NOT have slug 'team-home' (that belongs to A).
    assert proj_b["slug"] != "team-home", "B stole A's slug"
    # B must NOT be a member of A's project.
    b_in_a = conn.execute(
        "SELECT COUNT(*) AS c FROM project_members WHERE project_id = ? AND user_id = ?",
        (proj_a["id"], user_b["id"]),
    ).fetchone()["c"]
    assert b_in_a == 0, "B was added as member of A's project (cross-user leak)"
    # A's project must only have A as member.
    a_members = conn.execute(
        "SELECT user_id FROM project_members WHERE project_id = ?", (proj_a["id"],)
    ).fetchall()
    assert len(a_members) == 1 and a_members[0]["user_id"] == user_a["id"]
    # B's project must be owned by B and be private.
    assert proj_b["owner_user_id"] == user_b["id"]
    assert proj_b["visibility"] == "private"


# ---------------------------------------------------------------------------
# FIX 2 — bootstrap shared-project failure is non-fatal
# ---------------------------------------------------------------------------

def test_bootstrap_shared_failure_is_non_fatal(tmp_path, monkeypatch):
    """If provision_shared_project raises during bootstrap, the response is still 201."""
    from fastapi.testclient import TestClient
    from hive_os_api.main import create_app
    import hive_os_api.main as main_mod

    def boom(*a, **k):
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(main_mod, "provision_shared_project", boom)

    app = create_app({
        "database_path": str(tmp_path / "db.sqlite"),
        "workspace_root": str(tmp_path / "ws"),
        "hermes_profiles_root": str(tmp_path / "profiles"),
        "projectctl_path": "/usr/bin/true",
        "start_worker": False,
    })
    client = TestClient(app)
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
    # Token must be returned.
    assert body.get("token")
    # bootstrap_required must now be false (admin was committed).
    status_resp = client.get("/api/setup/status")
    assert status_resp.json()["bootstrap_required"] is False
    # shared_project must be None (it failed).
    assert body.get("shared_project") is None
    # A warning must be present.
    assert body.get("warning"), f"Expected warning in response, got: {body}"


# ---------------------------------------------------------------------------
# FIX 3 — enroll_all_users_as_members helper used by create_project
# ---------------------------------------------------------------------------

def test_enroll_all_users_as_members_helper(tmp_path):
    """enroll_all_users_as_members enrolls all users and emits audit entries."""
    conn = make_db()
    cfg = make_cfg(tmp_path)
    admin = add_user(conn, "admin", role="environment_admin")
    bob = add_user(conn, "bob")

    cur = conn.execute(
        "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES ('ops', 'Ops', '/x', ?, 'shared')",
        (admin["id"],),
    )
    project_id = cur.lastrowid

    provisioning.enroll_all_users_as_members(conn, project_id, admin["id"])

    members = {
        r["user_id"]: r["role"]
        for r in conn.execute(
            "SELECT user_id, role FROM project_members WHERE project_id = ?", (project_id,)
        ).fetchall()
    }
    assert members[admin["id"]] == "owner"
    assert members[bob["id"]] == "collaborator"

    actions = [r["action"] for r in conn.execute("SELECT action FROM audit_log").fetchall()]
    assert "workspace.provision.member" in actions


def test_create_shared_project_uses_enroll_helper_audit(tmp_path):
    """POST /api/projects with shared visibility emits workspace.provision.member audit entries."""
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default",
              "team_name": "Linc", "shared_project": {"slug": "linc", "name": "Linc"}},
    ).json()
    token = boot["token"]
    client.post("/api/users", headers={"Authorization": f"Bearer {token}"},
                json={"username": "bob", "password": "password123", "role": "member",
                      "profile_slug": "default", "profile_name": "Default"})

    resp = client.post("/api/projects", headers={"Authorization": f"Bearer {token}"},
                       json={"slug": "ops", "name": "Ops", "visibility": "shared"})
    assert resp.status_code == 201, resp.text

    import sqlite3
    conn = sqlite3.connect(tmp_path / "db.sqlite")
    conn.row_factory = sqlite3.Row
    actions = [r["action"] for r in conn.execute("SELECT action FROM audit_log").fetchall()]
    conn.close()
    assert "workspace.provision.member" in actions


# ---------------------------------------------------------------------------
# FIX 4 — validate team_name and shared project name lengths
# ---------------------------------------------------------------------------

def test_bootstrap_team_name_too_long_is_422(tmp_path):
    """team_name longer than 80 chars must be rejected with 422."""
    client = _client(tmp_path)
    resp = client.post(
        "/api/setup/bootstrap",
        json={
            "username": "admin",
            "password": "password123",
            "profile_slug": "default",
            "profile_name": "Default",
            "team_name": "A" * 81,
        },
    )
    assert resp.status_code == 422, resp.text


def test_project_create_name_too_long_is_422(tmp_path):
    """Project name longer than 120 chars must be rejected with 422."""
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default"},
    ).json()
    token = boot["token"]
    resp = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"slug": "ops", "name": "N" * 121, "visibility": "private"},
    )
    assert resp.status_code == 422, resp.text


def test_project_create_empty_name_is_422(tmp_path):
    """Project name that is empty (or whitespace-only) must be rejected with 422."""
    client = _client(tmp_path)
    boot = client.post(
        "/api/setup/bootstrap",
        json={"username": "admin", "password": "password123",
              "profile_slug": "default", "profile_name": "Default"},
    ).json()
    token = boot["token"]
    resp = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"slug": "ops", "name": "   ", "visibility": "private"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# FIX 5 — defense-in-depth in scaffold_project_dir
# ---------------------------------------------------------------------------

def test_scaffold_rejects_unsafe_slug(tmp_path):
    """scaffold_project_dir must raise ValueError for slugs containing path-traversal chars."""
    import pytest
    cfg = make_cfg(tmp_path)
    with pytest.raises(ValueError, match="unsafe slug"):
        provisioning.scaffold_project_dir(cfg, "../evil")
    with pytest.raises(ValueError, match="unsafe slug"):
        provisioning.scaffold_project_dir(cfg, "foo/bar")
    with pytest.raises(ValueError, match="unsafe slug"):
        provisioning.scaffold_project_dir(cfg, ".hidden")
    with pytest.raises(ValueError, match="unsafe slug"):
        provisioning.scaffold_project_dir(cfg, "foo\\bar")
