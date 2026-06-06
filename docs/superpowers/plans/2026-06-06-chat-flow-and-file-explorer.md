# Chat Flow Fix + Right-Sidebar File Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hive OS chat work end-to-end (real Hermes output, visible errors, working slash commands, responsive layout) and turn the right sidebar into a full project-scoped file explorer (navigate, view, edit, create, rename, delete).

**Architecture:** FastAPI backend gains (1) a credential-seeding helper that copies provider/config files from `~/.hermes` into each new isolated profile home, (2) a path-jailed project filesystem API, and (3) clearer run error reporting. The React/Vite PWA gains client-side slash-command handling, error rendering in the chat thread, a responsive shell, and a `WorkspaceTree` file explorer with an inline editor.

**Tech Stack:** Python 3.13, FastAPI, SQLite, pytest, FastAPI `TestClient`; React 19, Vite, TypeScript.

**Conventions:**
- Backend is TDD: write pytest first, watch it fail, implement, watch it pass, commit.
- Frontend has no test runner; the gate is `cd apps/web && npm run build` (tsc type-check + Vite build) plus a manual run note. Commit after each task.
- Run backend tests with: `cd apps/api && uv run pytest -q`
- All work happens in `/home/kuya/storage/projects/hive-os`.

---

## File Structure

**Backend — new files:**
- `apps/api/hive_os_api/profile_seed.py` — `seed_hermes_home(source, target)` copies credential/config files into a new profile home. One responsibility: seeding.
- `apps/api/hive_os_api/fsapi.py` — pure project-filesystem helpers (jail resolution + tree/read/write/mkdir/rename/delete). No FastAPI imports; takes/returns plain types so it is unit-testable.
- `apps/api/tests/test_profile_seed.py` — unit tests for seeding.
- `apps/api/tests/test_fsapi.py` — unit tests for jail + fs helpers.
- `apps/api/tests/test_files_api.py` — endpoint tests for the file API.

**Backend — modified files:**
- `apps/api/hive_os_api/settings.py` — add `source_hermes_home` default config key.
- `apps/api/hive_os_api/main.py` — call seeding inside `create_profile_for`; add `/api/projects/{slug}/tree`, `/file`, `/fs/mkdir`, `/fs/rename`, `/fs` (DELETE); fix `execute_run` error/empty handling.

**Frontend — new files:**
- `apps/web/src/api/commands.ts` — catalog + execute client.
- `apps/web/src/api/files.ts` — file API client.
- `apps/web/src/components/files/WorkspaceTree.tsx` — file explorer tree.
- `apps/web/src/components/files/FileEditor.tsx` — inline file viewer/editor.

**Frontend — modified files:**
- `apps/web/src/types.ts` — add `FileEntry` type.
- `apps/web/src/components/chat/Composer.tsx` — slash popover + intercept.
- `apps/web/src/screens/ChatScreen.tsx` — route slash commands; render errors.
- `apps/web/src/components/chat/ChatThread.tsx` — render error/warning events.
- `apps/web/src/App.tsx` — `/new` creates+switches session.
- `apps/web/src/components/shell/RightRail.tsx` — host `WorkspaceTree`.
- `apps/web/src/components/shell/AppShell.tsx` — responsive right rail toggle.
- `apps/web/src/styles.css` — responsive breakpoints + tree/editor styling.

---

## Phase A: Chat flow

### Task A1: Credential seeding into new profile homes

**Files:**
- Create: `apps/api/hive_os_api/profile_seed.py`
- Create: `apps/api/tests/test_profile_seed.py`
- Modify: `apps/api/hive_os_api/settings.py`
- Modify: `apps/api/hive_os_api/main.py` (inside `create_profile_for`)

- [ ] **Step 1: Write the failing unit test**

Create `apps/api/tests/test_profile_seed.py`:

```python
from __future__ import annotations

from pathlib import Path

from hive_os_api.profile_seed import SEED_FILES, seed_hermes_home


def test_seed_copies_credential_files_and_skips_state(tmp_path):
    source = tmp_path / "src-hermes"
    source.mkdir()
    (source / ".env").write_text("OPENROUTER_API_KEY=abc\n", encoding="utf-8")
    (source / "auth.json").write_text("{}", encoding="utf-8")
    (source / "config.yaml").write_text("model: x\n", encoding="utf-8")
    (source / "sessions").mkdir()
    (source / "sessions" / "a.json").write_text("{}", encoding="utf-8")
    (source / "checkpoints").mkdir()
    (source / "config.yaml.bak.20260101").write_text("old", encoding="utf-8")

    target = tmp_path / "profile-home"
    target.mkdir()

    copied = seed_hermes_home(source, target)

    assert (target / ".env").read_text(encoding="utf-8") == "OPENROUTER_API_KEY=abc\n"
    assert (target / "auth.json").exists()
    assert (target / "config.yaml").exists()
    assert not (target / "sessions").exists()
    assert not (target / "checkpoints").exists()
    assert not (target / "config.yaml.bak.20260101").exists()
    assert set(copied) == set(SEED_FILES)


def test_seed_is_idempotent_and_does_not_overwrite(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / ".env").write_text("NEW=2\n", encoding="utf-8")
    target = tmp_path / "tgt"
    target.mkdir()
    (target / ".env").write_text("KEEP=1\n", encoding="utf-8")

    copied = seed_hermes_home(source, target)

    assert (target / ".env").read_text(encoding="utf-8") == "KEEP=1\n"
    assert ".env" not in copied


def test_seed_missing_source_is_noop(tmp_path):
    target = tmp_path / "tgt"
    target.mkdir()
    assert seed_hermes_home(tmp_path / "nope", target) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_profile_seed.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hive_os_api.profile_seed'`

- [ ] **Step 3: Implement `profile_seed.py`**

