from __future__ import annotations
from pathlib import Path
from fastapi.testclient import TestClient
from hive_os_api.main import create_app


def test_task_crud_and_linked_thread(tmp_path):
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    c = TestClient(app)
    token = c.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    slug = c.get("/api/projects", headers=h).json()["projects"][0]["slug"]

    t = c.post(f"/api/projects/{slug}/tasks", headers=h, json={"title": "Fix login", "description": "bug"})
    assert t.status_code == 201
    task = t.json()
    assert task["status"] == "todo" and task["session_id"]

    # a dedicated agent thread (session) is linked to the task
    sess = [s for s in c.get("/api/sessions", headers=h).json()["sessions"] if s.get("task_id") == task["id"]]
    assert sess and sess[0]["task_title"] == "Fix login"

    assert len(c.get(f"/api/projects/{slug}/tasks", headers=h).json()["tasks"]) == 1

    # status transitions
    assert c.patch(f"/api/tasks/{task['id']}", headers=h, json={"status": "done"}).json()["status"] == "done"
    assert c.get(f"/api/tasks/{task['id']}", headers=h).json()["status"] == "done"

    # delete removes task + its thread
    assert c.delete(f"/api/tasks/{task['id']}", headers=h).status_code == 200
    assert c.get(f"/api/projects/{slug}/tasks", headers=h).json()["tasks"] == []
    assert [s for s in c.get("/api/sessions", headers=h).json()["sessions"] if s.get("task_id") == task["id"]] == []


def test_run_moves_task_to_review(tmp_path):
    import asyncio
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})

    class FakeProc:
        async def load_session(self, *a): raise Exception("new")
        async def new_session(self, *a): return "acp-1"
        async def prompt(self, sid, text, on_update, timeout=600):
            on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "done"}}); return "end_turn"
        def cancel(self, *a): pass

    class FakeMgr:
        async def get(self, spec=None, home=None, cwd=None): return FakeProc()
        async def shutdown(self): pass

    app.state.acp_manager = FakeMgr()
    c = TestClient(app)
    token = c.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    slug = c.get("/api/projects", headers=h).json()["projects"][0]["slug"]
    task = c.post(f"/api/projects/{slug}/tasks", headers=h, json={"title": "T"}).json()
    sid = task["session_id"]

    c.post(f"/api/sessions/{sid}/runs", headers=h, json={"message": "go"})
    assert c.get(f"/api/tasks/{task['id']}", headers=h).json()["status"] == "doing"  # set on run create

    async def run_once():
        run = app.state.worker.claim_run(); await app.state.worker.execute_run(run)
    asyncio.run(run_once())
    assert c.get(f"/api/tasks/{task['id']}", headers=h).json()["status"] == "review"  # set on completion


def test_task_payload_includes_creator(tmp_path):
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    c = TestClient(app)
    token = c.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    slug = c.get("/api/projects", headers=h).json()["projects"][0]["slug"]
    t = c.post(f"/api/projects/{slug}/tasks", headers=h, json={"title": "T"}).json()
    assert t["created_by"] == "kuya"


