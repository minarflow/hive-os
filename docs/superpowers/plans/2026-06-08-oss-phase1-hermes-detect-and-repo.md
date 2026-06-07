# OSS Phase 1 — Hermes auto-detect + repo OSS-readiness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hive OS usable by other self-hosters on Linux: detect an existing Hermes install (reuse it, never reinstall/ship credentials), surface its status in the app, and clean the repo for a public `minarflow/hive-os` push.

**Architecture:** No runtime architecture change. Add one pure detection helper (`hermes_status`) used by the API (`/api/runners/detect`) and the installer; surface status in the web UI; rewrite public-facing docs; scrub non-public files; push.

**Tech Stack:** Python 3 / FastAPI / pytest (backend), React + TS / Vite (web), bash installer, `gh` CLI for the GitHub push.

Implements Phase 1 + section 5 of `docs/superpowers/specs/2026-06-08-oss-multiplatform-packaging-design.md`. Decisions: Hermes stays private (bring-your-own); repo goes public under `minarflow/hive-os`.

---

## File structure

- `apps/api/hive_os_api/runners.py` — add `hermes_status()` (pure, testable) + `Path` import.
- `apps/api/tests/test_runners.py` — add `hermes_status` unit tests.
- `apps/api/hive_os_api/main.py` — include hermes status in `/api/runners/detect`.
- `apps/api/scripts/serve.py` — pass `HIVEOS_SOURCE_HERMES_HOME` / `HIVEOS_HERMES_BIN` into config.
- `apps/api/hive_os_api/settings.py` — normalize `hermes_bin` default (None).
- `apps/web/src/components/shell/HermesBanner.tsx` — new: "Hermes ready / not found" banner.
- `apps/web/src/App.tsx` — mount the banner.
- `README.md`, `QUICKSTART.md`, `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE.md`, `.github/pull_request_template.md` — public docs.
- `.gitignore` — ignore non-public files.

---

## Task 1: `hermes_status()` detection helper

**Files:**
- Modify: `apps/api/hive_os_api/runners.py`
- Test: `apps/api/tests/test_runners.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_runners.py` (create if missing — see imports):

```python
from pathlib import Path
from hive_os_api.runners import hermes_status


def _make_hermes_bin(tmp_path: Path) -> str:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "hermes"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    return str(bindir)


def test_hermes_status_ready_when_bin_and_home_present(tmp_path):
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "auth.json").write_text("{}")
    bindir = _make_hermes_bin(tmp_path)
    st = hermes_status(source_home=str(home), path_env=bindir)
    assert st["ready"] is True
    assert st["binary"].endswith("/hermes")
    assert st["home"] == str(home)
    assert st["guidance"] == ""


def test_hermes_status_missing_binary(tmp_path):
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "config.yaml").write_text("x: 1")
    st = hermes_status(source_home=str(home), path_env=str(tmp_path / "empty"))
    assert st["ready"] is False
    assert st["binary"] is None
    assert "PATH" in st["guidance"] or "install" in st["guidance"].lower()


def test_hermes_status_missing_home(tmp_path):
    bindir = _make_hermes_bin(tmp_path)
    st = hermes_status(source_home=str(tmp_path / "nope"), path_env=bindir)
    assert st["ready"] is False
    assert st["home"] is None
    assert "hermes -z" in st["guidance"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_runners.py -q`
Expected: FAIL — `ImportError: cannot import name 'hermes_status'`.

- [ ] **Step 3: Implement `hermes_status`**

In `apps/api/hive_os_api/runners.py`, add `from pathlib import Path` to the imports, then append:

```python
def _hermes_home_usable(home: str) -> bool:
    p = Path(home)
    return p.is_dir() and ((p / "auth.json").exists() or (p / "config.yaml").exists())


def hermes_status(source_home: str | None = None, path_env: str | None = None) -> dict:
    """Detect a usable Hermes runner without installing anything.

    Bring-your-own: reuse an existing `hermes` binary on PATH plus a Hermes home
    that has credentials/config. Returns ready + actionable guidance when not.
    """
    resolved = augmented_path(path_env)
    binary = resolve_binary("hermes", resolved)
    home = source_home or os.path.expanduser("~/.hermes")
    home_ok = _hermes_home_usable(home)
    ready = bool(binary) and home_ok
    if ready:
        guidance = ""
    elif not binary and not home_ok:
        guidance = ("Hermes not found. Install the Hermes agent CLI, run `hermes -z` "
                    "to authenticate, then restart Hive. See docs/installation.md.")
    elif not binary:
        guidance = ("Hermes credentials found but the `hermes` binary is not on PATH. "
                    "Install/expose the Hermes CLI, then restart Hive.")
    else:
        guidance = (f"`hermes` is installed but no usable Hermes home at {home}. "
                    "Run `hermes -z` to authenticate, or set HIVEOS_SOURCE_HERMES_HOME.")
    return {"ready": ready, "binary": binary, "home": home if home_ok else None, "guidance": guidance}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_runners.py -q`
