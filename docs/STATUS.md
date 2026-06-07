# Hive OS — status & handoff

Snapshot for continuing in a fresh session. (Updated 2026-06-08.)

## How to run

- **Dev** (HMR): `bash scripts/dev` → API `127.0.0.1:8765`, web `127.0.0.1:5177`, DB under `apps/api/.dev/`.
- **Production (always-on)**: `bash scripts/install-user` → systemd user service `hive-os` serving `127.0.0.1:8765` (API + built PWA), daily backup timer. Manage: `systemctl --user {status,restart,stop} hive-os`. After changing web code: `npm --prefix apps/web run build && systemctl --user restart hive-os`. After API code: just `systemctl --user restart hive-os`.
- **Data**: prod DB `~/.local/share/hive-os/hive-os.db`; agent profile homes `~/.local/share/hive-os/hermes-profiles/<user>/<profile>/`.
- **Tests**: `cd apps/api && uv run pytest -q` (77 passing). Web: `npx tsc --noEmit`.
- **Verifying UI**: headless Chrome via CDP + a DB-minted `auth_sessions` token (no login needed) — see prior session transcripts for the pattern.

## Built & verified

- Chat (ACP/Hermes): streaming, session continuity, tool cards, slash commands.
- Tasks: kanban + steerable per-task agent thread; auto status (doing→review), human Done; live refresh; verified e2e (agent writes+runs python, reports output).
- Reliability: heartbeat/reaper, per-session serialization, graceful shutdown, output salvage, orphaned-run cleanup; run timeout 900s + cancel-on-timeout.
- Files workspace ("Files" tab): whole-project tree, edit (CodeMirror), live **HTML/MD preview**, resizable tree, mobile master-detail.
- Run & Preview app: managed dev server (`AppManager`) + authed reverse proxy `/api/appview/{token}/{slug}/{path}`; folder field; verified FE+BE on one port renders + API works through proxy.
- Attach files to chat (upload → `uploads/`) + render images inline / files as download chips (preview route `/api/preview/{token}/{slug}/{path}`).
- MCP/skill from chat: agent runs `hermes mcp add` / `hermes skills install`; **auto-reload** (config_sig recycle in `acp.py`) makes new tools usable next message. Verified with `mcp-server-time`.
- Admin: user management (role/delete), project delete, audit log (in Settings).
- Shell/UX: top-bar (collapse sidebar, files toggle, avatar menu), unified dropdowns, unread/activity dots, desktop notifications, global search, themes/fonts, invite links (Tailscale MagicDNS), mobile fixes (profile in drawer, no overflow-x).

## Parked / next steps

- **Admin-global MCP/skill**: users already scoped to their own profile (enforced by design). Global (all profiles) needs an admin-only Hive action that applies to every profile home + seeds new profiles. Not built. (See memory `hive-os-mcp-skill-governance`.)
- **Multi-app per project** (e.g. frontend + backend at once): AppManager is one process per project today.
- **Multi-port preview** (FE :5173 + BE :8000 separate): proxy is single-port; needs the dev server to proxy `/api` to one port, or multi-port support.
- **HMR/WebSocket in preview**: proxy is HTTP-only (use Reload).
- **Tailscale "Share" button** (external URL for a running app): skipped — `tailscale serve` needs host root/operator (`sudo tailscale set --operator=$USER`), so it's host-admin only; in-app preview covers per-user testing.
- **Connectors/Skills admin UI**: optional — manage MCP/skills from the app instead of CLI.

## Caveats (by design)

- App-level ACL only; agents run with the server user's privileges (no sandbox). Fine for a trusted team on a private network; not for untrusted users. See `docs/security-boundaries.md`.
- No git remote yet — local only.
