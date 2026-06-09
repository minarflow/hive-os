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
    # Host dir the agent's login lives in (~ is expanded at use). Hive copies the
    # listed files into each new profile home so the agent is authenticated out of
    # the box, and re-copies refresh_files before each run to follow token rotation.
    source_dir: str = ""
    seed_files: tuple[str, ...] = ()
    refresh_files: tuple[str, ...] = ()


RUNNER_SPECS: dict[str, RunnerSpec] = {
    "hermes": RunnerSpec(
        id="hermes",
        spawn_argv=["hermes", "acp", "--accept-hooks"],
        home_env="HERMES_HOME",
        binary="hermes",
        display_name="Hermes",
        auth_hint="Install the Hermes CLI and authenticate (e.g. `hermes -z`).",
        source_dir="~/.hermes",
        seed_files=(".env", "auth.json", "config.yaml"),
        refresh_files=("auth.json", "config.yaml"),
    ),
    "claude-code": RunnerSpec(
        id="claude-code",
        spawn_argv=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
        home_env="CLAUDE_CONFIG_DIR",
        binary="claude",
        display_name="Claude Code",
        auth_hint="Install Claude Code and run `claude /login` (or set ANTHROPIC_API_KEY).",
        source_dir="~/.claude",
        seed_files=(".credentials.json", ".claude.json"),
        refresh_files=(".credentials.json",),
    ),
    "codex": RunnerSpec(
        id="codex",
        spawn_argv=["npx", "-y", "@zed-industries/codex-acp"],
        home_env="CODEX_HOME",
        binary="codex",
        display_name="Codex",
        auth_hint="Install the Codex CLI and run `codex login` (or set OPENAI_API_KEY).",
        source_dir="~/.codex",
        seed_files=("auth.json", "config.toml"),
        refresh_files=("auth.json",),
    ),
    "gemini": RunnerSpec(
        id="gemini",
        spawn_argv=["gemini", "--experimental-acp"],
        # Gemini CLI is the one native-ACP agent; it uses its global ~/.gemini
        # login (no per-profile home_env wired yet — verify on a host with it).
        home_env="",
        binary="gemini",
        display_name="Gemini CLI",
        auth_hint="Install the Gemini CLI and log in (or set GEMINI_API_KEY).",
        source_dir="~/.gemini",
        seed_files=(),
        refresh_files=(),
    ),
}

DEFAULT_RUNNER = "hermes"


def runner_spec(runner_id: str | None) -> RunnerSpec:
    return RUNNER_SPECS.get(runner_id or DEFAULT_RUNNER, RUNNER_SPECS[DEFAULT_RUNNER])