Expected: PASS (3 passed, plus any pre-existing).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/runners.py apps/api/tests/test_runners.py
git commit -m "feat(runners): hermes_status detection helper (bring-your-own)"
```

---

## Task 2: config plumbing for source home + binary override

**Files:**
- Modify: `apps/api/hive_os_api/settings.py` (normalize `hermes_bin`)
- Modify: `apps/api/scripts/serve.py` (read env)

- [ ] **Step 1: Add `hermes_bin` default in settings**

In `apps/api/hive_os_api/settings.py`, add to `DEFAULT_CONFIG` (after `source_hermes_home`):

```python
    "hermes_bin": None,
```

(No normalization needed; it is an optional explicit path. `source_hermes_home` is already normalized.)

- [ ] **Step 2: Wire env in serve.py**

In `apps/api/scripts/serve.py`, inside the `create_app({...})` dict add:

```python
        "source_hermes_home": os.environ.get("HIVEOS_SOURCE_HERMES_HOME") or None,
        "hermes_bin": os.environ.get("HIVEOS_HERMES_BIN") or None,
```

- [ ] **Step 3: Verify it imports/boots**

Run: `cd apps/api && uv run python -c "from hive_os_api.settings import normalize_config; print(normalize_config().get('hermes_bin'), 'ok')"`
Expected: `None ok`

- [ ] **Step 4: Commit**

```bash
git add apps/api/hive_os_api/settings.py apps/api/scripts/serve.py
git commit -m "feat(config): HIVEOS_SOURCE_HERMES_HOME / HIVEOS_HERMES_BIN env"
```

---

## Task 3: surface Hermes status in `/api/runners/detect`

**Files:**
- Modify: `apps/api/hive_os_api/main.py:1088-1096`
- Test: `apps/api/tests/test_runners.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/api/tests/test_runners.py`:

```python
from fastapi.testclient import TestClient
from hive_os_api.main import create_app


def test_detect_endpoint_includes_hermes_status(tmp_path):
    app = create_app({
        "database_path": str(tmp_path / "h.db"),
        "workspace_root": str(tmp_path / "rt"),
        "seed_users": [{"username": "kuya", "os_user": "kuya", "role": "environment_admin"}],
    })
    api = TestClient(app)
    tok = api.post("/auth/login", json={"username": "kuya", "password": "password123"}).json()["token"]
    body = api.get("/api/runners/detect", headers={"Authorization": f"Bearer {tok}"}).json()
    assert "hermes" in body
    assert set(["ready", "binary", "home", "guidance"]).issubset(body["hermes"].keys())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_runners.py::test_detect_endpoint_includes_hermes_status -q`
Expected: FAIL — `KeyError`/assert on `"hermes" in body`.

- [ ] **Step 3: Implement**

In `apps/api/hive_os_api/main.py`, add the import near the other `from .runners import ...` (or add one):

```python
from .runners import detect_runners, hermes_status
```

Then change the `runners_detect` body to return the status, using configured source home + binary:

```python
        return {
            "user": user["username"],
            "runners": runners,
            "hermes": hermes_status(source_home=cfg.get("source_hermes_home"), path_env=None),
        }
```

(If `cfg` isn't in scope at that point, it is the `create_app` `cfg`; the endpoint is defined inside `create_app`, so `cfg` is captured.)

- [ ] **Step 4: Run tests**

Run: `cd apps/api && uv run pytest tests/test_runners.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add apps/api/hive_os_api/main.py apps/api/tests/test_runners.py
git commit -m "feat(api): expose hermes readiness in /api/runners/detect"
```

---

## Task 4: friendly Hermes check in the installer

**Files:**
- Modify: `scripts/install-user`

- [ ] **Step 1: Add a non-fatal Hermes check**

In `scripts/install-user`, after the `==> Writing config` block and before installing systemd units, insert:

```bash
echo "==> Checking for Hermes runner"
if command -v hermes >/dev/null 2>&1 && { [ -f "${HERMES_HOME:-$HOME/.hermes}/auth.json" ] || [ -f "${HERMES_HOME:-$HOME/.hermes}/config.yaml" ]; }; then
  echo "    Hermes detected — Hive will use your existing install."
