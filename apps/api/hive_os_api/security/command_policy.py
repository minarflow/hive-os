from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandDecision:
    allowed: bool
    category: str
    reason: str
    argv: list[str]


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _has_any(argv: list[str], *flags: str) -> bool:
    return any(arg in flags for arg in argv)


def _pipe_to_shell(command: str) -> bool:
    lowered = command.lower()
    return ("curl" in lowered or "wget" in lowered) and ("| bash" in lowered or "| sh" in lowered or "bash -" in lowered or "sh -" in lowered)


def classify_command(command: str | list[str], cwd: str | Path, project_root: str | Path) -> CommandDecision:
    """Classify command safety for app-level Team Mode.

    Policy:
    - project-local dependency installs are allowed when cwd stays inside project_root.
    - global/system installs are blocked automatically.
    - unknown commands are allowed only as non-install project commands for now.

    This classifier is intentionally conservative for install-like commands. It is
    designed to be called before a runner/tool executes shell commands.
    """

    raw = command if isinstance(command, str) else " ".join(shlex.quote(part) for part in command)
    try:
        argv = shlex.split(raw) if isinstance(command, str) else list(command)
    except ValueError:
        return CommandDecision(False, "parse_error", "command could not be parsed safely", [])

    if not argv:
        return CommandDecision(False, "empty", "empty command", argv)

    cwd_path = Path(cwd)
    root_path = Path(project_root)
    if not _inside(cwd_path, root_path):
        return CommandDecision(False, "outside_project", "command cwd is outside the project root", argv)

    exe = Path(argv[0]).name

    if exe == "sudo":
        return CommandDecision(False, "global_install", "sudo is blocked for normal app users", argv)

    if exe in {"apt", "apt-get", "dpkg", "snap", "flatpak", "brew", "pacman", "dnf", "yum", "zypper"}:
        return CommandDecision(False, "global_install", f"{exe} changes system packages and is blocked", argv)

    if _pipe_to_shell(raw):
        return CommandDecision(False, "remote_script", "remote install scripts piped to shell are blocked", argv)

    if exe in {"npm", "pnpm", "yarn", "bun"}:
        if _has_any(argv, "-g", "--global") or "global" in argv:
            return CommandDecision(False, "global_install", "global Node package installs are blocked", argv)
        if _has_any(argv, "--prefix"):
            idx = argv.index("--prefix") if "--prefix" in argv else -1
            if idx >= 0 and idx + 1 < len(argv) and not _inside(cwd_path / argv[idx + 1], root_path):
                return CommandDecision(False, "outside_project", "install prefix points outside the project", argv)
        if any(arg in {"install", "i", "add"} for arg in argv[1:]):
            return CommandDecision(True, "project_local_install", "project-local Node dependency install allowed", argv)

    if exe in {"pip", "pip3"} or (exe in {"python", "python3"} and argv[1:3] == ["-m", "pip"]):
        if _has_any(argv, "--user", "--break-system-packages"):
            return CommandDecision(False, "global_install", "pip user/system installs are blocked", argv)
        if "install" in argv:
            if "--target" in argv:
                idx = argv.index("--target")
                if idx + 1 >= len(argv) or not _inside(cwd_path / argv[idx + 1], root_path):
                    return CommandDecision(False, "outside_project", "pip --target must stay inside project", argv)
            return CommandDecision(True, "project_local_install", "project-local Python dependency install allowed", argv)

    if exe in {"python", "python3"} and argv[1:3] == ["-m", "venv"]:
        target = cwd_path / (argv[3] if len(argv) > 3 else ".venv")
        if not _inside(target, root_path):
            return CommandDecision(False, "outside_project", "virtualenv target must stay inside project", argv)
        return CommandDecision(True, "project_local_install", "project-local virtualenv creation allowed", argv)

    if exe == "uv":
        if any(arg in {"add", "sync", "install"} for arg in argv[1:]):
            return CommandDecision(True, "project_local_install", "project-local uv dependency operation allowed", argv)

    if exe == "cargo":
        if len(argv) > 1 and argv[1] == "install":
            return CommandDecision(False, "global_install", "cargo install writes outside the project by default", argv)
        if len(argv) > 1 and argv[1] in {"add", "build", "test", "check"}:
            return CommandDecision(True, "project_local_install", "project-local Rust dependency/build operation allowed", argv)

    if exe == "go":
        if len(argv) > 1 and argv[1] == "install":
            return CommandDecision(False, "global_install", "go install writes to global/user bin and is blocked", argv)
        if len(argv) > 1 and argv[1] in {"get", "mod", "build", "test"}:
            return CommandDecision(True, "project_local_install", "project-local Go dependency/build operation allowed", argv)

    if exe in {"pipx", "gem"} and "install" in argv:
        return CommandDecision(False, "global_install", f"{exe} install is treated as global and blocked", argv)

    return CommandDecision(True, "project_command", "non-global project command allowed", argv)
