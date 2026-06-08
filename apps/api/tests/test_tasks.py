from __future__ import annotations
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
        async def get(self, home, cwd=None): return FakeProc()
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