Create `apps/api/hive_os_api/profile_seed.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

# Credential/config files Hermes reads at startup. Copied into each isolated
# profile HERMES_HOME so `hermes -z` can authenticate. Conversation state
# (sessions/, checkpoints/, logs/, backups/, *.bak*) is intentionally excluded
# so per-profile conversation isolation is preserved.
SEED_FILES: tuple[str, ...] = (".env", "auth.json", "config.yaml")


def seed_hermes_home(source: Path, target: Path) -> list[str]:
    """Copy credential/config files from source into target.

    Idempotent: never overwrites a file that already exists in target.
    No-op (returns []) when source is missing. Returns the names copied.
    """
    source = Path(source)
    target = Path(target)
    if not source.is_dir():
        return []
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in SEED_FILES:
        src = source / name
        dst = target / name
        if src.is_file() and not dst.exists():
            shutil.copy2(src, dst)
            copied.append(name)
    return copied
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_profile_seed.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Add `source_hermes_home` to settings**

In `apps/api/hive_os_api/settings.py`, add to `DEFAULT_CONFIG` dict (after the `hermes_profiles_root` line):

```python
    "source_hermes_home": None,
```

Then in `normalize_config`, before `return cfg`, add:

```python
    import os
    cfg["source_hermes_home"] = str(Path(cfg.get("source_hermes_home") or os.path.expanduser("~/.hermes")))
```

- [ ] **Step 6: Wire seeding into `create_profile_for`**

In `apps/api/hive_os_api/main.py`, add the import near the other local imports at the top of the file (next to `from .settings import ...`):

```python
from .profile_seed import seed_hermes_home
```

Then in `create_profile_for`, immediately after `home.mkdir(parents=True, exist_ok=True)`, add:

```python
        seed_hermes_home(Path(cfg["source_hermes_home"]), home)
```

- [ ] **Step 7: Write an endpoint-level test that seeding runs on profile create**

Add to `apps/api/tests/test_profile_seed.py`:

```python
from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def test_bootstrap_seeds_profile_home_from_source(tmp_path):
    source = tmp_path / "source-hermes"
    source.mkdir()
    (source / ".env").write_text("OPENROUTER_API_KEY=xyz\n", encoding="utf-8")

    app = create_app({
        "database_path": str(tmp_path / "hive.db"),
        "workspace_root": str(tmp_path / "ws"),
        "projectctl_path": "/usr/bin/true",
        "source_hermes_home": str(source),
        "start_worker": False,
    })
    client = TestClient(app)
    client.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"})

    seeded = tmp_path / "ws" / "hermes-profiles" / "kuya" / "default" / ".env"
    assert seeded.read_text(encoding="utf-8") == "OPENROUTER_API_KEY=xyz\n"
```

- [ ] **Step 8: Run the full suite**

Run: `cd apps/api && uv run pytest -q`
Expected: PASS (all previous 18 + 4 new = 22 passed)

- [ ] **Step 9: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/api/hive_os_api/profile_seed.py apps/api/hive_os_api/settings.py apps/api/hive_os_api/main.py apps/api/tests/test_profile_seed.py
git commit -m "feat(api): seed Hermes credentials into new profile homes"
```

---

### Task A2: Surface runner errors instead of "(no output)"

**Files:**
- Modify: `apps/api/hive_os_api/main.py` (`execute_run`, around lines 216-230)
- Modify: `apps/web/src/components/chat/ChatThread.tsx`

- [ ] **Step 1: Write the failing test**

Add `apps/api/tests/test_run_errors.py`:

```python
from __future__ import annotations

import asyncio

from hive_os_api.main import create_app, RunWorker


def _drain(app):
    asyncio.get_event_loop()


def test_failed_run_stores_error_text_not_no_output(tmp_path, monkeypatch):
    app = create_app({
        "database_path": str(tmp_path / "hive.db"),
        "workspace_root": str(tmp_path / "ws"),
        "projectctl_path": "/usr/bin/true",
        "start_worker": False,
    })
    from fastapi.testclient import TestClient
    client = TestClient(app)
    token = client.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    session = client.post("/api/sessions", headers=headers, json={"title": "x"}).json()
    client.post(f"/api/sessions/{session['id']}/runs", headers=headers, json={"message": "hi"})

    worker = app.state.worker

    async def fake_subprocess(*args, **kwargs):
        class P:
            pid = 4242
            returncode = 1
            stdout = None
            stderr = None
            async def wait(self):
                return 1
        return P()

    monkeypatch.setattr("hive_os_api.main.asyncio.create_subprocess_exec", fake_subprocess)

    async def run_once():
        run = worker.claim_run()
        assert run is not None
        await worker.execute_run(run)

    asyncio.get_event_loop().run_until_complete(run_once())

    msgs = client.get(f"/api/sessions/{session['id']}/messages", headers=headers).json()["messages"]
    assert any(m["role"] == "assistant" for m in msgs)
    last = [m for m in msgs if m["role"] == "assistant"][-1]
    assert last["content"] != "(no output)"
    assert "fail" in last["content"].lower() or "error" in last["content"].lower() or last["content"].startswith("Run failed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/test_run_errors.py -q`
Expected: FAIL — assistant content is `(no output)` (current behavior stores `"(no output)"` and an empty stderr → no error text).

- [ ] **Step 3: Fix `execute_run` empty/error handling**

In `apps/api/hive_os_api/main.py`, locate this block (around line 219-230):

```python
            answer = "".join(final_chunks).strip() or "(no output)"
            with self.app.state.db_lock:
                cur = db.execute("INSERT INTO messages(session_id, role, content) VALUES (?, 'assistant', ?)", (session_id, answer))
                db.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
                if proc.returncode == 0:
                    self.add_event(run_id, session_id, project_id, "message.complete", {"message_id": cur.lastrowid, "text": answer})
                    self.add_event(run_id, session_id, project_id, "run.completed", {"exit_code": proc.returncode})
                    db.execute("UPDATE runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
                else:
                    error = answer[-1200:]
                    self.add_event(run_id, session_id, project_id, "run.failed", {"exit_code": proc.returncode, "error": error})
                    db.execute("UPDATE runs SET status = 'failed', error = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (error, run_id))
```

Replace it with (note: `error_chunks` is added in Step 4):

