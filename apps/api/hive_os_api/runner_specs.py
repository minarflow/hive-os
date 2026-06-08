from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunnerSpec:
    id: str
    spawn_argv: list[str]
    home_env: str          # env var that points the agent at its per-profile home
    binary: str            # the underlying CLI that must be installed/authenticated
    display_name: str
    auth_hint: str = ""


RUNNER_SPECS: dict[str, RunnerSpec] = {
    "hermes": RunnerSpec(
        id="hermes",
        spawn_argv=["hermes", "acp", "--accept-hooks"],
        home_env="HERMES_HOME",
        binary="hermes",
        display_name="Hermes",
        auth_hint="Install the Hermes CLI and authenticate (e.g. `hermes -z`).",
    ),
    "claude-code": RunnerSpec(
        id="claude-code",
        spawn_argv=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
        home_env="CLAUDE_CONFIG_DIR",
        binary="claude",
        display_name="Claude Code",
        auth_hint="Install Claude Code and run `claude /login` (or set ANTHROPIC_API_KEY).",
    ),
}

DEFAULT_RUNNER = "hermes"


def runner_spec(runner_id: str | None) -> RunnerSpec:
    return RUNNER_SPECS.get(runner_id or DEFAULT_RUNNER, RUNNER_SPECS[DEFAULT_RUNNER])
