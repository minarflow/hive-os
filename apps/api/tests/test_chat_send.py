from __future__ import annotations

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def test_chat_send_rejects_unwired_runner(tmp_path):
    app = create_app(
        {
            "database_path": str(tmp_path / "hive.db"),
            "workspace_root": str(tmp_path / "workspace"),
            "projectctl_path": "/usr/bin/true",
            "seed_users": [{"username": "aris", "role": "member", "os_user": "aris"}],
            "start_worker": False,
        }
    )
    client = TestClient(app)
    token = client.post("/auth/login", json={"username": "aris", "password": "password123"}).json()["token"]
    res = client.post("/api/chat/send", headers={"Authorization": f"Bearer {token}"}, json={"message": "hello", "runner_id": "opencode"})
    assert res.status_code == 400


def test_chat_send_hermes_enqueues_async_run(tmp_path):
    app = create_app(
        {
            "database_path": str(tmp_path / "hive.db"),
            "workspace_root": str(tmp_path / "workspace"),
            "projectctl_path": "/usr/bin/true",
            "seed_users": [{"username": "aris", "role": "member", "os_user": "aris"}],
            "start_worker": False,
        }
    )
    client = TestClient(app)
    token = client.post("/auth/login", json={"username": "aris", "password": "password123"}).json()["token"]

    res = client.post(
        "/api/chat/send",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "hello", "runner_id": "hermes", "model": "test/model"},
    )
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "queued"
    assert body["run_id"]

    events = client.get(f"/api/sessions/{body['session_id']}/events", headers={"Authorization": f"Bearer {token}"})
    assert events.status_code == 200
    assert events.json()["events"][0]["type"] == "run.queued"