def test_collaborator_runs_in_shared_task_with_own_identity(tmp_path):
    # A shared-project member can work in another member's task, using their own
    # profile, and their chat message is attributed to them (not the creator).
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    c = TestClient(app)
    owner = c.post("/api/setup/bootstrap", json={"username": "iqbal", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    oh = {"Authorization": f"Bearer {owner}"}
    c.post("/api/users", headers=oh, json={"username": "george", "password": "password123", "role": "member", "profile_name": "Default", "profile_slug": "default"})
    gh = {"Authorization": f"Bearer {c.post('/auth/login', json={'username': 'george', 'password': 'password123'}).json()['token']}"}
    c.post("/api/projects", headers=oh, json={"slug": "team", "name": "Team", "visibility": "shared"})
    task = c.post("/api/projects/team/tasks", headers=oh, json={"title": "Build"}).json()
    c.post("/api/projects/team/invite", headers=oh, json={"username": "george"})
    sid = task["session_id"]
    r = c.post(f"/api/sessions/{sid}/runs", headers=gh, json={"message": "hi from george"})
    assert r.status_code == 202, r.text  # used to 404: run resolved the creator's profile
    msgs = c.get(f"/api/sessions/{sid}/messages", headers=gh).json()["messages"]
    assert any(m["role"] == "user" and m["author"] == "george" for m in msgs)


def test_collaborators_get_independent_agent_sessions(tmp_path):
    # Regression: a 2nd collaborator's run reused the 1st user's ACP session id,
    # which doesn't exist in the 2nd user's home. The adapter's load_session
    # silently "succeeds", so the prompt hit a missing session -> "no output".
    import asyncio
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})

    class FakeProc:
        def __init__(self): self.sessions = set()
        async def load_session(self, sid, cwd): pass  # silently succeeds even if unknown (the real bug)
        async def new_session(self, cwd):
            sid = f"s{len(self.sessions)}"; self.sessions.add(sid); return sid
        async def prompt(self, sid, text, on_update, timeout=600):
            if sid not in self.sessions:
                raise Exception(f"session {sid} not found")
            on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "ok"}})
            return "end_turn"

    class FakeMgr:
        def __init__(self): self.procs = {}
        async def get(self, spec=None, home=None, cwd=None): return self.procs.setdefault(home or "", FakeProc())
        async def recycle(self, spec=None, home=None, cwd=None): pass
        async def shutdown(self): pass

    app.state.acp_manager = FakeMgr()
    c = TestClient(app)
    oh = {"Authorization": f"Bearer {c.post('/api/setup/bootstrap', json={'username':'iqbal','password':'password123','profile_name':'I','profile_slug':'default'}).json()['token']}"}
    c.post("/api/users", headers=oh, json={"username": "george", "password": "password123", "role": "member", "profile_name": "G", "profile_slug": "default"})
    gh = {"Authorization": f"Bearer {c.post('/auth/login', json={'username':'george','password':'password123'}).json()['token']}"}
    c.post("/api/projects", headers=oh, json={"slug": "team", "name": "T", "visibility": "shared"})
    sid = c.post("/api/projects/team/tasks", headers=oh, json={"title": "x"}).json()["session_id"]
    c.post("/api/projects/team/invite", headers=oh, json={"username": "george"})

    def run_one():
        async def go():
            r = app.state.worker.claim_run(); assert r; await app.state.worker.execute_run(r)
        asyncio.run(go())

    c.post(f"/api/sessions/{sid}/runs", headers=oh, json={"message": "hi"}); run_one()   # iqbal (1st)
    c.post(f"/api/sessions/{sid}/runs", headers=gh, json={"message": "hi"}); run_one()   # george (2nd)
    asst = [m for m in c.get(f"/api/sessions/{sid}/messages", headers=gh).json()["messages"] if m["role"] == "assistant"]
    assert len(asst) == 2
    assert all("no output" not in m["content"].lower() for m in asst)  # both agents actually responded


def test_assistant_message_carries_run_id_and_activity(tmp_path):
    # The agent's tool/subagent activity persists on the saved message so the
    # swarm stays visible after the run. 'Task' tools are flagged as subagents.
    import asyncio
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})

    class FakeProc:
        async def load_session(self, *a): raise Exception("new")
        async def new_session(self, *a): return "acp-1"
        async def prompt(self, sid, text, on_update, timeout=600):
            on_update({"sessionUpdate": "tool_call", "toolCallId": "t1", "title": "Task"})
            on_update({"sessionUpdate": "tool_call", "toolCallId": "t2", "title": "Write fib.py"})
            on_update({"sessionUpdate": "tool_call_update", "toolCallId": "t2", "status": "completed"})
            on_update({"sessionUpdate": "tool_call_update", "toolCallId": "t1", "status": "completed"})
            on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "done"}})
            return "end_turn"
        def cancel(self, *a): pass

    class FakeMgr:
        async def get(self, spec=None, home=None, cwd=None): return FakeProc()
        async def recycle(self, *a, **k): pass
        async def shutdown(self): pass

    app.state.acp_manager = FakeMgr()
    c = TestClient(app)
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    sid = c.post("/api/sessions", headers=h, json={"title": "t"}).json()["id"]
    c.post(f"/api/sessions/{sid}/runs", headers=h, json={"message": "go"})

    async def run_once():
        r = app.state.worker.claim_run(); assert r; await app.state.worker.execute_run(r)
    asyncio.run(run_once())

    msgs = c.get(f"/api/sessions/{sid}/messages", headers=h).json()["messages"]
    asst = [m for m in msgs if m["role"] == "assistant"][-1]
    assert asst["run_id"]
    titles = {a["title"]: a for a in asst.get("activity", [])}
    assert "Task" in titles and titles["Task"]["subagent"] is True      # subagent flagged
    assert "Write fib.py" in titles and titles["Write fib.py"]["subagent"] is False
    assert titles["Task"]["status"] == "completed"


