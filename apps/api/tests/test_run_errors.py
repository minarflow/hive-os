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