else
  echo "    WARNING: Hermes not detected." >&2
  echo "    Hive installs fine, but chats won't run until Hermes is set up:" >&2
  echo "      1) install the Hermes agent CLI (must be on PATH)" >&2
  echo "      2) run 'hermes -z' to authenticate" >&2
  echo "      3) restart: systemctl --user restart hive-os" >&2
fi
```

- [ ] **Step 2: Lint the script**

Run: `bash -n scripts/install-user`
Expected: no output (syntax OK).

- [ ] **Step 3: Commit**

```bash
git add scripts/install-user
git commit -m "feat(install): warn (non-fatal) when Hermes runner is absent"
```

---

## Task 5: Hermes status banner in the web UI

**Files:**
- Create: `apps/web/src/components/shell/HermesBanner.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Create the banner component**

`apps/web/src/components/shell/HermesBanner.tsx`:

```tsx
import React from 'react'

type HermesStatus = { ready: boolean; binary: string | null; home: string | null; guidance: string }

export function HermesBanner({ token }: { token: string }) {
  const [status, setStatus] = React.useState<HermesStatus | null>(null)
  React.useEffect(() => {
    if (!token) return
    fetch('/api/runners/detect', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json()).then(b => setStatus(b.hermes ?? null)).catch(() => setStatus(null))
  }, [token])
  if (!status || status.ready) return null
  return <div className="hermes-banner" role="status">⚠ Hermes runner not ready — {status.guidance}</div>
}
```

- [ ] **Step 2: Mount it in App.tsx**

In `apps/web/src/App.tsx`, import it at the top:

```tsx
import { HermesBanner } from './components/shell/HermesBanner'
```

Then render it just inside the authenticated app shell (right before the `view === 'chat'` block — i.e. as the first child of the main content area):

```tsx
      <HermesBanner token={token} />
```

- [ ] **Step 3: Add minimal styling**

Append to `apps/web/src/styles.css`:

```css
.hermes-banner { margin: 10px 16px; padding: 9px 13px; border: 1px solid color-mix(in srgb, #c0392b 40%, var(--ui-stroke-secondary)); background: color-mix(in srgb, #c0392b 10%, var(--ui-surface)); color: var(--ui-text-primary); border-radius: 10px; font-size: .85rem; }
```

- [ ] **Step 4: Typecheck + build**

Run: `cd apps/web && npx tsc --noEmit && npm run build`
Expected: tsc clean, build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/shell/HermesBanner.tsx apps/web/src/App.tsx apps/web/src/styles.css
git commit -m "feat(web): show a banner when the Hermes runner isn't ready"
```

---

## Task 6: public-facing docs

**Files:**
- Modify: `README.md`
- Create: `QUICKSTART.md`, `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE.md`, `.github/pull_request_template.md`

- [ ] **Step 1: Rewrite README.md**

Replace `README.md` with content covering, in order: one-line description; a screenshot placeholder line (`![Hive OS](docs/screenshot.png)`); "What it is" (multi-user, Hermes-first agent workspace, PWA); Requirements (Linux, `uv`, `npm`, a Hermes install + credentials — link `docs/installation.md`); Quickstart (3 commands: clone, `bash scripts/install-user`, open `http://127.0.0.1:8765`); "Bring your own Hermes" note (Hive detects an existing Hermes; it ships no credentials); Security/trust model (link `docs/security-boundaries.md`: app-level ACL only, agents run as the server user); License (MIT). Keep under ~120 lines.

- [ ] **Step 2: Create QUICKSTART.md**

Concrete steps: prerequisites check (`uv --version`, `npm --version`, `hermes --version`), `git clone https://github.com/minarflow/hive-os`, `cd hive-os`, `bash scripts/install-user`, first-run bootstrap (open the URL, create the admin user), and how to restart (`systemctl --user restart hive-os`).

- [ ] **Step 3: Create CONTRIBUTING.md**

Dev setup (`bash scripts/dev`), test commands (`cd apps/api && uv run pytest -q`; `cd apps/web && npx tsc --noEmit`), the runner-agnostic / Hermes-first rule (link `AGENTS.md`), commit style, "no secrets/PII in commits."

- [ ] **Step 4: Create GitHub templates**

