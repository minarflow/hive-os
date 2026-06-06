from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("hive_os.provisioning")


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


def ensure_member(conn: sqlite3.Connection, project_id: int, user_id: int, role: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO project_members(project_id, user_id, role) VALUES (?, ?, ?)",
        (project_id, user_id, role),
    )


def _audit(conn: sqlite3.Connection, actor_user_id, action: str, slug: str, metadata: str = "{}") -> None:
    conn.execute(
        "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, metadata) "
        "VALUES (?, ?, 'project', ?, ?)",
        (actor_user_id, action, slug, metadata),
    )


def provision_private_project(conn: sqlite3.Connection, cfg: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    slug = user["username"]
    existing = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
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


def provision_shared_project(conn: sqlite3.Connection, cfg: dict[str, Any], slug: str, name: str, owner: dict[str, Any]) -> dict[str, Any]:
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


def get_team_name(conn: sqlite3.Connection, cfg: dict[str, Any]) -> str:
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'team_name'").fetchone()
    if row and row["value"]:
        return row["value"]
    return cfg.get("default_team_name") or "Team"


def set_team_name(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO app_settings(key, value) VALUES ('team_name', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
        (name,),
    )