```python
            stdout_text = "".join(final_chunks).strip()
            stderr_text = "".join(error_chunks).strip()
            ok = proc.returncode == 0 and stdout_text
            if ok:
                answer = stdout_text
            else:
                detail = stderr_text or stdout_text or "Hermes produced no output."
                answer = f"Run failed (exit {proc.returncode}): {detail}"[-2000:]
            with self.app.state.db_lock:
                cur = db.execute("INSERT INTO messages(session_id, role, content) VALUES (?, 'assistant', ?)", (session_id, answer))
                db.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
                if ok:
                    self.add_event(run_id, session_id, project_id, "message.complete", {"message_id": cur.lastrowid, "text": answer})
                    self.add_event(run_id, session_id, project_id, "run.completed", {"exit_code": proc.returncode})
                    db.execute("UPDATE runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
                else:
                    self.add_event(run_id, session_id, project_id, "message.complete", {"message_id": cur.lastrowid, "text": answer})
                    self.add_event(run_id, session_id, project_id, "run.failed", {"exit_code": proc.returncode, "error": answer})
                    db.execute("UPDATE runs SET status = 'failed', error = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (answer, run_id))
```

- [ ] **Step 4: Capture stderr into `error_chunks`**

In `execute_run`, find the line `final_chunks: list[str] = []` (around line 172) and add right after it:

```python
        error_chunks: list[str] = []
```

Then in the inner `read_stream` function, find the `else:` branch that handles stderr (around line 211-213):

```python
                    else:
                        with self.app.state.db_lock:
                            self.add_event(run_id, session_id, project_id, "warning", {"stream": "stderr", "text": text})
```

Replace it with:

```python
                    else:
                        error_chunks.append(text)
                        with self.app.state.db_lock:
                            self.add_event(run_id, session_id, project_id, "warning", {"stream": "stderr", "text": text})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/test_run_errors.py -q`
Expected: PASS (1 passed)

- [ ] **Step 6: Run full backend suite**

Run: `cd apps/api && uv run pytest -q`
Expected: PASS (all green)

- [ ] **Step 7: Render error/warning events in the chat thread**

Replace the entire body of `apps/web/src/components/chat/ChatThread.tsx` with:

```tsx
import type { ChatMessage, RunEvent } from '../../types'

export function ChatThread({ messages, events, pendingRunId, pendingText }: { messages: ChatMessage[]; events: RunEvent[]; pendingRunId?: number | null; pendingText?: string }) {
  const completedRunIds = new Set(events.filter(e => ['message.complete', 'run.completed', 'run.failed', 'run.cancelled'].includes(e.type)).map(e => e.run_id))
  const deltas = pendingRunId && !completedRunIds.has(pendingRunId)
    ? events.filter(e => e.type === 'message.delta' && e.run_id === pendingRunId).map(e => String(e.payload.text || '')).join('')
    : ''
  const failures = events.filter(e => e.type === 'run.failed')

  return <div className="thread"><div className="chat-log">
    {messages.map((message, index) => <div className={`chat-line ${message.role}`} key={message.id ?? index}><strong>{message.role === 'user' ? 'You' : message.role === 'assistant' ? 'Hermes' : 'Hive OS'}</strong><span>{message.content}</span></div>)}
    {deltas && <div className="chat-line assistant"><strong>Hermes streaming</strong><span>{deltas}</span></div>}
    {failures.map(e => <div className="chat-line error" key={`err-${e.id}`}><strong>Run error</strong><span>{String(e.payload.error || 'Run failed')}</span></div>)}
    {pendingText && <div className="chat-line pending"><strong>Run</strong><span><i className="typing-dot" /> {pendingText}</span></div>}
  </div></div>
}
```

- [ ] **Step 8: Add error-line styling**

In `apps/web/src/styles.css`, append:

```css
.chat-line.error { border-left: 3px solid #dc2626; background: #fef2f2; }
.chat-line.error strong { color: #b91c1c; }
.chat-line.error span { color: #7f1d1d; white-space: pre-wrap; }
```

- [ ] **Step 9: Type-check / build the web app**

Run: `cd apps/web && npm run build`
Expected: build succeeds, no TypeScript errors.

- [ ] **Step 10: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/api/hive_os_api/main.py apps/api/tests/test_run_errors.py apps/web/src/components/chat/ChatThread.tsx apps/web/src/styles.css
git commit -m "feat: surface Hermes run errors in chat instead of silent (no output)"
```

---

### Task A3: Slash commands in the composer (`/new` etc.)

**Files:**
- Create: `apps/web/src/api/commands.ts`
- Modify: `apps/web/src/components/chat/Composer.tsx`
- Modify: `apps/web/src/screens/ChatScreen.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Add the commands API client**

Create `apps/web/src/api/commands.ts`:

```ts
import { api } from './client'

export type CatalogCommand = { name: string; description: string; surface: string; unavailableMessage: string | null }
export type CommandCatalog = { groups: Array<{ label: string; commands: CatalogCommand[] }> }

export const getCommandCatalog = (token: string) => api<CommandCatalog>('/api/commands/catalog', token)
```

- [ ] **Step 2: Add a `onNewSession` prop to `ChatScreen` and intercept `/new`**

In `apps/web/src/screens/ChatScreen.tsx`, change the component props signature (line 9) to add `onNewSession`:

Add `onNewSession: () => Promise<void>` to the props type, then change `submit` (lines 47-58) so it intercepts slash commands before creating a run:

```tsx
  async function submit(text: string) {
    setError('')
    try {
      const trimmed = text.trim()
      if (trimmed.startsWith('/') && !trimmed.startsWith('//')) {
        const name = trimmed.split(/\s+/)[0].toLowerCase()
        if (name === '/new' || name === '/reset') { await props.onNewSession(); return }
        if (name === '/help' || name === '/status' || name === '/session' || name === '/project' || name === '/runner') {
          setMessages(current => [...current, { role: 'system', content: localCommandReply(name, props) }])
          return
        }
        if (name === '/model' || name === '/clear' || name === '/tools') {
          setMessages(current => [...current, { role: 'system', content: `${name} is managed by Hive OS UI, not raw chat.` }])
          return
        }
      }
      const prompt = trimmed.startsWith('//') ? trimmed.slice(1) : text
      const session = await ensureSession(prompt)
      setMessages(current => [...current, { role: 'user', content: prompt }])
      const run = await createRun(props.token, session.id, { message: prompt, profile_id: props.activeProfile?.id || null, model: props.activeProfile?.default_model || null })
      setBusyRun(run.run_id)
      const eventBody = await listEvents(props.token, session.id)
      setEvents(eventBody.events)
      await props.onRefresh()
    } catch (err) { setError(String(err)) }
  }
```

