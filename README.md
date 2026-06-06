# Hive OS

Hermes-first Team Mode PWA for human + AI agent collaboration.

Hive OS provides a local/self-hosted workspace where multiple users can sign in, create private or shared projects, and run Hermes through user-owned Hermes profiles. Each Hive OS user can create multiple Hermes/agent profiles; every profile gets its own managed `HERMES_HOME`, so credentials, sessions, and model defaults stay separated at the app level.

## Status

Usable Team Mode foundation:

- username/password first-run onboarding
- app-level multi-user accounts
- per-user multi-profile Hermes setup
- private/shared projects
- async runs and durable events
- SSE/WebSocket event streaming endpoints
- installable PWA basics
- source/bundle install scripts

This phase intentionally does **not** use OS-level per-user isolation. Project access is enforced by Hive OS membership checks. POSIX ACL integration remains available through `infra/scripts/hiveosctl` for a later secure mode.

## Quick start: development

```bash
git clone <repo-url> hive-os
cd hive-os
bash scripts/dev
```

Open:

```text
http://127.0.0.1:5177
```

The dev script starts:

- FastAPI backend: `127.0.0.1:8765`
- Vite PWA dev server: `127.0.0.1:5177`
- DB/runtime data under `apps/api/.dev/`
- no-op project helper (`/usr/bin/true`) so no sudo/ACL is required

## Build and test

```bash
bash scripts/build
```

This syncs API deps, runs API tests, installs web deps, and builds the PWA.

## Install locally

Preview install actions:

```bash
sudo bash scripts/install-local --dry-run
```

Install:

```bash
sudo bash scripts/install-local
hive-os doctor
hive-os serve
```

Open:

```text
http://127.0.0.1:8765
```

On first launch, Hive OS asks for:

- admin username
- admin password
- first Hermes profile name/slug

## User-local install without sudo

```bash
bash scripts/hive-os init-config
bash scripts/hive-os build
bash scripts/hive-os doctor
bash scripts/hive-os serve
```

Default user-local locations:

```text
~/.config/hive-os/hive-os.env
~/.local/share/hive-os/
```

## PWA over Tailscale

After `hive-os serve` is running:

```bash
tailscale serve --bg https / http://127.0.0.1:8765
```

Open the HTTPS MagicDNS URL from your phone and install the PWA.

## Repository layout

```text
apps/api/              FastAPI backend
apps/web/              React/Vite PWA
infra/scripts/         optional ACL/project helper
infra/systemd/         service templates
infra/tailscale/       tailnet/PWA notes
docs/                  architecture and install docs
scripts/               build/dev/install wrappers
templates/             project workspace templates
```

## Docs

- [Installation](docs/installation.md)
- [Development tools guide](docs/development-tools.md)
- [Security boundaries](docs/security-boundaries.md)
- [Locked repo policy](docs/locked-repo-policy.md)
- [Prompt-injection hardening](docs/prompt-injection-hardening.md)
- [Architecture](docs/architecture.md)
- [ACL smoke test](docs/acl-smoke-test.md)

## License

TBD.
