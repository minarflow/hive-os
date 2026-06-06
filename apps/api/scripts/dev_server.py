from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import uvicorn

from hive_os_api.main import create_app

ROOT = Path("/srv/hive-os-demo-api")
APP_DATA = Path(__file__).resolve().parents[1] / ".dev"
APP_DATA.mkdir(parents=True, exist_ok=True)
REPO = Path(__file__).resolve().parents[3]
HIVEOSCTL = REPO / "infra" / "scripts" / "hiveosctl"

app = create_app(
    {
        "database_path": str(APP_DATA / "hive-os-dev.db"),
        "workspace_root": str(ROOT),
        # UI dev mode uses DB-only project mutations; real ACL smoke is covered by
        # scripts/smoke_acl_api.py. This keeps the preview server from blocking on sudo.
        "projectctl_command": ["/usr/bin/true"],
        "seed_users": [
            {"username": "kuya", "os_user": "kuya", "role": "environment_admin"},
            {"username": "aris", "os_user": "aris", "role": "member"},
        ],
    }
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
