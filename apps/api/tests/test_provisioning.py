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
