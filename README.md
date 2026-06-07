# Hive OS

Self-hosted, multi-user agent workspace — chat, tasks, files, wiki, and run-and-preview, driven by your own Hermes install.

![Hive OS](docs/screenshot.png)

## What it is

Hive OS is a **Hermes-first** team workspace you run as a background service and reach from any browser (or phone via Tailscale). It ships as a FastAPI backend + React PWA.

Features:
- **Chat with agents** — streaming responses, tool-activity cards, slash commands, and session continuity via the Agent Client Protocol (ACP).
- **Tasks (kanban)** — each task has a transparent, steerable agent thread. Agents move tasks to Review; a human marks them Done.
- **Files** — per-project file browser (read/write, mkdir, rename, delete) and an Artifacts view for agent deliverables.
- **Wiki** — per-project and global wiki with tree editing.
- **Accounts & teams** — username/password sign-in, roles (admin/member), and invite links.
- **PWA** — installable on desktop or phone; works great over Tailscale.

## Requirements

- Linux
- [`uv`](https://docs.astral.sh/uv/)
- Node.js / `npm`
- A working **Hermes CLI** install with credentials (`~/.hermes`)

See [docs/installation.md](docs/installation.md) for full details.

## Quickstart

```bash
git clone https://github.com/minarflow/hive-os
cd hive-os
bash scripts/install-user
```

Open `http://127.0.0.1:8765` — the first visit walks you through creating the admin account.

Manage the service:

```bash
systemctl --user status hive-os
systemctl --user restart hive-os
systemctl --user stop hive-os
```

## Bring your own Hermes

Hive OS ships **no credentials**. On startup it looks for an existing `hermes` on your `PATH` and a populated `~/.hermes` directory. If found, it reuses them. If not, the install script prints a warning and the app shows a banner guiding you through setup.

Two environment variables let you override the auto-detected paths:

| Variable | Effect |
|---|---|
| `HIVEOS_SOURCE_HERMES_HOME` | Path to the Hermes home to copy credentials from when creating new profiles |
| `HIVEOS_HERMES_BIN` | Explicit path to the `hermes` binary |

## Security / trust model

Hive OS enforces access at the **application** level (membership + role checks), not the OS level. Agents run with the **same privileges as the server process** — they can read and write files and run tools on the host. This is by design and appropriate for a **trusted team on a private network** (e.g. a Tailnet).

Do **not** expose Hive OS to untrusted users without adding OS-level isolation (e.g. running it in a container). See [docs/security-boundaries.md](docs/security-boundaries.md) for the full boundary description.

## Tailscale / phone access

```bash
tailscale serve --bg https / http://127.0.0.1:8765
```

Open your HTTPS MagicDNS URL on any device and install the PWA.

## Repository layout

```text
apps/api/        FastAPI backend
apps/web/        React/Vite PWA
infra/scripts/   optional ACL/project helper
infra/systemd/   service templates
docs/            architecture, install, security, backup docs
scripts/         build/dev/install/backup wrappers
templates/       project workspace templates
```

## Docs

- [Installation](docs/installation.md)
- [Security boundaries](docs/security-boundaries.md)
- [Architecture](docs/architecture.md)
- [Backup & recovery](docs/backup.md)

## License

[MIT](LICENSE)
