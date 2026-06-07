# Hive OS

Hermes-first **Team Mode** PWA for human + AI agent collaboration.

Hive OS is a local/self-hosted workspace where a team signs in, creates private or
shared projects, and drives [Hermes](https://github.com/) agents through the Agent
Client Protocol (ACP). Each user owns multiple agent **profiles**; every profile
gets its own managed `HERMES_HOME`, so credentials, sessions, and model defaults
stay separated.

## Features

- **Accounts & teams** — username/password first-run onboarding, app-level
  multi-user accounts, roles (admin / member), and **invite links** that
  auto-use your Tailscale MagicDNS URL (single-use, expiring).
- **Projects** — private or shared, with a file browser (read/write, mkdir,
  rename, delete) and an **Artifacts** view for agent deliverables.
- **Chat with agents** — streaming responses, native session continuity (ACP),
  live **tool-activity cards**, reasoning, and slash commands.
- **Tasks** — a kanban board where each task has a transparent, steerable agent
  thread. Agents move a task to **Review** when done; a human marks it **Done**.
- **Wiki** — per-project and global wiki (tree, edit, mkdir, rename, delete).
- **Search** — global search across projects, chats, tasks, and message content.
- **Notifications** — desktop alerts when an agent finishes while your tab is
  backgrounded (opt-in in Settings).
- **Admin** — team user management (role change / removal), project deletion,
  and an **audit log** of logins, invites, runs, and admin actions.
- **Reliability** — runs survive crashes and restarts: heartbeat watchdog,
  per-session serialization, graceful shutdown, and output salvage so a chat
  never hangs forever and streamed output is never lost.
- **PWA** — installable, works great over Tailscale.

## Security model (read before exposing it)

Hive OS enforces access at the **application** level (membership + role checks),
not the OS level. Agents run with the **same privileges as the server process** —
they can read/write files and run tools on the host. That is by design and fine
for a **trusted team on a private network** (e.g. a Tailnet).

Do **not** expose Hive OS to untrusted users as-is. If you need a harder boundary,
run it in a container (an agent's blast radius is then the container, not the host)
or behind OS-level isolation. See [docs/security-boundaries.md](docs/security-boundaries.md).

## Quick start: development

```bash
git clone <repo-url> hive-os
cd hive-os
bash scripts/dev
```

Open `http://127.0.0.1:5177`. The dev script starts the FastAPI backend
(`127.0.0.1:8765`), the Vite PWA dev server (`127.0.0.1:5177`), keeps runtime
data under `apps/api/.dev/`, and uses a no-op project helper so no sudo/ACL is
required.

## Build and test

```bash
bash scripts/build      # sync deps, run API tests, build the PWA
```

## Install (always-on, no sudo)

One command builds the app and runs it as a systemd **user** service that
auto-starts on login/boot, restarts on crash, and backs up the DB daily:

```bash
bash scripts/install-user
```

Then open `http://127.0.0.1:8765` and create your admin account. Manage it with
`systemctl --user {status,restart,stop} hive-os`.

Other options — system-wide with sudo, or manual control:

```bash
sudo bash scripts/install-local      # add --dry-run to preview
# or run it yourself:
bash scripts/hive-os init-config && bash scripts/hive-os build && bash scripts/hive-os serve
```

On first launch Hive OS asks for an admin username/password and a first agent
profile. After that, invite teammates from **Team Users** (the link uses your
Tailnet URL automatically).

> Docker / docker-compose is an optional way to self-host with isolation; it is
> not bundled here. Any standard FastAPI + static-PWA container setup works.

## Using it

- **Chat**: pick a project + agent, type. `/` shows slash commands.
- **Tasks**: create a task, open it, click **▶ Kerjakan task ini** to start the
  agent (or type your own brief). Watch it work; it lands in **Review** when done.
  Steer it any time by sending a message; mark **Done** yourself.
- **Artifacts**: agent deliverables saved to a project's `artifacts/` folder show
  up here with preview + download.
- **Search** (top bar): jump to any chat, task, project, or message.
- **Settings** (avatar menu, top-right): theme, fonts, font size, desktop
  notifications, password, and — for admins — the audit log.

## PWA over Tailscale

```bash
tailscale serve --bg https / http://127.0.0.1:8765
```

Open the HTTPS MagicDNS URL on your phone and install the PWA.

## Backup

The database is a single SQLite file. Take consistent online backups with:

```bash
HIVEOS_DB_PATH=~/.local/share/hive-os/hive-os.db bash scripts/backup
```

Schedule it via cron or a systemd timer — see [docs/backup.md](docs/backup.md).

## Repository layout

```text
apps/api/              FastAPI backend
apps/web/              React/Vite PWA
infra/scripts/         optional ACL/project helper
infra/systemd/         service templates
docs/                  architecture, install, security, backup docs
scripts/               build/dev/install/backup wrappers
templates/             project workspace templates
```

## Docs

- [Status & handoff](docs/STATUS.md) — current state + next steps
- [Installation](docs/installation.md)
- [Backup & recovery](docs/backup.md)
- [Security boundaries](docs/security-boundaries.md)
- [Architecture](docs/architecture.md)
- [Development tools guide](docs/development-tools.md)
- [Prompt-injection hardening](docs/prompt-injection-hardening.md)

## License

[MIT](LICENSE)
