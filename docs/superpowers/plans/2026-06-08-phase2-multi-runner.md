# Phase 2 (Milestone 1) — Claude Code as a runner — Implementation Plan

> Execute task-by-task with fresh subagents + review. Steps use `- [ ]`.

**Goal:** Let a profile pick its agent runner and run it over ACP — adding **Claude Code** alongside Hermes, without breaking Hermes. Codex/Gemini follow the same pattern later.

**Architecture:** Hive stays a control plane that drives agents over ACP. Generalize the hardcoded `hermes acp` spawn into a small per-runner registry (spawn command + home env var). Each profile carries a `runner_id`; the worker spawns the right adapter and points it at the profile's per-runner home.

**Verified by spike:** `@agentclientprotocol/claude-agent-acp` (renamed from `@zed-industries/claude-code-acp`, v0.16.2) launches and answers the ACP `initialize` handshake — same protocol Hive already speaks. Claude Code auth = `claude /login`, isolatable per config dir via `CLAUDE_CONFIG_DIR`. Host has `claude`, `codex`, `npx` (no `gemini`).

---

## Runner model

A runner spec = `{id, spawn_argv, home_env, install_check}`:
- **hermes**: `["hermes","acp","--accept-hooks"]`, home env `HERMES_HOME`, needs `hermes` on PATH.
- **claude-code**: `["npx","-y","@agentclientprotocol/claude-agent-acp"]`, home env `CLAUDE_CONFIG_DIR`, needs `claude` on PATH (adapter fetched via npx).

The profile's existing `hermes_home` column is reused as the generic "agent home" path (each runner gets its own dir under the profile, pointed at by that runner's home env).

---

## Task 1: runner registry (spawn spec per runner)

**Files:** Create `apps/api/hive_os_api/runner_specs.py`; Test `apps/api/tests/test_runner_specs.py`

- [ ] **Step 1: failing test** — `apps/api/tests/test_runner_specs.py`:
```python
from hive_os_api.runner_specs import runner_spec, RUNNER_SPECS


def test_hermes_spec():
    s = runner_spec("hermes")
    assert s.spawn_argv[:2] == ["hermes", "acp"]
    assert s.home_env == "HERMES_HOME"


def test_claude_code_spec():
    s = runner_spec("claude-code")
    assert "claude-agent-acp" in " ".join(s.spawn_argv)
    assert s.home_env == "CLAUDE_CONFIG_DIR"
    assert s.binary == "claude"


def test_unknown_runner_falls_back_to_hermes():
    assert runner_spec("nope").id == "hermes"


def test_registry_has_expected_runners():
    assert set(["hermes", "claude-code"]).issubset(RUNNER_SPECS.keys())
```

- [ ] **Step 2:** run → fail (ImportError).
  `cd apps/api && uv run pytest tests/test_runner_specs.py -q`

- [ ] **Step 3: implement** `apps/api/hive_os_api/runner_specs.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunnerSpec:
    id: str
    spawn_argv: list[str]
    home_env: str
    binary: str          # the underlying CLI that must be installed/authenticated
    display_name: str
    auth_hint: str = ""


RUNNER_SPECS: dict[str, RunnerSpec] = {
    "hermes": RunnerSpec(
        id="hermes",
        spawn_argv=["hermes", "acp", "--accept-hooks"],
        home_env="HERMES_HOME",
        binary="hermes",
        display_name="Hermes",
        auth_hint="Install the Hermes CLI and authenticate (e.g. `hermes -z`).",
    ),
    "claude-code": RunnerSpec(
        id="claude-code",
        spawn_argv=["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
        home_env="CLAUDE_CONFIG_DIR",
        binary="claude",
        display_name="Claude Code",
        auth_hint="Install Claude Code and run `claude /login` (or set ANTHROPIC_API_KEY).",
    ),
}

DEFAULT_RUNNER = "hermes"


def runner_spec(runner_id: str | None) -> RunnerSpec:
    return RUNNER_SPECS.get(runner_id or DEFAULT_RUNNER, RUNNER_SPECS[DEFAULT_RUNNER])
```

- [ ] **Step 4:** run → pass.
- [ ] **Step 5: commit** `feat(runners): runner spawn-spec registry (hermes + claude-code)`.

---

## Task 2: generalize AcpProcess to spawn per-runner

**Files:** Modify `apps/api/hive_os_api/acp.py`

Today `AcpProcess.__init__(hermes_home, cwd)` and `start()` hardcode `hermes acp` + `HERMES_HOME`. Generalize to carry a `RunnerSpec`.

- [ ] **Step 1:** Change `AcpProcess.__init__` to `(self, spec, home, cwd)` storing `self.spec = spec`, `self.home = home`, `self.cwd = cwd`. Keep a `self.hermes_home` alias = `home` for any existing references (grep first; update them).

- [ ] **Step 2:** In `start()`, replace the hardcoded env + exec:
```python
        env = os.environ.copy()
        if self.home:
            env[self.spec.home_env] = self.home
            os.makedirs(self.home, exist_ok=True)
        env["PATH"] = augmented_path(env.get("PATH"))
        os.makedirs(self.cwd, exist_ok=True)
        self.proc = await asyncio.create_subprocess_exec(
            *self.spec.spawn_argv,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=env, cwd=self.cwd, limit=READ_LIMIT,
        )
```
(`config_sig(self.home)` stays — it signs the profile home; keep using `self.home`.)

