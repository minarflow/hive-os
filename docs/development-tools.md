# Development tools guide

This document is the source of truth for future Hermes/Claude Code sessions that develop Hive OS.

## Product context

Hive OS is a Hermes-first Team Mode PWA. It runs on a Linux server/workstation and provides app-level multi-user accounts, private/shared projects, per-user Hermes profiles, async runs, event streaming, and PWA access over localhost/Tailscale.

Current intentional boundary:

```text
OS/server admin boundary: physical/SSH/AnyDesk access to the machine
Hive OS app boundary: app users, projects, sessions, profiles, and API authorization
Runner boundary: Hermes subprocess gets selected HERMES_HOME and project cwd
```

Hive OS does **not** currently provide OS-level isolation between Iqbal/George/William. Treat users as a trusted internal team unless secure mode is explicitly implemented.

## Useful commands

From repo root:

```bash
bash scripts/dev
bash scripts/build
bash scripts/hive-os init-config
bash scripts/hive-os doctor
bash scripts/hive-os serve
```

Verification:

```bash
cd apps/api && .venv/bin/python -m pytest -q tests
npm --prefix apps/web run build
```

Packaged local serve:

```bash
bash scripts/hive-os init-config
bash scripts/hive-os build
bash scripts/hive-os serve
```

## Runtime paths

User-local install:

```text
~/.config/hive-os/hive-os.env
~/.local/share/hive-os/hive-os.db
~/.local/share/hive-os/workspace
~/.local/share/hive-os/hermes-profiles/<username>/<profile>
```

System install:

```text
/opt/hive-os
/etc/hive-os/hive-os.env
/var/lib/hive-os/hive-os.db
/var/lib/hive-os/workspace
/var/lib/hive-os/hermes-profiles/<username>/<profile>
```

## Code ownership

Core files:

```text
apps/api/hive_os_api/main.py       API, auth, runs/events, static PWA serving
apps/api/hive_os_api/db.py         SQLite schema/migrations
apps/api/hive_os_api/auth.py       password/token helpers
apps/api/hive_os_api/settings.py   config/path helpers
apps/web/src/App.tsx               app state and screen routing
apps/web/src/screens/*             UI screens
apps/web/src/api/*                 typed API calls
scripts/*                          install/dev/build wrappers
```

## Rules for coding agents

When a future agent edits this repo:

1. Read this file and `docs/security-boundaries.md` first for security-sensitive work.
2. Do not treat app-level private projects as OS-level isolation.
3. Do not expose arbitrary filesystem browsing to app users.
4. Do not let client-supplied paths decide source/runtime/project access.
5. Keep Hermes/Codex/Claude runner adapters behind Hive OS policy checks.
6. Run API tests and web build after changes.
7. Never print or commit secrets, tokens, `.env`, DB files, or Hermes profile contents.

## Adding new features

Every new feature should answer:

- Which Hive OS user can see it?
- Which project/profile/session does it belong to?
- Does it read source code, project files, runtime files, or secrets?
- Can a prompt injection influence it?
- Is the action audited?
- Is it available to normal users, project owners, or environment admins only?
