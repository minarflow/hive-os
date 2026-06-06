from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("hive_os.provisioning")


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