def test_successful_run_appends_auto_log(tmp_path):
    import asyncio
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})

    class FakeProc:
        def __init__(self): self.calls = 0
        async def load_session(self, *a): raise Exception("new")
        async def new_session(self, *a): return "acp-1"
        async def prompt(self, sid, text, on_update, timeout=600):
            self.calls += 1
            if self.calls == 1:
                on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "Built the feature."}})
            else:  # the summarize follow-up
                on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "Implemented login and added tests."}})
            return "end_turn"
        def cancel(self, *a): pass

    class FakeMgr:
        _proc = FakeProc()
        async def get(self, spec=None, home=None, cwd=None): return FakeMgr._proc
        async def recycle(self, *a, **k): pass
        async def shutdown(self): pass

    app.state.acp_manager = FakeMgr()
    c = TestClient(app)
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    proj = c.get("/api/projects", headers=h).json()["projects"][0]
    sid = c.post("/api/sessions", headers=h, json={"title": "t", "project_slug": proj["slug"]}).json()["id"]
    c.post(f"/api/sessions/{sid}/runs", headers=h, json={"message": "build login"})

    async def run_once():
        r = app.state.worker.claim_run(); assert r; await app.state.worker.execute_run(r)
    asyncio.run(run_once())

    log = Path(proj["path"]) / "wiki" / "log.md"
    assert log.exists()
    assert "Implemented login and added tests." in log.read_text(encoding="utf-8")
    assert FakeMgr._proc.calls == 2   # main turn + summarize turn


def test_auto_log_failure_does_not_fail_run(tmp_path):
    import asyncio
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})

    class FakeProc:
        def __init__(self): self.calls = 0
        async def load_session(self, *a): raise Exception("new")
        async def new_session(self, *a): return "acp-1"
        async def prompt(self, sid, text, on_update, timeout=600):
            self.calls += 1
            if self.calls == 1:
                on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "Did the work."}})
                return "end_turn"
            raise RuntimeError("summarizer exploded")
        def cancel(self, *a): pass

    class FakeMgr:
        async def get(self, spec=None, home=None, cwd=None): return FakeProc()
        async def recycle(self, *a, **k): pass
        async def shutdown(self): pass

    app.state.acp_manager = FakeMgr()
    c = TestClient(app)
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    proj = c.get("/api/projects", headers=h).json()["projects"][0]
    sid = c.post("/api/sessions", headers=h, json={"title": "t", "project_slug": proj["slug"]}).json()["id"]
    c.post(f"/api/sessions/{sid}/runs", headers=h, json={"message": "go"})

    async def run_once():
        r = app.state.worker.claim_run(); await app.state.worker.execute_run(r)
    asyncio.run(run_once())

    msgs = c.get(f"/api/sessions/{sid}/messages", headers=h).json()["messages"]
    asst = [m for m in msgs if m["role"] == "assistant"][-1]
    assert asst["content"] == "Did the work."   # run still completed cleanly


