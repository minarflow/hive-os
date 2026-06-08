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


# auth.json holds OAuth tokens the host rotates; config.yaml carries the
# provider/credential setup. A per-profile copy made once goes stale when the
# host's token rotates, so the profile's agent can no longer authenticate
# ("no output"). Refresh these from the live source before each run so every
# profile always runs on the host's current credentials.
REFRESH_FILES: tuple[str, ...] = ("auth.json", "config.yaml")


def refresh_hermes_credentials(source: Path, target: Path) -> list[str]:
    """Force-copy credential/config files from source into target (overwriting).

    Unlike seed_hermes_home this DOES overwrite, keeping shared-account profiles
    on the host's current auth. No-op when source or target is missing.
    """
    source = Path(source)
    target = Path(target)
    if not source.is_dir() or not target.is_dir():
        return []
    changed: list[str] = []
    for name in REFRESH_FILES:
        src = source / name
        dst = target / name
        if src.is_file() and not src.is_symlink():
            try:
                differs = (not dst.exists()) or src.read_bytes() != dst.read_bytes()
                if differs:
                    shutil.copy2(src, dst)
                    changed.append(name)
            except OSError:
                continue
    return changed
