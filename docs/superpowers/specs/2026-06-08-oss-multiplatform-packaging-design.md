# Hive OS — OSS-ready multi-platform packaging (design)

Date: 2026-06-08 · Status: draft for review

## 1. Goal

Make Hive OS distributable as open source so other people can self-host it.
Ship it as packages for **Linux, macOS, Windows, and Docker**, using the
**server model** (run Hive in the background, use it from a browser / phone via
Tailscale). Runner is **Hermes only** for now; the architecture stays
runner-agnostic so other agents can be added later.

## 2. Scope / non-goals

In scope:
- Auto-detect an existing Hermes install and reuse it (no reinstall when present).
- A Docker image + compose that runs on Linux/Windows/macOS (via Docker Desktop).
- Native background-service installers: Linux (systemd user — exists), macOS
  (launchd — new). Windows: recommend Docker Desktop (no native Python service).
- OSS repo hygiene: README + screenshots, QUICKSTART, CONTRIBUTING, final
  secret/PII scrub, public GitHub push.

Non-goals (explicitly deferred):
- Desktop app (Tauri/Electron native window) — server model only.
- Multi-user OS-user + POSIX ACL deployment — parked (`manage_os_acl` off).
- Bundling Hermes credentials — never; users always supply their own.
- Adding non-Hermes runners — architecture stays open, but not built here.

## 3. Constraints & key facts (ground truth)

- **Hermes is a private package** (has `pyproject.toml` but is not on PyPI). It
  cannot be assumed `pip install`-able by the public.
- **`~/.hermes` is highly personal** (auth.json tokens, config, sessions,
  memories). It MUST NOT ship in any artifact.
- Current architecture: FastAPI backend + SQLite + built React PWA served by the
  backend on `127.0.0.1:8765`. The backend spawns `hermes acp --accept-hooks`
  (JSON-RPC over stdio) with `HERMES_HOME` set per profile; profiles are seeded
  from a **source Hermes home** (default `~/.hermes`) so each can authenticate.
- Hive therefore needs two things from the host: the **`hermes` binary on PATH**
  and a **source Hermes home** to seed from. Credentials come from that home,
  supplied by the user.
- Existing install (`scripts/install-user`) builds (`uv sync`, `npm run build`)
  and installs a systemd **user** service + daily backup timer. Requires `uv`
  and `npm`.
- Repo is already ~90% OSS-ready: MIT LICENSE, `.gitignore` scrubs secrets/DB,
  no tracked secrets, extensive `docs/`. Not yet pushed (no git remote).

## 4. Architecture (unchanged at runtime)

```
host machine
  Hive API (FastAPI)  ──serves──>  built PWA  ──> browser / phone (Tailscale)
       │ spawns
       ▼
  hermes acp (runner)  ── uses ──> Hermes home (user credentials)
       │
  workspace data: <data-dir>/hive-os.db + projects/  (persisted)
```

The only new runtime behaviour is **runner provisioning** (section 5). Packaging
(sections 6–8) wraps this same server in different delivery mechanisms.

## 5. Runner provisioning — Hermes auto-detect

A single bootstrap routine, run by every install path (native installers and the
Docker entrypoint), with this precedence:

1. **Explicit override** — if `HIVEOS_HERMES_BIN` / `HIVEOS_SOURCE_HERMES_HOME`
   are set, use them.
2. **Detect existing** — if `hermes` is on PATH **and** a usable Hermes home
   exists (`~/.hermes` or `$HERMES_HOME` with an `auth.json`/`config.yaml`),
   configure Hive to use them. → "already have Hermes, nothing to install."
3. **Absent** — do not fail silently. Print clear, actionable guidance: how to
   install Hermes and where to put credentials, then exit non-zero on installers
   / show a banner in the app's runner screen. Optional future hook:
   `HIVEOS_HERMES_AUTOINSTALL` to fetch Hermes when a distributable source is
   configured (depends on section 12 decision).

Surface this state via the existing `/api/runners/detect` so the UI can show
"Hermes: ready / not found (how to fix)".

## 6. Phase 1 — OSS-ready + Hermes detect + Linux verify

- Implement the section-5 detection routine; wire `install-user` and `serve.py`
  to it; friendly error when Hermes is missing.
