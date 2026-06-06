from __future__ import annotations

import shutil
from pathlib import Path

# Credential/config files Hermes reads at startup. Copied into each isolated
# profile HERMES_HOME so `hermes -z` can authenticate. Conversation state
# (sessions/, checkpoints/, logs/, backups/, *.bak*) is intentionally excluded
# so per-profile conversation isolation is preserved.
SEED_FILES: tuple[str, ...] = (".env", "auth.json", "config.yaml")


def seed_hermes_home(source: Path, target: Path) -> list[str]:
    """Copy credential/config files from source into target.

    Idempotent: never overwrites a file that already exists in target.
    No-op (returns []) when source is missing. Returns the names copied.
    """
    source = Path(source)
    target = Path(target)
    if not source.is_dir():
        return []
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in SEED_FILES:
        src = source / name
        dst = target / name
        if src.is_file() and not src.is_symlink() and not dst.exists():
            try:
                shutil.copy2(src, dst)
                copied.append(name)
            except OSError:
                continue
    return copied