`.github/ISSUE_TEMPLATE.md` (Environment / Steps / Expected / Actual / Logs) and `.github/pull_request_template.md` (What / Why / Testing / Screenshots).

- [ ] **Step 5: Commit**

```bash
git add README.md QUICKSTART.md CONTRIBUTING.md .github/
git commit -m "docs: public README, quickstart, contributing, templates"
```

---

## Task 7: final scrub of non-public files

**Files:**
- Modify: `.gitignore`
- Remove from tracking: `nohup.out`, `.impeccable.md`, `.claude/`

- [ ] **Step 1: Audit what is tracked + scan for PII**

Run:
```bash
git ls-files | grep -E '^\.claude/|^\.impeccable\.md$|nohup\.out' || echo "none tracked"
git grep -nIE '/home/kuya|minarflowofficial|georgev\.vie|\.ts\.net' -- . ':!docs/superpowers/*' || echo "no PII hits"
```
Expected: review each hit; runtime/personal references in non-doc source must be removed or parameterized.

- [ ] **Step 2: Ignore + untrack non-public files**

```bash
printf '\n# Not for public repo\n.impeccable.md\n.claude/\n' >> .gitignore
git rm -r --cached --ignore-unmatch .claude .impeccable.md nohup.out
```

- [ ] **Step 3: Fix any PII hits from Step 1**

For each non-doc hit, replace hardcoded personal paths/handles with config/env or generic placeholders. (Docs under `docs/superpowers/` are internal specs/plans and may reference the author.)

- [ ] **Step 4: Run the full backend suite to confirm nothing broke**

Run: `cd apps/api && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: scrub non-public files; ignore .claude/.impeccable"
```

---

## Task 8: verify the Linux installer end-to-end (clean state)

**Files:** none (verification).

- [ ] **Step 1: Install into throwaway dirs**

Run:
```bash
HIVEOS_WORKSPACE_ROOT=/tmp/hive-verify/ws \
HIVEOS_CONFIG=/tmp/hive-verify/cfg/hive-os.env \
bash scripts/install-user
```
Expected: builds, writes units, prints the Hermes-detected line, service starts.

- [ ] **Step 2: Confirm it serves**

Run: `systemctl --user is-active hive-os && curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/`
Expected: `active` then `200`.

- [ ] **Step 3: Confirm detection both ways**

Run: `curl -s http://127.0.0.1:8765/api/runners/detect` is auth-gated; instead check the helper directly:
`cd apps/api && uv run python -c "from hive_os_api.runners import hermes_status; print(hermes_status())"`
Expected: `ready` True on this host. Then temporarily set `PATH=/usr/bin` and a bogus home to confirm guidance text appears:
`uv run python -c "from hive_os_api.runners import hermes_status; print(hermes_status(source_home='/tmp/nope', path_env='/usr/bin'))"`

- [ ] **Step 4: Capture evidence + clean up**

Note the outputs in the execution log. Then: `rm -rf /tmp/hive-verify` (leave the real service untouched — it uses the default dirs).

---

## Task 9: create + push public GitHub repo

**Files:** none (ops). Requires `gh` authenticated as minarflow.

- [ ] **Step 1: Confirm gh auth**

Run: `gh auth status`
Expected: logged in. If not, STOP and ask the user to run `! gh auth login` (interactive).

- [ ] **Step 2: Confirm working tree is clean and tests pass**

Run: `git status --short` (empty) and `cd apps/api && uv run pytest -q` (all pass).

- [ ] **Step 3: Create the public repo and push**

```bash
gh repo create minarflow/hive-os --public --source=. --remote=origin --description "Hermes-first multi-user agent workspace (self-hosted)" --push
```
Expected: repo created, `main` pushed.

- [ ] **Step 4: Verify remotely**

Run: `gh repo view minarflow/hive-os --web` (or `gh repo view minarflow/hive-os`)
Expected: README renders; no secret/DB files present. Spot-check: `gh api repos/minarflow/hive-os/contents | grep -i '\.env$\|\.db$\|\.claude'` returns nothing.

---

## Self-review notes

- Spec §5 (detection) → Tasks 1–4. §6 (OSS docs/scrub/verify/push) → Tasks 6–9. UI surfacing → Task 5.
- §12 decisions honored: BYO (no Hermes shipped/installed — only detected); public `minarflow/hive-os` (Task 9).
- Phases 2 (Docker) and 3 (macOS/Windows) are intentionally out of this plan and get their own plans after Phase 1 verifies.