Add this helper function above the `ChatScreen` component (after the imports):

```tsx
function localCommandReply(name: string, props: { activeProject: Project | null; activeProfile: Profile | null; activeSession: ChatSession | null }): string {
  switch (name) {
    case '/help': return 'Commands: /new (new session), /status, /session, /project, /runner. Prefix // to send a literal slash message to Hermes.'
    case '/status': return `Project: ${props.activeProject?.name || 'none'} · Profile: ${props.activeProfile?.name || 'none'} · Runner: hermes`
    case '/session': return `Session: ${props.activeSession?.title || 'new chat'}`
    case '/project': return `Project: ${props.activeProject?.name || 'none'} (${props.activeProject?.slug || '-'})`
    case '/runner': return 'Active runner: hermes (only runner enabled).'
    default: return 'Unknown command.'
  }
}
```

- [ ] **Step 3: Implement `/new` in `App.tsx`**

In `apps/web/src/App.tsx`, add an import:

```tsx
import { createSession } from './api/sessions'
```

Add this callback inside `App` (after `doLogout`):

```tsx
  async function startNewSession() {
    const created = await createSession(token, { title: 'New chat', project_slug: activeProject?.slug || null, profile_id: activeProfile?.id || null })
    setActiveSession(created)
    setView('chat')
    await refreshAll(token)
  }
```

Then pass it to `ChatScreen` (line 103), adding the prop:

```tsx
      {view === 'chat' && <ChatScreen activeProfile={activeProfile} activeProject={activeProject} activeSession={activeSession} profiles={profiles} projects={projects} token={token} onActiveProfile={setActiveProfile} onActiveProject={setActiveProject} onSession={setActiveSession} onRefresh={refreshAll} onNewSession={startNewSession} />}
```

- [ ] **Step 4: Slash popover autocomplete in `Composer`**

Replace the body of `apps/web/src/components/chat/Composer.tsx` with:

```tsx
import React from 'react'
import { getCommandCatalog, type CatalogCommand } from '../../api/commands'

export function Composer({ disabled, token, onSubmit }: { disabled?: boolean; token: string; onSubmit: (text: string) => Promise<void> }) {
  const [draft, setDraft] = React.useState('')
  const [commands, setCommands] = React.useState<CatalogCommand[]>([])

  React.useEffect(() => {
    if (!token) return
    void getCommandCatalog(token).then(c => setCommands(c.groups.flatMap(g => g.commands))).catch(() => undefined)
  }, [token])

  const showPopover = draft.startsWith('/') && !draft.startsWith('//') && !draft.includes(' ')
  const matches = showPopover ? commands.filter(c => c.name.startsWith(draft.toLowerCase())) : []

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || disabled) return
    setDraft('')
    await onSubmit(text)
  }

  return <form className="composer" onSubmit={submit}>
    {matches.length > 0 && <div className="slash-popover">{matches.map(c => <button type="button" key={c.name} onClick={() => setDraft(c.name + ' ')}><strong>{c.name}</strong><span>{c.description}</span><em>{c.surface}</em></button>)}</div>}
    <textarea placeholder="Message Hermes in this project…" value={draft} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }} />
    <div className="composer-footer"><span>Hermes Team Mode · async streaming</span><button className="primary-button" disabled={disabled || !draft.trim()} type="submit">Send</button></div>
  </form>
}
```

- [ ] **Step 5: Pass `token` to `Composer` in `ChatScreen`**

In `apps/web/src/screens/ChatScreen.tsx`, find the `<Composer ... />` usage (end of the render) and change it to:

```tsx
<Composer disabled={!props.activeProfile} token={props.token} onSubmit={submit} />
```

- [ ] **Step 6: Type-check / build**

Run: `cd apps/web && npm run build`
Expected: build succeeds, no TypeScript errors.

- [ ] **Step 7: Manual verification**

Run: `cd /home/kuya/storage/projects/hive-os && bash scripts/dev` (in a background terminal), open `http://127.0.0.1:5177`, log in, type `/new` and confirm a new session is created and the left sidebar reflects it; type `/help` and confirm a system reply appears; type `//hello` and confirm it sends a literal message to Hermes.

- [ ] **Step 8: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/web/src/api/commands.ts apps/web/src/components/chat/Composer.tsx apps/web/src/screens/ChatScreen.tsx apps/web/src/App.tsx
git commit -m "feat(web): wire slash commands incl /new session switch"
```

---

### Task A4: Responsive layout

**Files:**
- Modify: `apps/web/src/components/shell/AppShell.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Add a right-rail toggle + responsive class to `AppShell`**

In `apps/web/src/components/shell/AppShell.tsx`, add state and a toggle. Change the `useState` block (lines 22-23) to:

```tsx
  const [drawerOpen, setDrawerOpen] = React.useState(false)
  const [collapsed, setCollapsed] = React.useState(false)
  const [railOpen, setRailOpen] = React.useState(false)
```

Change the root `div` className (line 25) to include rail state:

```tsx
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''} ${railOpen ? 'rail-open' : ''}`}>
```

In the `main-header` (lines 32-35), add a rail toggle button after the `context-chips` div:

```tsx
          <button className="icon-button rail-toggle" onClick={() => setRailOpen(v => !v)} aria-label="Toggle files">⌸</button>
```

Wrap the `<RightRail .../>` (line 38) so it can be dismissed on mobile:

```tsx
      {railOpen && <button aria-label="Close files" className="drawer-scrim rail-scrim" onClick={() => setRailOpen(false)} />}
      <RightRail activeProfile={props.activeProfile} activeProject={props.activeProject} activeSession={props.activeSession} projects={props.projects} />