def test_wiki_draft_run_emits_draft_event(tmp_path):
    import asyncio
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})

    class FakeProc:
        async def load_session(self, *a): raise Exception("new")
        async def new_session(self, *a): return "acp-1"
        async def prompt(self, sid, text, on_update, timeout=600):
            draft = '```json\n{"title":"Caching","path":"perf/caching.md","body":"# Caching","related":[],"conflicts":[],"action":"new","target":null}\n```'
            on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": draft}})
            return "end_turn"
        def cancel(self, *a): pass

    class FakeMgr:
        async def get(self, spec=None, home=None, cwd=None): return FakeProc()
        async def recycle(self, *a, **k): pass
        async def shutdown(self): pass

    app.state.acp_manager = FakeMgr()
    c = TestClient(app)
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    proj = c.get("/api/projects", headers=h).json()["projects"][0]
    sid = c.post("/api/sessions", headers=h, json={"title": "t", "project_slug": proj["slug"]}).json()["id"]
    r = c.post(f"/api/sessions/{sid}/wiki-note/draft", headers=h, json={"profile_id": None})
    assert r.status_code == 202

    async def run_once():
        run = app.state.worker.claim_run(); assert run["kind"] == "wiki_draft"; await app.state.worker.execute_run(run)
    asyncio.run(run_once())

    events = c.get(f"/api/sessions/{sid}/events", headers=h).json()["events"]
    drafts = [e for e in events if e["type"] == "wiki.draft"]
    assert drafts, "expected a wiki.draft event"
    payload = drafts[-1]["payload"]
    assert payload["title"] == "Caching"
    assert payload["path"] == "perf/caching.md"
    msgs = c.get(f"/api/sessions/{sid}/messages", headers=h).json()["messages"]
    assert not [m for m in msgs if m["role"] == "assistant"]


def test_wiki_note_commit_writes_and_merges(tmp_path):
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    c = TestClient(app)
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    proj = c.get("/api/projects", headers=h).json()["projects"][0]
    sid = c.post("/api/sessions", headers=h, json={"title": "t", "project_slug": proj["slug"]}).json()["id"]
    note = Path(proj["path"]) / "wiki" / "perf" / "caching.md"

    r = c.post(f"/api/sessions/{sid}/wiki-note/commit", headers=h,
               json={"path": "perf/caching.md", "content": "# Caching\nUse Redis.", "mode": "new"})
    assert r.status_code == 200
    assert "Use Redis." in note.read_text(encoding="utf-8")

    r2 = c.post(f"/api/sessions/{sid}/wiki-note/commit", headers=h,
                json={"path": "perf/caching.md", "content": "## Update\nAdd TTL.", "mode": "append"})
    assert r2.status_code == 200
    merged = note.read_text(encoding="utf-8")
    assert "Use Redis." in merged and "Add TTL." in merged


def test_projectless_chat_has_no_wiki(tmp_path):
    # Wiki is project-scoped: a chat without a project can't be saved to a wiki,
    # and produces no auto-log (no hidden personal wiki).
    import asyncio
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})

    class FakeProc:
        async def load_session(self, *a): raise Exception("new")
        async def new_session(self, *a): return "acp-1"
        async def prompt(self, sid, text, on_update, timeout=600):
            on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "Did it."}})
            return "end_turn"
        def cancel(self, *a): pass

    class FakeMgr:
        async def get(self, spec=None, home=None, cwd=None): return FakeProc()
        async def recycle(self, *a, **k): pass
        async def shutdown(self): pass

    app.state.acp_manager = FakeMgr()
    c = TestClient(app)
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    sid = c.post("/api/sessions", headers=h, json={"title": "t"}).json()["id"]   # no project_slug

    # Draft is rejected for a project-less chat.
    r = c.post(f"/api/sessions/{sid}/wiki-note/draft", headers=h, json={"profile_id": None})
    assert r.status_code == 400

    # A normal run completes but writes no log anywhere under the workspace.
    c.post(f"/api/sessions/{sid}/runs", headers=h, json={"message": "go"})

    async def run_once():
        run = app.state.worker.claim_run(); await app.state.worker.execute_run(run)
    asyncio.run(run_once())

    assert not list((tmp_path / "ws").rglob("log.md"))


def test_wiki_commit_rebuilds_index(tmp_path):
    app = create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    c = TestClient(app)
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    proj = c.get("/api/projects", headers=h).json()["projects"][0]
    sid = c.post("/api/sessions", headers=h, json={"title": "t", "project_slug": proj["slug"]}).json()["id"]

    r = c.post(f"/api/sessions/{sid}/wiki-note/commit", headers=h,
               json={"path": "perf/caching.md", "content": "# Caching\n\nUse Redis.", "mode": "new"})
    assert r.status_code == 200
    idx = (Path(proj["path"]) / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "[Caching](perf/caching.md)" in idx
    assert "Use Redis." in idx
