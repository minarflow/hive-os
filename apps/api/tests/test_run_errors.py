from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


class FakeAcpProcess:
    def __init__(self, behavior: str):
        self.behavior = behavior

    async def load_session(self, session_id, cwd):
        raise Exception("not loadable")  # force a fresh new_session

    async def new_session(self, cwd):
        return "acp-test-1"

    async def prompt(self, session_id, text, on_update, timeout=600):
        if self.behavior == "fail":
            raise Exception("boom from runner")
        if self.behavior == "stream":
            on_update({"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "hello world"}})
        return "end_turn"

    def cancel(self, session_id):
        pass


class FakeAcpManager:
    def __init__(self, behavior: str):
        self.behavior = behavior

    async def get(self, hermes_home):
        return FakeAcpProcess(self.behavior)

    async def shutdown(self):
        pass


def _setup(tmp_path, behavior):
    app = create_app({
        "database_path": str(tmp_path / "hive.db"),
        "workspace_root": str(tmp_path / "ws"),
        "projectctl_path": "/usr/bin/true",
        "start_worker": False,
    })
    app.state.acp_manager = FakeAcpManager(behavior)
    client = TestClient(app)
    token = client.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    session = client.post("/api/sessions", headers=headers, json={"title": "x"}).json()
    client.post(f"/api/sessions/{session['id']}/runs", headers=headers, json={"message": "hi"})

    async def run_once():
        run = app.state.worker.claim_run()
        assert run is not None
        await app.state.worker.execute_run(run)

    asyncio.run(run_once())
    return client, headers, session


def test_failed_run_stores_error_message(tmp_path):
    client, headers, session = _setup(tmp_path, "fail")
    msgs = client.get(f"/api/sessions/{session['id']}/messages", headers=headers).json()["messages"]
    err = [m for m in msgs if m["role"] == "error"]
    assert err and err[-1]["content"].startswith("Run failed")
    events = client.get(f"/api/sessions/{session['id']}/events", headers=headers).json()["events"]
    assert any(e["type"] == "run.failed" for e in events)


def test_streamed_run_persists_assistant_message_and_acp_session(tmp_path):
    client, headers, session = _setup(tmp_path, "stream")
    msgs = client.get(f"/api/sessions/{session['id']}/messages", headers=headers).json()["messages"]
    asst = [m for m in msgs if m["role"] == "assistant"]
    assert asst and asst[-1]["content"] == "hello world"
    events = client.get(f"/api/sessions/{session['id']}/events", headers=headers).json()["events"]
    assert any(e["type"] == "message.delta" for e in events)
    assert any(e["type"] == "run.completed" for e in events)
