# Hive OS Quickstart

## 1. Prerequisite checks

Confirm all three tools are available before you start:

```bash
uv --version
npm --version
hermes --version
```

You also need an authenticated Hermes install. Check for credentials:

```bash
ls ~/.hermes/auth.json ~/.hermes/config.yaml 2>/dev/null && echo "Hermes credentials found"
```

If Hermes is missing or not authenticated, install and authenticate it first. Hive OS will install without it but agents won't run until Hermes is set up.

## 2. Clone and install

```bash
git clone https://github.com/minarflow/hive-os
cd hive-os
bash scripts/install-user
```

The install script:
- Builds the Python backend (via `uv sync`) and the React PWA (`npm install && npm run build`).
- Writes a config file at `~/.config/hive-os/hive-os.env`.
- Installs and enables a systemd **user** service (`hive-os.service`) that starts automatically on login/boot and restarts on crash.
- Installs a daily backup timer (`hive-os-backup.timer`) that runs at 03:00.

## 3. First run — bootstrap the admin account

Open `http://127.0.0.1:8765` in your browser.

On first launch Hive OS prompts you for:
- Admin username
- Admin password
- First Hermes profile name

After that, you can invite teammates from **Team Users** in the admin panel.

## 4. Managing the service

```bash
# Check status and recent logs
systemctl --user status hive-os

# Tail live logs
journalctl --user -u hive-os -f

# Restart after a config change
systemctl --user restart hive-os

# Stop the service
systemctl --user stop hive-os

# Update to the latest version (pull + rebuild + restart; runs DB migrations)
./scripts/hive-os update
```

## 5. Where data lives

All runtime data lives outside the repository. Default paths:

| What | Default path |
|---|---|
| Database | `~/.local/share/hive-os/hive-os.db` |
| Workspace / project files | `~/.local/share/hive-os/` |
| Hermes profiles | `~/.local/share/hive-os/hermes-profiles/` |
| Config file | `~/.config/hive-os/hive-os.env` |
| Daily backups | `~/.local/share/hive-os/backups/` |

Override any path by editing `~/.config/hive-os/hive-os.env` and restarting the service.

Key variables:

| Variable | Default | Effect |
|---|---|---|
| `HIVEOS_PORT` | `8765` | Port the API/PWA listens on |
| `HIVEOS_HOST` | `127.0.0.1` | Bind address |
| `HIVEOS_DB_PATH` | `~/.local/share/hive-os/hive-os.db` | SQLite database file |
| `HIVEOS_WORKSPACE_ROOT` | `~/.local/share/hive-os` | Root for project files |
| `HIVEOS_SOURCE_HERMES_HOME` | _(unset)_ | Hermes home to copy credentials from |
| `HIVEOS_HERMES_BIN` | _(unset, uses PATH)_ | Explicit path to the `hermes` binary |

## 6. Phone, other devices & inviting teammates (Tailscale)

Hive listens only on `127.0.0.1:8765`, so to reach it from your phone or to let
**teammates open invite links**, expose it to your tailnet with Tailscale Serve.
Invite links use this machine's Tailscale HTTPS URL, so they only work once Serve
is running.

```bash
# one-time: let your user run Serve without sudo (enable MagicDNS + HTTPS
# Certificates in the Tailscale admin console first)
sudo tailscale set --operator=$(whoami)

# expose Hive to the tailnet (persists across reboots)
tailscale serve --bg 8765
tailscale serve status
```

Open your Tailscale HTTPS MagicDNS URL (`https://<machine>.<tailnet>.ts.net`) on
any device and install the PWA from the browser menu. Teammates install Tailscale,
join the same tailnet, then open the invite link. See
[docs/installation.md](docs/installation.md#remote-access--team-sharing-tailscale)
for full detail and troubleshooting.

## 7. Backups

The database is a single SQLite file. The daily timer backs it up automatically to `~/.local/share/hive-os/backups/`. To run a manual backup:

```bash
bash scripts/backup
```

## Troubleshooting

- **Web UI not loading**: run `bash scripts/build` to rebuild the PWA dist, then restart the service.
- **Agents not running / "Hermes not found"**: install the Hermes CLI, authenticate with `hermes -z`, confirm it is on `PATH`, then `systemctl --user restart hive-os`.
- **PWA cannot install on phone**: the browser requires HTTPS. Use Tailscale Serve (step 6 above).
- **Want a fresh install**: stop the service, delete `~/.local/share/hive-os/hive-os.db`, and restart.