```

- [ ] **Step 2: Add responsive CSS**

In `apps/web/src/styles.css`, append:

```css
/* Responsive shell: hide right rail on narrow widths, open as overlay */
.rail-toggle { display: none; }
.rail-scrim { display: none; }
@media (max-width: 1279px) {
  .app-shell .right-rail { position: fixed; top: 0; right: 0; height: 100%; width: min(360px, 86vw); transform: translateX(100%); transition: transform .2s ease; z-index: 40; box-shadow: -8px 0 24px rgba(0,0,0,.18); }
  .app-shell.rail-open .right-rail { transform: translateX(0); }
  .app-shell.rail-open .rail-scrim { display: block; position: fixed; inset: 0; z-index: 39; background: rgba(0,0,0,.35); border: 0; }
  .rail-toggle { display: inline-flex; }
}
@media (max-width: 767px) {
  .main-pane { min-width: 0; }
  .chat-stage, .thread, .chat-log { max-width: 100vw; }
  .composer textarea { width: 100%; box-sizing: border-box; }
  .toolbar-row { flex-wrap: wrap; gap: 8px; }
}
```

- [ ] **Step 3: Build**

Run: `cd apps/web && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual verification**

With the dev server running, open Chrome DevTools device toolbar at 390px width: confirm the chat fills the screen, the composer does not overflow, the left menu opens as a drawer, and the right files panel opens as an overlay via the header toggle.

- [ ] **Step 5: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/web/src/components/shell/AppShell.tsx apps/web/src/styles.css
git commit -m "feat(web): responsive shell with toggleable right rail"
```

---

## Phase B: Right-sidebar file explorer

### Task B1: Path-jail filesystem helpers (pure module)

**Files:**
- Create: `apps/api/hive_os_api/fsapi.py`
- Create: `apps/api/tests/test_fsapi.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_fsapi.py`:

```python
from __future__ import annotations

import pytest

from hive_os_api import fsapi


def _project(tmp_path):
    root = tmp_path / "proj"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("hello", encoding="utf-8")
    (root / "sub" / "b.md").write_text("# title", encoding="utf-8")
    return root


def test_resolve_in_project_rejects_traversal(tmp_path):
    root = _project(tmp_path)
    with pytest.raises(fsapi.FsError):
        fsapi.resolve_in_project(root, "../secret")
    with pytest.raises(fsapi.FsError):
        fsapi.resolve_in_project(root, "/etc/passwd")


def test_resolve_in_project_allows_inside(tmp_path):
    root = _project(tmp_path)
    assert fsapi.resolve_in_project(root, "sub/b.md") == (root / "sub" / "b.md").resolve()
    assert fsapi.resolve_in_project(root, "") == root.resolve()


def test_list_tree_returns_sorted_dirs_first(tmp_path):
    root = _project(tmp_path)
    entries = fsapi.list_tree(root, "")
    assert entries[0] == {"name": "sub", "type": "dir", "size": 0}
    assert {"name": "a.txt", "type": "file", "size": 5} in entries


def test_read_and_write_file(tmp_path):
    root = _project(tmp_path)
    assert fsapi.read_file(root, "a.txt") == "hello"
    fsapi.write_file(root, "sub/c.txt", "new content")
    assert (root / "sub" / "c.txt").read_text(encoding="utf-8") == "new content"


def test_read_file_rejects_too_large(tmp_path):
    root = _project(tmp_path)
    (root / "big.txt").write_text("x" * (fsapi.MAX_READ_BYTES + 1), encoding="utf-8")
    with pytest.raises(fsapi.FsError):
        fsapi.read_file(root, "big.txt")


def test_mkdir_rename_delete(tmp_path):
    root = _project(tmp_path)
    fsapi.mkdir(root, "newdir")
    assert (root / "newdir").is_dir()
    fsapi.rename(root, "a.txt", "renamed.txt")
    assert (root / "renamed.txt").exists() and not (root / "a.txt").exists()
    fsapi.delete(root, "renamed.txt")
    assert not (root / "renamed.txt").exists()
    fsapi.delete(root, "sub")
    assert not (root / "sub").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_fsapi.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'hive_os_api.fsapi'`

- [ ] **Step 3: Implement `fsapi.py`**

Create `apps/api/hive_os_api/fsapi.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

MAX_READ_BYTES = 1_000_000


class FsError(Exception):
    """Raised for any disallowed or invalid filesystem operation."""


def resolve_in_project(root: Path, rel: str) -> Path:
    """Resolve rel against the project root, jailed inside it.

    Rejects absolute paths and any path that escapes the project root
    (including via .. or symlinks).
    """
    root = Path(root).resolve()
    rel = (rel or "").strip().lstrip("/")
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise FsError("path escapes project root")
    return target


def list_tree(root: Path, rel: str) -> list[dict]:
    target = resolve_in_project(root, rel)
    if not target.is_dir():
        raise FsError("not a directory")
    entries: list[dict] = []
    for child in target.iterdir():
        is_dir = child.is_dir()
        entries.append({
            "name": child.name,
            "type": "dir" if is_dir else "file",
            "size": 0 if is_dir else child.stat().st_size,
        })
    entries.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))
    return entries


def read_file(root: Path, rel: str) -> str:
    target = resolve_in_project(root, rel)
    if not target.is_file():
        raise FsError("not a file")
    if target.stat().st_size > MAX_READ_BYTES:
        raise FsError("file too large to open")
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FsError("binary file not supported") from exc


def write_file(root: Path, rel: str, content: str) -> None:
    target = resolve_in_project(root, rel)
    if target.is_dir():
        raise FsError("target is a directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def mkdir(root: Path, rel: str) -> None:
    target = resolve_in_project(root, rel)
    target.mkdir(parents=True, exist_ok=True)


def rename(root: Path, src_rel: str, dst_rel: str) -> None:
    src = resolve_in_project(root, src_rel)
    dst = resolve_in_project(root, dst_rel)
    if not src.exists():
        raise FsError("source does not exist")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)


def delete(root: Path, rel: str) -> None:
    target = resolve_in_project(root, rel)
    if target == Path(root).resolve():
        raise FsError("cannot delete project root")
    if not target.exists():
        raise FsError("path does not exist")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd apps/api && uv run pytest tests/test_fsapi.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/api/hive_os_api/fsapi.py apps/api/tests/test_fsapi.py
