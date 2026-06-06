from __future__ import annotations

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def authed(tmp_path):
    app = create_app(
        {
            "database_path": str(tmp_path / "hive.db"),
            "workspace_root": str(tmp_path / "workspace"),
            "projectctl_path": "/usr/bin/true",
            "seed_users": [{"username": "aris", "role": "member", "os_user": "aris"}],
        }
    )
    client = TestClient(app)
    token = client.post("/auth/login", json={"username": "aris", "password": "password123"}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_session_and_messages_lifecycle(tmp_path):
    client, headers = authed(tmp_path)

    created = client.post("/api/sessions", headers=headers, json={"title": "First chat", "runner_id": "hermes"})
    assert created.status_code == 201
    session_id = created.json()["id"]

    listed = client.get("/api/sessions", headers=headers).json()["sessions"]
    assert listed[0]["title"] == "First chat"
    assert listed[0]["runner_id"] == "hermes"

    msg = client.post(
        f"/api/sessions/{session_id}/messages",
        headers=headers,
        json={"role": "user", "content": "/status"},
    )
    assert msg.status_code == 200

    messages = client.get(f"/api/sessions/{session_id}/messages", headers=headers).json()["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "/status"


def test_session_messages_are_owner_scoped(tmp_path):
    app = create_app(
        {
            "database_path": str(tmp_path / "hive.db"),
            "workspace_root": str(tmp_path / "workspace"),
            "projectctl_path": "/usr/bin/true",
            "seed_users": [
                {"username": "aris", "role": "member", "os_user": "aris"},
                {"username": "kuya", "role": "environment_admin", "os_user": "kuya"},
            ],
        }
    )
    client = TestClient(app)
    aris = client.post("/auth/login", json={"username": "aris", "password": "password123"}).json()["token"]
    kuya = client.post("/auth/login", json={"username": "kuya", "password": "password123"}).json()["token"]
    sid = client.post("/api/sessions", headers={"Authorization": f"Bearer {aris}"}, json={"title": "Private"}).json()["id"]

    assert client.get(f"/api/sessions/{sid}/messages", headers={"Authorization": f"Bearer {kuya}"}).status_code == 404


def test_session_rename_and_delete(tmp_path):
    client, headers = authed(tmp_path)
    sid = client.post("/api/sessions", headers=headers, json={"title": "Old name"}).json()["id"]

    renamed = client.patch(f"/api/sessions/{sid}", headers=headers, json={"title": "New name"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "New name"
    assert client.get("/api/sessions", headers=headers).json()["sessions"][0]["title"] == "New name"

    deleted = client.delete(f"/api/sessions/{sid}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/sessions", headers=headers).json()["sessions"] == []
    # messages of a deleted session are gone (cascade) -> session not found
    assert client.get(f"/api/sessions/{sid}/messages", headers=headers).status_code == 404
