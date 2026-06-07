from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class RunnerDefinition:
    id: str
    display_name: str
    binary_names: tuple[str, ...]
    has_adapter: bool
    detection_only: bool = False
    notes: str = ""


# Hive OS runner registry.
#
# This is intentionally small and execution-oriented. It is inspired by the
# Minarflow OS registry, but not copied wholesale: Hive OS only exposes runners
# that make sense for the multi-user workspace console right now.
RUNNER_REGISTRY: tuple[RunnerDefinition, ...] = (
    RunnerDefinition("hermes", "Hermes", ("hermes",), True, notes="Hermes Agent CLI / gateway runner"),
    RunnerDefinition("claude-code", "Claude Code", ("claude",), True, notes="Anthropic Claude Code CLI"),
    RunnerDefinition("codex", "Codex", ("codex",), True, notes="OpenAI Codex CLI"),
    RunnerDefinition("opencode", "OpenCode", ("opencode",), True, notes="OpenCode CLI"),
    # Detected but not runnable until Hive OS has explicit adapters.
    RunnerDefinition("aider", "Aider", ("aider",), False, detection_only=True),
    RunnerDefinition("gemini", "Gemini CLI", ("gemini",), False, detection_only=True),
    RunnerDefinition("cursor-agent", "Cursor Agent", ("cursor-agent", "cursor"), False, detection_only=True),
)


def augmented_path(path_env: str | None = None) -> str:
    """PATH used by non-interactive service processes.

    GUI/server processes often miss Homebrew/user-local bins. Add the common
    local paths without replacing the provided environment.
    """

    base = path_env or os.environ.get("PATH", "")
    extras = (
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/bin"),
        "/home/linuxbrew/.linuxbrew/bin",
        "/usr/local/bin",
        "/opt/homebrew/bin",
    )
    parts = [p for p in base.split(os.pathsep) if p]
    for extra in extras:
        if extra not in parts:
            parts.append(extra)
    return os.pathsep.join(parts)


def resolve_binary(binary_name: str, path_env: str) -> str | None:
    return shutil.which(binary_name, path=path_env)


def detect_runners(path_env: str | None = None, registry: Iterable[RunnerDefinition] = RUNNER_REGISTRY) -> list[dict]:
    resolved_path = augmented_path(path_env)
    detected: list[dict] = []

    for runner in registry:
        if not runner.binary_names:
            detected.append(
                {
                    "id": runner.id,
                    "displayName": runner.display_name,
                    "installed": True,
                    "path": None,
                    "hasAdapter": runner.has_adapter,
                    "detectionOnly": runner.detection_only,
                    "runnable": runner.has_adapter,
                    "notes": runner.notes,
                }
            )
            continue

        found_path = None
        found_binary = None
        for binary in runner.binary_names:
            candidate = resolve_binary(binary, resolved_path)
            if candidate:
                found_path = candidate
                found_binary = binary
                break

        installed = found_path is not None
        detected.append(
            {
                "id": runner.id,
                "displayName": runner.display_name,
                "installed": installed,
                "path": found_path,
                "binary": found_binary,
                "hasAdapter": runner.has_adapter,
                "detectionOnly": runner.detection_only,
                "runnable": installed and runner.has_adapter,
                "notes": runner.notes,
            }
        )

    return detected


def _hermes_home_usable(home: str) -> bool:
    p = Path(home)
    return p.is_dir() and ((p / "auth.json").exists() or (p / "config.yaml").exists())


def hermes_status(source_home: str | None = None, path_env: str | None = None) -> dict:
    """Detect a usable Hermes runner without installing anything.

    Bring-your-own: reuse an existing `hermes` binary on PATH plus a Hermes home
    that has credentials/config. Returns ready + actionable guidance when not.
    """
    resolved = path_env if path_env is not None else augmented_path()
    binary = resolve_binary("hermes", resolved)
    home = source_home or os.path.expanduser("~/.hermes")
    home_ok = _hermes_home_usable(home)
    ready = bool(binary) and home_ok
    if ready:
        guidance = ""
    elif not binary and not home_ok:
        guidance = ("Hermes not found. Install the Hermes agent CLI, run `hermes -z` "
                    "to authenticate, then restart Hive. See docs/installation.md.")
    elif not binary:
        guidance = ("Hermes credentials found but the `hermes` binary is not on PATH. "
                    "Install/expose the Hermes CLI, then restart Hive.")
    else:
        guidance = (f"`hermes` is installed but no usable Hermes home at {home}. "
                    "Run `hermes -z` to authenticate, or set HIVEOS_SOURCE_HERMES_HOME.")
    return {"ready": ready, "binary": binary, "home": home if home_ok else None, "guidance": guidance}
