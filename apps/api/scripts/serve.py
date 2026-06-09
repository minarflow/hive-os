from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from hive_os_api.main import create_app


def env_path(name: str, default: Path) -> str:
    return os.environ.get(name, str(default))


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def default_data_dir() -> Path:
    """Per-OS default for runtime data (DB, projects, profiles). Overridable via
    HIVEOS_WORKSPACE_ROOT."""
    if os.name == "nt":  # Windows
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "hive-os"
    if sys.platform == "darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "hive-os"
    return Path.home() / ".local" / "share" / "hive-os"  # Linux/XDG


workspace_root = Path(env_path("HIVEOS_WORKSPACE_ROOT", default_data_dir()))
web_dist = Path(env_path("HIVEOS_WEB_DIST", REPO_ROOT / "apps/web/dist"))
projectctl = Path(env_path("HIVEOS_PROJECTCTL", REPO_ROOT / "infra/scripts/hiveosctl"))

app = create_app(
    {
        "database_path": env_path("HIVEOS_DB_PATH", workspace_root / "hive-os.db"),
        "workspace_root": str(workspace_root),
        "hermes_profiles_root": env_path("HIVEOS_HERMES_PROFILES_ROOT", workspace_root / "hermes-profiles"),
        "projectctl_path": str(projectctl),
        "projectctl_command": os.environ.get("HIVEOS_PROJECTCTL_COMMAND", "").split() or None,
        # Off by default (single-user $HOME install). The /srv multi-user root
        # deployment sets HIVEOS_MANAGE_OS_ACL=1 to enable ownership/ACL ops.
        "manage_os_acl": env_bool("HIVEOS_MANAGE_OS_ACL", False),
        "web_dist_path": str(web_dist),
        "public_base_url": os.environ.get("HIVEOS_PUBLIC_BASE_URL") or None,
        "source_hermes_home": os.environ.get("HIVEOS_SOURCE_HERMES_HOME") or None,
        "hermes_bin": os.environ.get("HIVEOS_HERMES_BIN") or None,
        "refresh_credentials": env_bool("HIVEOS_REFRESH_CREDENTIALS", True),
        "run_timeout_seconds": env_int("HIVEOS_RUN_TIMEOUT_SECONDS", 900),
        "run_worker_poll_interval_ms": env_int("HIVEOS_RUN_WORKER_POLL_MS", 250),
        "seed_users": [],
    }
)


if __name__ == "__main__":
    uvicorn.run(app, host=os.environ.get("HIVEOS_HOST", "127.0.0.1"), port=env_int("HIVEOS_PORT", 8765))
