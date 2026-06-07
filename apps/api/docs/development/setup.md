# Development Setup and Tools

## Requirements

- Linux server or Linux dev machine
- Python 3.11+
- `uv` for Python dependency management
- `pytest` via the project dev dependency group
- Hermes CLI available on `PATH` only when testing real runner execution

## Repository

API app path:

```bash
/path/to/hive-os/apps/api
```

Main package:

```text
hive_os_api/
```

Tests:

```text
tests/
```

Docs:

```text
docs/
```

## Install dependencies

Use `uv`; do not hand-edit virtualenv contents.

```bash
cd /path/to/hive-os/apps/api
uv sync --dev
```

If a dependency must be added, follow [package policy](./package-policy.md).

## Run tests

```bash
cd /path/to/hive-os/apps/api
uv run pytest -q
```

## Run dev server

```bash
cd /path/to/hive-os/apps/api
uv run uvicorn hive_os_api.main:app --host 127.0.0.1 --port 8765
```

Do not expose the development server to `0.0.0.0` unless explicitly testing LAN access and authentication/security implications are understood.

## Safe development workflow for Hermes/Claude Code

Before changing code:

1. Read `docs/README.md` and the specific security doc relevant to the change.
2. Identify whether the change touches auth, file access, runner execution, command routing, or project membership.
3. If yes, add/update tests that prove denial and allowance behavior.
4. Never loosen source, hidden-file, or secret access only to make a test pass.

Before finishing:

1. Run `uv run pytest -q`.
2. Mention any tests not run.
3. Update docs if behavior changed.

## Local data

Prototype/dev data may live under `.dev/`. Treat dev databases as disposable, but still do not commit personal tokens, production paths, or secrets.

## Tooling expectations

- Prefer `uv run ...` for Python commands.
- Prefer typed request/response models for new API surfaces.
- Keep authorization checks close to the route and reusable helper.
- Add regression tests for 401/403/404 cases, not only success paths.
- For runner/tool changes, add tests for blocked paths, hidden files, non-member projects, and cancelled/failed runs.