git commit -m "feat(api): path-jailed project filesystem helpers"
```

---

### Task B2: File API endpoints

**Files:**
- Modify: `apps/api/hive_os_api/main.py` (add request models + endpoints)
- Create: `apps/api/tests/test_files_api.py`

- [ ] **Step 1: Write the failing endpoint test**

Create `apps/api/tests/test_files_api.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def client(tmp_path: Path) -> TestClient:
    app = create_app({
        "database_path": str(tmp_path / "hive.db"),
        "workspace_root": str(tmp_path / "ws"),
        "projectctl_path": "/usr/bin/true",
        "start_worker": False,
    })
    return TestClient(app)


def setup_project(c: TestClient, tmp_path: Path) -> dict:
    token = c.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = c.post("/api/projects", headers=headers, json={"slug": "demo", "name": "Demo"}).json()
    # projectctl is /usr/bin/true so create the dir ourselves to mirror real behavior
    Path(proj["path"]).mkdir(parents=True, exist_ok=True)
    return headers


def test_tree_read_write_mkdir_rename_delete(tmp_path):
    c = client(tmp_path)
    headers = setup_project(c, tmp_path)

    assert c.put("/api/projects/demo/file?path=notes/a.txt", headers=headers, json={"content": "hello"}).status_code == 200
    tree = c.get("/api/projects/demo/tree?path=notes", headers=headers).json()["entries"]
    assert {"name": "a.txt", "type": "file", "size": 5} in tree

    body = c.get("/api/projects/demo/file?path=notes/a.txt", headers=headers).json()
    assert body["content"] == "hello"

    assert c.post("/api/projects/demo/fs/mkdir", headers=headers, json={"path": "newdir"}).status_code == 200
    assert c.post("/api/projects/demo/fs/rename", headers=headers, json={"from": "notes/a.txt", "to": "notes/b.txt"}).status_code == 200
    assert c.delete("/api/projects/demo/fs?path=notes/b.txt", headers=headers).status_code == 200


def test_traversal_is_rejected(tmp_path):
    c = client(tmp_path)
    headers = setup_project(c, tmp_path)
    assert c.get("/api/projects/demo/tree?path=../..", headers=headers).status_code == 400


def test_non_member_cannot_access(tmp_path):
    c = client(tmp_path)
    headers = setup_project(c, tmp_path)
    # create a second user via admin and log in as them
    c.post("/api/users", headers=headers, json={"username": "aris", "password": "password123", "role": "member", "profile_name": "Default", "profile_slug": "default"})
    other = c.post("/auth/login", json={"username": "aris", "password": "password123"}).json()["token"]
    oh = {"Authorization": f"Bearer {other}"}
    assert c.get("/api/projects/demo/tree", headers=oh).status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd apps/api && uv run pytest tests/test_files_api.py -q`
Expected: FAIL — 404/405 for the file routes (not implemented yet).

- [ ] **Step 3: Add request models**

In `apps/api/hive_os_api/main.py`, near the other `BaseModel` request classes (after `ChatSendRequest`), add:

```python
class FileWriteRequest(BaseModel):
    content: str


class FsPathRequest(BaseModel):
    path: str = Field(min_length=1)


class FsRenameRequest(BaseModel):
    from_: str = Field(min_length=1, alias="from")
    to: str = Field(min_length=1)

    model_config = {"populate_by_name": True}
