# Hive OS installation

Hive OS is Linux-first and runs as a Hermes-first Team Mode PWA. Team Mode uses app-level accounts and per-user/per-profile `HERMES_HOME` directories; it does **not** require OS-level user isolation.

## Requirements

- Linux workstation/server
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Node.js/npm compatible with the web stack
- Hermes CLI installed and logged in for real agent runs
- Optional: Tailscale for phone/PWA access

## Quick dev run

```bash
git clone https://github.com/minarflow/hive-os hive-os
cd hive-os
bash scripts/dev
```

Open:

```text
http://127.0.0.1:5177
```

The dev script uses:

- API: `127.0.0.1:8765`
- Web: `127.0.0.1:5177`
- Runtime data: `apps/api/.dev/`
- Project helper: `/usr/bin/true` so no sudo/ACL is required

## Build and test

```bash
bash scripts/build
```

This runs API dependency sync, API tests, web dependency install, and web build.

## Local Team Mode install

Preview the install actions:

```bash
sudo bash scripts/install-local --dry-run
```

Install to `/opt/hive-os` with runtime data in `/var/lib/hive-os`:

```bash
sudo bash scripts/install-local
```

Then:

```bash
hive-os doctor
hive-os serve
```

Open:

```text
http://127.0.0.1:8765
```

On first launch, Hive OS will ask for:

- admin username
- admin password
- first Hermes profile name/slug

Each user can then create multiple Hermes profiles. Every profile gets its own managed home:

```text
<workspace>/hermes-profiles/<username>/<profile_slug>
```

## User-local install without sudo

You can also use the wrapper directly from a clone:

```bash
bash scripts/hive-os init-config
bash scripts/hive-os build
bash scripts/hive-os doctor
bash scripts/hive-os serve
```

Default user-local data lives under:

```text
~/.local/share/hive-os
~/.config/hive-os/hive-os.env
```

## Remote access & team sharing (Tailscale)

Hive OS listens only on `127.0.0.1:8765`, so out of the box it is reachable
only from the machine it runs on. To open it on your phone or **invite
teammates**, expose it privately to your [tailnet](https://tailscale.com/) with
Tailscale Serve. The invite links Hive generates use this machine's Tailscale
HTTPS URL (e.g. `https://<machine>.<tailnet>.ts.net`), so they only work once
Serve is running.

### One-time setup

1. Install Tailscale on the Hive host and sign in (`tailscale up`).
2. Enable HTTPS for your tailnet (once, in the admin console):
   <https://login.tailscale.com/admin/dns> → turn on **MagicDNS** and
   **HTTPS Certificates**.
3. Allow your user to run Serve without `sudo` every time:

   ```bash
   sudo tailscale set --operator=$(whoami)
   ```

### Expose Hive to the tailnet

```bash
tailscale serve --bg 8765      # maps https://<machine>.<tailnet>.ts.net -> 127.0.0.1:8765
tailscale serve status         # verify the mapping
```

Now open `https://<machine>.<tailnet>.ts.net` from any device on the tailnet and
install Hive OS as a PWA.

### Inviting teammates

1. Make sure Serve is running (above).
2. In Hive, add the member / copy the invite link.
3. The teammate installs Tailscale, joins the **same tailnet**, then opens the
   invite link.

If the invite link shows `ERR_CONNECTION_REFUSED`, Serve isn't running (or HTTPS
isn't enabled for the tailnet) — re-check the one-time setup above.

## systemd example

A template is provided at:

```text
infra/systemd/hive-os.service.example
```

Typical flow:

```bash
sudo useradd --system --home /var/lib/hive-os --shell /usr/sbin/nologin hive-os
sudo cp infra/systemd/hive-os.service.example /etc/systemd/system/hive-os.service
sudo systemctl daemon-reload
sudo systemctl enable --now hive-os
```

Adjust ownership and paths for your machine.

## Configuration

Copy `.env.example` to either:

```text
~/.config/hive-os/hive-os.env
/etc/hive-os/hive-os.env
```

Important variables:

- `HIVEOS_DB_PATH`
- `HIVEOS_WORKSPACE_ROOT`
- `HIVEOS_HERMES_PROFILES_ROOT`
- `HIVEOS_WEB_DIST`
- `HIVEOS_HOST`
- `HIVEOS_PORT`
- `HIVEOS_PROJECTCTL_COMMAND`

By default, Team Mode uses `HIVEOS_PROJECTCTL_COMMAND=/usr/bin/true`, meaning project access is enforced at the app layer and no OS-level ACL mutation is attempted.

## Update

From an installed checkout:

```bash
cd /opt/hive-os
sudo git pull
sudo bash scripts/build
sudo systemctl restart hive-os
```

For user-local installs:

```bash
git pull
bash scripts/build
bash scripts/hive-os serve
```

## Troubleshooting

```bash
hive-os doctor
```

Common issues:

- Web dist missing: run `bash scripts/build`.
- Hermes not found: install/login Hermes and ensure it is on `PATH` for the service.
- PWA cannot install: use HTTPS, e.g. Tailscale Serve.
- First-run setup does not show: delete/reset the configured SQLite DB only if you intentionally want a fresh install.
