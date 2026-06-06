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