```

- [ ] **Step 4: Add the import for fsapi**

In `apps/api/hive_os_api/main.py`, add near the other local imports:

```python
from . import fsapi
```

- [ ] **Step 5: Add the endpoints**

In `apps/api/hive_os_api/main.py`, add these routes inside `create_app` (place them right after the `list_members` endpoint, before `list_sessions`). Note `visible_project` enforces membership (raises 404 for non-members) and `fsapi.FsError` maps to 400:

```python
    def _project_root(slug: str, user: dict[str, Any]) -> Path:
        project = visible_project(slug, user)
        return Path(project["path"])

    def _audit_fs(user: dict[str, Any], action: str, slug: str, path: str) -> None:
        db().execute(
            "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, metadata) VALUES (?, ?, 'project', ?, ?)",
            (user["id"], action, slug, json.dumps({"path": path})),
        )

    @app.get("/api/projects/{slug}/tree")
    def project_tree(slug: str, path: str = "", user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            return {"path": path, "entries": fsapi.list_tree(root, path)}
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{slug}/file")
    def project_read_file(slug: str, path: str, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            return {"path": path, "content": fsapi.read_file(root, path)}
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/projects/{slug}/file")
    def project_write_file(slug: str, path: str, payload: FileWriteRequest, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.write_file(root, path, payload.content)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "file.write", slug, path)
        return {"ok": True, "path": path}

    @app.post("/api/projects/{slug}/fs/mkdir")
    def project_mkdir(slug: str, payload: FsPathRequest, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.mkdir(root, payload.path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "fs.mkdir", slug, payload.path)
        return {"ok": True, "path": payload.path}

    @app.post("/api/projects/{slug}/fs/rename")
    def project_rename(slug: str, payload: FsRenameRequest, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.rename(root, payload.from_, payload.to)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "fs.rename", slug, f"{payload.from_} -> {payload.to}")
        return {"ok": True}

    @app.delete("/api/projects/{slug}/fs")
    def project_delete(slug: str, path: str, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.delete(root, path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "fs.delete", slug, path)
        return {"ok": True, "path": path}
```

- [ ] **Step 6: Run to verify pass**

Run: `cd apps/api && uv run pytest tests/test_files_api.py -q`
Expected: PASS (3 passed)

- [ ] **Step 7: Run full backend suite**

Run: `cd apps/api && uv run pytest -q`
Expected: PASS (all green)

- [ ] **Step 8: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/api/hive_os_api/main.py apps/api/tests/test_files_api.py
git commit -m "feat(api): project-scoped file explorer endpoints"
```

---

### Task B3: Frontend file API client + types

**Files:**
- Modify: `apps/web/src/types.ts`
- Create: `apps/web/src/api/files.ts`

- [ ] **Step 1: Add the `FileEntry` type**

In `apps/web/src/types.ts`, append:

```ts
export type FileEntry = { name: string; type: 'dir' | 'file'; size: number }
```

- [ ] **Step 2: Create the files API client**

Create `apps/web/src/api/files.ts`:

```ts
import { api } from './client'
import type { FileEntry } from '../types'

const q = (s: string) => encodeURIComponent(s)

export const listTree = (token: string, slug: string, path = '') =>
  api<{ path: string; entries: FileEntry[] }>(`/api/projects/${slug}/tree?path=${q(path)}`, token)

export const readFile = (token: string, slug: string, path: string) =>
  api<{ path: string; content: string }>(`/api/projects/${slug}/file?path=${q(path)}`, token)

export const writeFile = (token: string, slug: string, path: string, content: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/file?path=${q(path)}`, token, { method: 'PUT', body: JSON.stringify({ content }) })

export const mkdir = (token: string, slug: string, path: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/fs/mkdir`, token, { method: 'POST', body: JSON.stringify({ path }) })

export const renamePath = (token: string, slug: string, from: string, to: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/fs/rename`, token, { method: 'POST', body: JSON.stringify({ from, to }) })

export const deletePath = (token: string, slug: string, path: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/fs?path=${q(path)}`, token, { method: 'DELETE' })
```

- [ ] **Step 3: Verify `api` client signature**

Open `apps/web/src/api/client.ts` and confirm `api(path, token, init?)` accepts a third `RequestInit` arg (it is used this way in `api/sessions.ts`). If the signature differs, adjust the calls in `files.ts` to match the existing pattern. Then build:

Run: `cd apps/web && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/web/src/types.ts apps/web/src/api/files.ts
git commit -m "feat(web): file explorer API client + FileEntry type"
```

---

### Task B4: `WorkspaceTree` explorer + `FileEditor`

**Files:**
- Create: `apps/web/src/components/files/WorkspaceTree.tsx`
- Create: `apps/web/src/components/files/FileEditor.tsx`
- Modify: `apps/web/src/components/shell/RightRail.tsx`
- Modify: `apps/web/src/components/shell/AppShell.tsx` (pass `token`)
- Modify: `apps/web/src/App.tsx` (pass `token` to AppShell)
- Modify: `apps/web/src/styles.css` (tree + editor styles)

- [ ] **Step 1: Create the `FileEditor` component**

Create `apps/web/src/components/files/FileEditor.tsx`:

```tsx
import React from 'react'
import { readFile, writeFile } from '../../api/files'

export function FileEditor({ token, slug, path, onClose }: { token: string; slug: string; path: string; onClose: () => void }) {
  const [content, setContent] = React.useState('')
  const [status, setStatus] = React.useState('loading')

  React.useEffect(() => {
    setStatus('loading')
    readFile(token, slug, path).then(b => { setContent(b.content); setStatus('ready') }).catch(e => setStatus(String(e)))
  }, [token, slug, path])

  async function save() {
    setStatus('saving')
    try { await writeFile(token, slug, path, content); setStatus('saved') } catch (e) { setStatus(String(e)) }
  }

  return <div className="file-editor">
    <div className="file-editor-head"><strong>{path}</strong><div><button onClick={() => void save()}>Save</button><button onClick={onClose}>Close</button></div></div>
    {status === 'loading' ? <p className="muted">Loading…</p> : <textarea value={content} onChange={e => setContent(e.target.value)} />}
    <div className="file-editor-status muted">{status}</div>
  </div>
}
```

- [ ] **Step 2: Create the `WorkspaceTree` component**

Create `apps/web/src/components/files/WorkspaceTree.tsx`:

```tsx
import React from 'react'
import type { FileEntry, Project } from '../../types'
import { listTree, mkdir, renamePath, deletePath, writeFile } from '../../api/files'
import { FileEditor } from './FileEditor'

function Node({ token, slug, dir, depth, onOpen, refreshKey }: { token: string; slug: string; dir: string; depth: number; onOpen: (path: string) => void; refreshKey: number }) {
  const [open, setOpen] = React.useState(depth === 0)
  const [entries, setEntries] = React.useState<FileEntry[]>([])
  const [loaded, setLoaded] = React.useState(false)

  const load = React.useCallback(() => {
    listTree(token, slug, dir).then(b => { setEntries(b.entries); setLoaded(true) }).catch(() => setLoaded(true))
  }, [token, slug, dir])

  React.useEffect(() => { if (open) load() }, [open, load, refreshKey])

  return <div className="tree-node">
    {entries.map(entry => {
      const path = dir ? `${dir}/${entry.name}` : entry.name
      return entry.type === 'dir'
        ? <Folder key={path} token={token} slug={slug} path={path} name={entry.name} depth={depth} onOpen={onOpen} refreshKey={refreshKey} />
        : <button key={path} className="tree-row file" style={{ paddingLeft: 8 + depth * 12 }} onClick={() => onOpen(path)}>📄 {entry.name}</button>
    })}
    {loaded && entries.length === 0 && depth === 0 && <p className="muted tree-empty">Empty project</p>}
  </div>
}

function Folder({ token, slug, path, name, depth, onOpen, refreshKey }: { token: string; slug: string; path: string; name: string; depth: number; onOpen: (path: string) => void; refreshKey: number }) {
  const [open, setOpen] = React.useState(false)
  return <div>
    <button className="tree-row dir" style={{ paddingLeft: 8 + depth * 12 }} onClick={() => setOpen(v => !v)}>{open ? '▾' : '▸'} 📁 {name}</button>
    {open && <Node token={token} slug={slug} dir={path} depth={depth + 1} onOpen={onOpen} refreshKey={refreshKey} />}
  </div>
}

export function WorkspaceTree({ token, project }: { token: string; project: Project | null }) {
  const [refreshKey, setRefreshKey] = React.useState(0)
  const [editing, setEditing] = React.useState<string | null>(null)
  const refresh = () => setRefreshKey(k => k + 1)

  if (!project) return <aside className="right-rail"><div className="rail-card"><p className="muted">Select a project to browse files.</p></div></aside>

  async function newFile() {
    const name = window.prompt('New file path (relative to project):')
    if (!name) return
    await writeFile(token, project!.slug, name, '').catch(() => undefined)
    refresh()
  }
  async function newFolder() {
    const name = window.prompt('New folder path:')
    if (!name) return
    await mkdir(token, project!.slug, name).catch(() => undefined)
    refresh()
  }
  async function rename() {
    const from = window.prompt('Rename from (path):'); if (!from) return
    const to = window.prompt('Rename to (path):'); if (!to) return
    await renamePath(token, project!.slug, from, to).catch(() => undefined)
    refresh()
  }
  async function remove() {
    const path = window.prompt('Delete path:'); if (!path) return
    if (!window.confirm(`Delete ${path}? This cannot be undone.`)) return
    await deletePath(token, project!.slug, path).catch(() => undefined)
    refresh()
  }

  return <aside className="right-rail">
    <div className="tree-toolbar"><strong>{project.name}</strong><div className="tree-actions"><button title="New file" onClick={() => void newFile()}>＋📄</button><button title="New folder" onClick={() => void newFolder()}>＋📁</button><button title="Rename" onClick={() => void rename()}>✎</button><button title="Delete" onClick={() => void remove()}>🗑</button></div></div>
    <div className="tree-scroll"><Node token={token} slug={project.slug} dir="" depth={0} onOpen={setEditing} refreshKey={refreshKey} /></div>
    {editing && <FileEditor token={token} slug={project.slug} path={editing} onClose={() => setEditing(null)} />}
  </aside>
}
```

- [ ] **Step 3: Wire `WorkspaceTree` into `RightRail`**

Replace the contents of `apps/web/src/components/shell/RightRail.tsx` with:

```tsx
import type { ChatSession, Profile, Project } from '../../types'
import { WorkspaceTree } from '../files/WorkspaceTree'

export function RightRail({ token, activeProject }: { token: string; activeProfile: Profile | null; activeProject: Project | null; activeSession: ChatSession | null; projects: Project[] }) {
  return <WorkspaceTree token={token} project={activeProject} />
}
```

- [ ] **Step 4: Pass `token` from `AppShell` to `RightRail`**

In `apps/web/src/components/shell/AppShell.tsx`, add `token: string` to the props type, and update the `<RightRail .../>` usage to pass it:

```tsx
      <RightRail token={props.token} activeProfile={props.activeProfile} activeProject={props.activeProject} activeSession={props.activeSession} projects={props.projects} />
```

- [ ] **Step 5: Pass `token` from `App` to `AppShell`**

In `apps/web/src/App.tsx`, add `token={token}` to the `<AppShell ...>` props (alongside `user={user}`).

- [ ] **Step 6: Add tree + editor styling**

In `apps/web/src/styles.css`, append:

```css
.tree-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-bottom: 1px solid var(--ui-stroke-tertiary, #e5e7eb); }
.tree-actions button { border: 0; background: transparent; cursor: pointer; padding: 2px 4px; }
.tree-scroll { overflow: auto; flex: 1; padding: 4px 0; }
.tree-row { display: block; width: 100%; text-align: left; border: 0; background: transparent; cursor: pointer; padding: 4px 8px; font-size: .85rem; white-space: nowrap; }
.tree-row:hover { background: var(--ui-row-hover-background, #f1f5f9); }
.tree-empty { padding: 8px 10px; }
.file-editor { position: absolute; inset: 0; display: flex; flex-direction: column; background: var(--ui-bg-editor, #fff); z-index: 5; }
.file-editor-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; border-bottom: 1px solid var(--ui-stroke-tertiary, #e5e7eb); }
.file-editor-head button { margin-left: 6px; }
.file-editor textarea { flex: 1; width: 100%; border: 0; padding: 10px; font-family: ui-monospace, monospace; font-size: .85rem; resize: none; box-sizing: border-box; }
.file-editor-status { padding: 4px 10px; font-size: .75rem; }
.right-rail { display: flex; flex-direction: column; position: relative; }
```

- [ ] **Step 7: Build**

Run: `cd apps/web && npm run build`
Expected: build succeeds, no TypeScript errors.

- [ ] **Step 8: Manual verification**

With `bash scripts/dev` running and logged in: select a project, confirm the right rail shows its file tree; expand a folder; click a file to open the editor, edit and Save (confirm the change persists on disk); use the toolbar to create a file/folder, rename, and delete (with confirm). On a 390px viewport, confirm the rail opens as an overlay via the header toggle.

- [ ] **Step 9: Commit**

```bash
cd /home/kuya/storage/projects/hive-os
git add apps/web/src/components/files apps/web/src/components/shell/RightRail.tsx apps/web/src/components/shell/AppShell.tsx apps/web/src/App.tsx apps/web/src/styles.css
git commit -m "feat(web): right-sidebar workspace file explorer with inline editor"
```

---

## Final verification (whole feature)

- [ ] **Backend:** `cd apps/api && uv run pytest -q` → all green.
- [ ] **Frontend:** `cd apps/web && npm run build` → succeeds.
- [ ] **End-to-end manual** (`bash scripts/dev`, open `http://127.0.0.1:5177`):
  1. Log in → select project + profile → send "say hi" → Hermes's answer appears (or a readable error if it fails).
  2. `/new` → switches to a new session; left sidebar follows.
  3. Phone-width layout: chat full-screen, composer not overflowing, left drawer + right files overlay both work.
  4. File tree: navigate, open+edit+save a file, create/rename/delete file & folder — all confined to the project.

## Self-review notes (author)

- Spec A1 (seed) → Task A1. A2 (surface errors) → Task A2. A3 (slash/`/new`) → Task A3. A4 (responsive) → Task A4. B1 (backend fs API) → Tasks B1+B2. B2 (frontend explorer + editor) → Tasks B3+B4. All spec sections covered.
- Type consistency: `FileEntry` defined in B3 and consumed in B4; `seed_hermes_home`/`SEED_FILES` defined and imported consistently; `fsapi.FsError` used uniformly; `onNewSession` prop added in A3 (ChatScreen) and supplied from A3 (App).
- Known caveat: frontend uses `window.prompt/confirm` for fs actions (fast, dependency-free). A richer inline rename/context-menu UX is a deliberate post-today polish, not a placeholder.
