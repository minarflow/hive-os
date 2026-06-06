#!/usr/bin/env python
"""Seed demo data into a Hive OS instance (idempotent).

Creates a small team, a shared project, interlinked wiki notes (personal +
project) so the wiki Graph/Search/backlinks have something to show, and a couple
of chat sessions.

Config comes from the same env vars the dev/serve scripts use; defaults target
the dev workspace (~/.local/share/hive-os-dev). Safe to re-run.

Usage:
    cd apps/api && uv run python scripts/seed_demo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from hive_os_api import provisioning  # noqa: E402
from hive_os_api.auth import hash_password, iso_now  # noqa: E402
from hive_os_api.db import connect, init_db  # noqa: E402
from hive_os_api.profile_seed import seed_hermes_home  # noqa: E402
from hive_os_api.settings import hermes_home_for, normalize_config  # noqa: E402

DEV_ROOT = os.environ.get("HIVEOS_DEV_ROOT", os.path.expanduser("~/.local/share/hive-os-dev"))
cfg = normalize_config({
    "database_path": os.environ.get("HIVEOS_DB_PATH", f"{DEV_ROOT}/hive-os-dev.db"),
    "workspace_root": os.environ.get("HIVEOS_WORKSPACE_ROOT", DEV_ROOT),
    "source_hermes_home": os.environ.get("HIVEOS_SOURCE_HERMES_HOME", os.path.expanduser("~/.hermes")),
})

conn = connect(cfg["database_path"])
init_db(conn, source_hermes_home=cfg["source_hermes_home"])


def ensure_user(username: str, role: str) -> dict:
    conn.execute(
        "INSERT OR IGNORE INTO users(username, os_user, role, password_hash, password_set_at) VALUES (?, ?, ?, ?, ?)",
        (username, username, role, hash_password("password123"), iso_now()),
    )
    return dict(conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone())


def ensure_profile(user: dict) -> dict:
    row = conn.execute("SELECT * FROM profiles WHERE user_id = ? ORDER BY is_default DESC, id LIMIT 1", (user["id"],)).fetchone()
    if row:
        return dict(row)
    home = hermes_home_for(cfg, user["username"], "default")
    Path(home).mkdir(parents=True, exist_ok=True)
    seed_hermes_home(Path(cfg["source_hermes_home"]), Path(home))
    cur = conn.execute(
        "INSERT INTO profiles(user_id, slug, name, hermes_home, is_default) VALUES (?, 'default', 'Default', ?, 1)",
        (user["id"], str(home)),
    )
    return dict(conn.execute("SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)).fetchone())


def ensure_session(title: str, project_id, owner_id: int, profile_id: int, turns: list[tuple[str, str]]) -> None:
    if conn.execute("SELECT id FROM sessions WHERE title = ? AND owner_user_id = ?", (title, owner_id)).fetchone():
        return
    cur = conn.execute(
        "INSERT INTO sessions(title, project_id, owner_user_id, profile_id, runner_id, visibility) VALUES (?, ?, ?, ?, 'hermes', 'private')",
        (title, project_id, owner_id, profile_id),
    )
    sid = cur.lastrowid
    for role, content in turns:
        conn.execute("INSERT INTO messages(session_id, role, content) VALUES (?, ?, ?)", (sid, role, content))


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ── Team + users + shared project ─────────────────────────────────────
provisioning.set_team_name(conn, os.environ.get("HIVEOS_TEAM_NAME", "Linc"))
admin = ensure_user("kuya", "environment_admin")
aris = ensure_user("aris", "member")
iqbal = ensure_user("iqbal", "member")
for u in (admin, aris, iqbal):
    ensure_profile(u)
    provisioning.provision_user_workspace(conn, cfg, u)
shared = provisioning.provision_shared_project(conn, cfg, "deltapack", "Deltapack", admin)

# ── Personal wiki for admin (interlinked knowledge graph) ─────────────
personal = Path(cfg["workspace_root"]) / "users" / admin["username"] / "wiki"
PERSONAL = {
    "index.md": "# Home\n\nMap of content:\n\n- [[hive-os]]\n- [[hermes]]\n- [[architecture]]\n- [[ideas]]\n",
    "hive-os.md": "# Hive OS\n\nTeam-mode PWA for human + AI agents.\n\nSee [[architecture]], runs on [[hermes]], notes in [[wiki]].\n",
    "hermes.md": "# Hermes\n\nThe first [[runners|runner]]. Powers [[hive-os]] chat.\n",
    "runners.md": "# Runners\n\nRunner-agnostic layer. [[hermes]] is first; Claude Code/Codex later.\n",
    "architecture.md": "# Architecture\n\nFastAPI + SQLite + React PWA. Access control in [[security]]. Part of [[hive-os]].\n",
    "security.md": "# Security\n\nApp-level ACL now; POSIX ACL later. Backs [[architecture]].\n",
    "wiki.md": "# Wiki\n\nObsidian-like: [[wikilinks]], backlinks, graph. Used across [[hive-os]] and captured in [[ideas]].\n",
    "ideas.md": "# Ideas\n\n- Session continuity to [[hermes]] gateway\n- Tags + daily notes in [[wiki]]\n- More [[runners]]\n",
}
for name, body in PERSONAL.items():
    write(personal, name, body)

# ── Shared project wiki (deltapack) ───────────────────────────────────
proj_wiki = Path(shared["path"]) / "wiki"
PROJECT = {
    "overview.md": "# Deltapack — Overview\n\nShared team workspace. See [[roadmap]] and the [[team]].\n",
    "roadmap.md": "# Roadmap\n\nFrom [[overview]] to shipping. Tracked in [[milestones]].\n",
    "milestones.md": "# Milestones\n\n- v1 chat\n- v2 wiki\n\nBack to [[roadmap]].\n",
    "team.md": "# Team\n\nkuya (owner), aris, iqbal. See [[overview]].\n",
}
for name, body in PROJECT.items():
    write(proj_wiki, name, body)

# ── A couple of chat sessions for the admin ───────────────────────────
admin_profile = ensure_profile(admin)
ensure_session(
    "Welcome to Hive OS", None, admin["id"], admin_profile["id"],
    [("user", "Apa itu Hive OS?"), ("assistant", "Hive OS adalah workspace tim untuk kolaborasi manusia + agen AI. Lihat wiki untuk detail.")],
)
ensure_session(
    "Deltapack kickoff", shared["id"], admin["id"], admin_profile["id"],
    [("user", "Bantu rencanakan deltapack"), ("assistant", "Mulai dari overview & roadmap di wiki project ini.")],
)

print("Seeded:")
print(f"  users      : kuya (admin), aris, iqbal  [password: password123]")
print(f"  shared proj: deltapack ({shared['path']})")
print(f"  personal wiki notes: {len(PERSONAL)} -> {personal}")
print(f"  project wiki notes : {len(PROJECT)} -> {proj_wiki}")
print("  sessions   : 2")