- Repo hygiene for public release:
  - README rewrite: what it is, screenshots, 3-step quickstart, requirements
    (Linux + Hermes + uv + npm), security note, link to docs.
  - `QUICKSTART.md`, `CONTRIBUTING.md`, issue/PR templates, top-level `.env.example`
    confirmed complete.
  - Final scrub pass: grep for personal paths / tokens / private project names in
    tracked files; remove `nohup.out`, `.impeccable.md`, `.claude/` from the
    public set (gitignore or strip).
- Verify the Linux installer end-to-end from a clean state (fresh
  workspace/config dir, fresh DB) and capture evidence.
- Create the public GitHub repo (account + visibility per section 12) and push.

## 7. Phase 2 — Docker (cross-platform)

- Multi-stage `Dockerfile`: node stage builds the PWA; python stage runs the API
  with `uv`. Non-root container user; data under a volume.
- `docker-compose.yml`:
  - volume `hive-data` → workspace (DB + projects) persists across restarts.
  - mount the user's Hermes home read-write at a known path; entrypoint runs the
    section-5 detection against it.
  - env file for config (`HIVEOS_*`), port mapping `8765:8765`.
- **Hermes-in-Docker** (the hard part, see section 12): default is **bring your
  own** — user mounts their Hermes home and the image expects `hermes`
  available. Build-arg `HERMES_SRC` (git URL / path) optionally vendors Hermes
  at build time if/when it becomes distributable.
- Document Windows/macOS usage via Docker Desktop.

## 8. Phase 3 — native macOS & Windows

- macOS: `scripts/install-macos` writing a **launchd** LaunchAgent
  (`~/Library/LaunchAgents/…plist`) mirroring the systemd unit (auto-start,
  keepalive) + backup. Reuse the section-5 detection.
- Windows: documented path = **Docker Desktop** (recommended). Optionally a
  PowerShell script that runs the server via a Scheduled Task — marked
  best-effort, not a supported service.

## 9. Configuration matrix (env, all optional)

| Var | Meaning | Default |
|-----|---------|---------|
| `HIVEOS_WORKSPACE_ROOT` | data dir (DB + projects) | `~/.local/share/hive-os` |
| `HIVEOS_HERMES_BIN` | explicit hermes binary | autodetect on PATH |
| `HIVEOS_SOURCE_HERMES_HOME` | seed source for profiles | `~/.hermes` |
| `HIVEOS_HERMES_AUTOINSTALL` | attempt install if absent | off |
| `HIVEOS_MANAGE_OS_ACL` | multi-user ACL ops | off |
| `HIVEOS_PORT` / `HIVEOS_HOST` | bind | `8765` / `127.0.0.1` |

## 10. Security

- No credentials/PII in any artifact; `.dockerignore` mirrors `.gitignore`.
- Container runs as non-root; bind defaults to localhost (Tailscale/reverse
  proxy for remote, as today).
- Carry forward existing `docs/security-boundaries.md`: app-level ACL only,
  agents run with the server user's privileges — state this prominently in the
  README so self-hosters understand the trust model.

## 11. Verification plan

- Phase 1: run `install-user` on a clean config/data dir; confirm service up,
  `/health` 200, Hermes detected, a chat run completes. Detection: temporarily
  hide `hermes` → confirm the friendly "not found" guidance.
- Phase 2: `docker compose up` on this Linux host; `/health` 200 through the
  container; a chat run completes using a mounted Hermes home; data persists
  across `down`/`up`.
- Phase 3: macOS launchd load/start verified on a Mac if available, else mark
  BLOCKED with the plist for manual test; Windows = verify the Docker path.
- Each phase: capture command output / screenshots as evidence before claiming
  done.

## 12. Decisions (resolved 2026-06-08)

- **Hermes stays private → bring-your-own.** Artifacts ship Hive only. Hosts who
  already run Hermes get auto-detect + reuse; hosts without get clear install
  guidance. The `HERMES_SRC` build-arg vendoring hook is implemented but left
  **off**, so bundling can be flipped on later without rework.
- **GitHub: `minarflow/hive-os`, public.** Push as the minarflow identity (matches
  this repo's commit author) and make it public once Phase 1 is verified.

## 13. Deliverables

- [ ] Hermes auto-detect bootstrap + `/api/runners/detect` surfacing + UI banner
- [ ] README + screenshots + QUICKSTART + CONTRIBUTING + templates + final scrub
- [ ] Verified Linux installer + public GitHub repo pushed
- [ ] Dockerfile + docker-compose + .dockerignore + docs (verified on Linux)
- [ ] macOS launchd installer; Windows Docker-Desktop guide (+ optional PS script)
