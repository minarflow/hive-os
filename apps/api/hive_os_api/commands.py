from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    description: str
    group: str
    surface: str
    unavailable_message: str | None = None


COMMANDS: tuple[CommandDefinition, ...] = (
    CommandDefinition("/help", "Show Hive OS chat commands", "Session", "hive"),
    CommandDefinition("/status", "Show current user/project/runner status", "Session", "hive"),
    CommandDefinition("/new", "Start a new session draft", "Session", "hive"),
    CommandDefinition("/session", "Show current session context", "Session", "hive"),
    CommandDefinition("/project", "Show or select project context", "Project", "hive"),
    CommandDefinition("/runner", "Show or switch active runner", "Runner", "hive"),
    CommandDefinition("/model", "Open/select model via UI", "Runner", "ui-owned", "/model is managed by Hive OS model picker, not raw chat."),
    CommandDefinition("/clear", "Terminal-only clear screen command", "Unavailable", "terminal-only", "/clear is terminal-only. Use /new or the Sessions sidebar in Hive OS."),
    CommandDefinition("/tools", "Terminal-only toolset command", "Unavailable", "terminal-only", "/tools is terminal-only. Use Runners/Settings in Hive OS."),
)

ALIASES = {
    "/reset": "/new",
    "/runners": "/runner",
}


def normalize_command(raw: str) -> tuple[str, str, bool]:
    text = raw.strip()
    force_raw = text.startswith("//")
    if force_raw:
        text = "/" + text[2:]
    if not text.startswith("/"):
        text = "/" + text
    name, _, arg = text.partition(" ")
    name = name.lower()
    name = ALIASES.get(name, name)
    return name, arg.strip(), force_raw


def command_catalog() -> dict:
    groups: dict[str, list[dict]] = {}
    for cmd in COMMANDS:
        groups.setdefault(cmd.group, []).append(
            {
                "name": cmd.name,
                "description": cmd.description,
                "surface": cmd.surface,
                "unavailableMessage": cmd.unavailable_message,
            }
        )
    return {"groups": [{"label": label, "commands": commands} for label, commands in groups.items()]}


def find_command(name: str) -> CommandDefinition | None:
    return next((cmd for cmd in COMMANDS if cmd.name == name), None)


def execute_command(raw_command: str, *, user: dict, project_slug: str | None = None, runner_id: str | None = None) -> dict:
    name, arg, force_raw = normalize_command(raw_command)

    if force_raw:
        return {
            "kind": "runner_raw",
            "command": name,
            "arg": arg,
            "message": f"Reserved raw runner passthrough: {name}{(' ' + arg) if arg else ''}",
        }

    cmd = find_command(name)
    if not cmd:
        return {
            "kind": "system_message",
            "surface": "unknown",
            "message": f"Unknown command: {name}. Use /help to see Hive OS commands. Use //{name.lstrip('/')} to reserve raw runner passthrough.",
        }

    if cmd.surface in {"terminal-only", "ui-owned"}:
        return {
            "kind": "system_message",
            "surface": cmd.surface,
            "message": cmd.unavailable_message or f"{name} is not available in chat.",
        }

    if name == "/help":
        names = ", ".join(c.name for c in COMMANDS if c.surface == "hive")
        return {"kind": "system_message", "surface": "hive", "message": f"Hive OS commands: {names}. Use //command for raw runner passthrough."}

    if name == "/status":
        return {
            "kind": "system_message",
            "surface": "hive",
            "message": f"User: {user['username']} ({user['role']}). Project: {project_slug or 'none'}. Runner: {runner_id or 'hermes'}. Command router: ready.",
        }

    if name == "/new":
        return {"kind": "new_session", "surface": "hive", "message": "New session draft ready."}

    if name == "/session":
        return {"kind": "system_message", "surface": "hive", "message": f"Session context: project={project_slug or 'none'}, runner={runner_id or 'hermes'}."}

    if name == "/project":
        if arg:
            return {"kind": "select_project", "surface": "hive", "projectSlug": arg, "message": f"Project switch requested: {arg}"}
        return {"kind": "system_message", "surface": "hive", "message": f"Current project: {project_slug or 'none'}."}

    if name == "/runner":
        if arg:
            return {"kind": "select_runner", "surface": "hive", "runnerId": arg, "message": f"Runner switch requested: {arg}"}
        return {"kind": "system_message", "surface": "hive", "message": f"Current runner: {runner_id or 'hermes'}."}

    return {"kind": "system_message", "surface": "hive", "message": f"Executed {name}."}