- [ ] **Step 3:** Update `AcpManager.get/recycle` to key by `(spec.id, home, cwd)` and take `spec`:
  `async def get(self, spec, home, cwd)` / `async def recycle(self, spec, home, cwd)`. Key = `(spec.id, home, cwd)`. Construct `AcpProcess(spec, home, cwd)`.

- [ ] **Step 4:** Import `RunnerSpec`/`runner_spec` where needed. Run `cd apps/api && uv run pytest -q` — the existing run-path tests (test_run_errors, test_tasks) exercise AcpManager via fakes; ensure they still pass (the fakes define their own get/recycle signatures, so update fakes if their signatures must match — check test_run_errors `FakeAcpManager.get(self, hermes_home, cwd=None)` and adjust to `get(self, spec=None, home=None, cwd=None)` keeping back-compat).

- [ ] **Step 5: commit** `refactor(acp): drive any runner via spawn-spec (not hardcoded hermes)`.

---

## Task 3: profiles carry a runner_id

**Files:** `apps/api/hive_os_api/db.py` (schema + migrate_existing), `apps/api/hive_os_api/migrations.py` (versioned add), `apps/api/hive_os_api/main.py` (profile create/payload)

- [ ] **Step 1:** Add to `profiles` CREATE TABLE: `runner_id TEXT NOT NULL DEFAULT 'hermes'`. Add to `migrate_existing`: `_add_column(conn, "profiles", "runner_id", "runner_id TEXT NOT NULL DEFAULT 'hermes'")`. Add a versioned migration entry (next version) that does the same `ADD COLUMN` idempotently (so existing prod DBs gain it with an auto-backup).

- [ ] **Step 2:** `ProfileCreateRequest` gains `runner_id: str = "hermes"` (validate it's in RUNNER_SPECS, else 400). `create_profile_for` / `create_profile` store it. `profile_payload` returns `runner_id`.

- [ ] **Step 3:** Test in `apps/api/tests/test_profile_seed.py` (or a new test): creating a profile with `runner_id="claude-code"` persists and is returned; default is `hermes`.

- [ ] **Step 4:** `cd apps/api && uv run pytest -q` → pass.
- [ ] **Step 5: commit** `feat(profiles): per-profile runner_id (migration v2)`.

---

## Task 4: worker resolves the profile's runner

**Files:** `apps/api/hive_os_api/main.py` (execute_run + run insert)

- [ ] **Step 1:** When creating a run, record the profile's `runner_id` on the run (the `runs.runner_id` column already exists — currently always 'hermes'; set it from the profile).

- [ ] **Step 2:** In `execute_run`, resolve `spec = runner_spec(run["runner_id"])` and call `acp_manager.get(spec, hermes_home, cwd)` / `recycle(spec, hermes_home, cwd)`. The credential-refresh block (`refresh_hermes_credentials`) should only run for `spec.id == "hermes"`.

- [ ] **Step 3:** Run the full suite. Verify Hermes path unaffected.
- [ ] **Step 4: commit** `feat(runner): execute_run drives the profile's runner via spec`.

---

## Task 5: detection + readiness for claude-code

**Files:** `apps/api/hive_os_api/runners.py`, `main.py` runners_detect

- [ ] **Step 1:** Add a `runner_ready(runner_id, path_env=None) -> {ready, binary, guidance}` helper (mirror `hermes_status`): resolves `spec.binary` on PATH; ready if found; guidance = `spec.auth_hint` when not. For claude-code, "ready" means `claude` is on PATH (login is verified at run time, surfaced via stderr like Phase 1).

- [ ] **Step 2:** `runners_detect`: for each registry runner that has a spec, set `runnable = binary found`; keep the rest detection-only. Return per-runner readiness.

- [ ] **Step 3:** Test: with `claude` present (or a stubbed PATH), claude-code is reported runnable.
- [ ] **Step 4: commit** `feat(runners): report claude-code runnable + readiness`.

---

## Task 6: UI — pick a runner when creating a profile

**Files:** `apps/web/src/screens/ProfilesScreen.tsx` (+ api/profiles.ts, types.ts)

- [ ] **Step 1:** `Profile` type gains `runner_id`. Profile-create API sends `runner_id`.
- [ ] **Step 2:** Profile create form: a Dropdown of available runners (from `/api/runners/detect`, only `runnable` ones), default Hermes. Show the auth hint if the picked runner isn't ready.
- [ ] **Step 3:** `npx tsc --noEmit && npm run build` clean.
- [ ] **Step 4: commit** `feat(web): choose a runner when creating a profile`.

---

## Task 7: end-to-end verification

- [ ] Build + restart in the worktree on a throwaway port/workspace (NOT the live service).
- [ ] Confirm Hermes profile still runs a chat to completion.
- [ ] Create a `claude-code` profile; run a chat; confirm a real Claude Code response (requires `claude` logged in on host). If not logged in, confirm the surfaced guidance ("run claude /login") rather than a blank.
- [ ] Capture evidence. Then a final review before merge.

---

## Notes / deferred
- **Codex** (`@zed-industries/codex-acp`, binary `codex`) and **Gemini CLI** (native `gemini --experimental-acp`, home env `GEMINI_*`/config) = add as RUNNER_SPECS entries later; same plumbing.
- **Per-user Claude login isolation** via `CLAUDE_CONFIG_DIR` needs a real-auth check in Task 7; if isolation is imperfect, document it (shared host = shared Claude login unless each profile dir is logged in separately).
- **npx cold-start latency**: first claude-code run downloads the adapter; consider pinning/installing it in install-user later.
