from __future__ import annotations

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def test_bootstrap_creates_admin_default_profile_and_password_login(tmp_path):
    app = create_app({"database_path": str(tmp_path / "hive.db"), "workspace_root": str(tmp_path / "workspace"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    client = TestClient(app)

    assert client.get("/api/setup/status").json()["bootstrap_required"] is True
    boot = client.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"})
    assert boot.status_code == 201
    assert boot.json()["user"]["username"] == "kuya"
    assert boot.json()["profile"]["slug"] == "default"
    assert (tmp_path / "workspace" / "hermes-profiles" / "kuya" / "default").exists()
    assert client.post("/auth/login", json={"username": "kuya", "password": "wrongpass"}).status_code == 401
    assert client.post("/auth/login", json={"username": "kuya", "password": "password123"}).status_code == 200


def test_user_can_create_multiple_hermes_profiles(tmp_path):
    app = create_app({"database_path": str(tmp_path / "hive.db"), "workspace_root": str(tmp_path / "workspace"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    client = TestClient(app)
    token = client.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/profiles", headers=headers, json={"slug": "minarflow", "name": "Minarflow", "default_model": "test/model"})
    assert created.status_code == 201
    assert created.json()["slug"] == "minarflow"
    body = client.get("/api/profiles", headers=headers).json()
    assert [p["slug"] for p in body["profiles"]] == ["default", "minarflow"]
    assert (tmp_path / "workspace" / "hermes-profiles" / "kuya" / "minarflow").exists()


def test_run_creation_is_async_and_persists_events(tmp_path):
    app = create_app({"database_path": str(tmp_path / "hive.db"), "workspace_root": str(tmp_path / "workspace"), "projectctl_path": "/usr/bin/true", "start_worker": False})
    client = TestClient(app)
    token = client.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    session = client.post("/api/sessions", headers=headers, json={"title": "Async"}).json()

    run = client.post(f"/api/sessions/{session['id']}/runs", headers=headers, json={"message": "hello"})
    assert run.status_code == 202
    assert run.json()["status"] == "queued"
    events = client.get(f"/api/sessions/{session['id']}/events", headers=headers).json()["events"]
    assert events[0]["type"] == "run.queued"
