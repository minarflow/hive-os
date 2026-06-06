from __future__ import annotations

import asyncio

from hive_os_api.main import create_app, RunWorker


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

    asyncio.run(run_once())

    msgs = client.get(f"/api/sessions/{session['id']}/messages", headers=headers).json()["messages"]
    assert any(m["role"] == "error" for m in msgs)
    last = [m for m in msgs if m["role"] == "error"][-1]
    assert last["content"].startswith("Run failed")


def test_successful_empty_output_is_not_a_failure(tmp_path, monkeypatch):
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
    session = client.post("/api/sessions", headers=headers, json={"title": "y"}).json()
    client.post(f"/api/sessions/{session['id']}/runs", headers=headers, json={"message": "hello"})

    worker = app.state.worker

    async def fake_subprocess_ok(*args, **kwargs):
        class P:
            pid = 5050
            returncode = 0
            stdout = None
            stderr = None
            async def wait(self):
                return 0
        return P()

    monkeypatch.setattr("hive_os_api.main.asyncio.create_subprocess_exec", fake_subprocess_ok)

    async def run_once():
        run = worker.claim_run()
        assert run is not None
        await worker.execute_run(run)

    asyncio.run(run_once())

    msgs = client.get(f"/api/sessions/{session['id']}/messages", headers=headers).json()["messages"]
    assert any(m["role"] == "assistant" for m in msgs)
    last = [m for m in msgs if m["role"] == "assistant"][-1]
    assert last["content"] == "Hermes exited successfully but produced no output."

    events = client.get(f"/api/sessions/{session['id']}/events", headers=headers).json()["events"]
    assert not any(e["type"] == "run.failed" for e in events)
