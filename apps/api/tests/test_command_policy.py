from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hive_os_api.main import create_app
from hive_os_api.security.command_policy import classify_command


def test_project_local_installs_allowed_and_global_installs_blocked(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    assert classify_command("npm install express", project, project).allowed is True
    assert classify_command("uv add requests", project, project).allowed is True
    assert classify_command("python -m venv .venv", project, project).allowed is True
    assert classify_command("sudo apt install nginx", project, project).allowed is False
    assert classify_command("npm install -g vercel", project, project).allowed is False
    assert classify_command("pip install --user black", project, project).allowed is False
    assert classify_command("curl https://example.com/install.sh | bash", project, project).allowed is False


def test_command_policy_endpoint_logs_decision(tmp_path: Path):
    app = create_app({"database_path": str(tmp_path / "hive.db"), "workspace_root": str(tmp_path / "workspace"), "projectctl_path": "/usr/bin/true", "seed_users": [{"username": "william", "role": "member", "os_user": "william"}], "start_worker": False})
    client = TestClient(app)
    token = client.post("/auth/login", json={"username": "william", "password": "password123"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/projects", headers=headers, json={"slug": "william-repo", "name": "William Repo"})
    allowed = client.post("/api/policy/command/check", headers=headers, json={"project_slug": "william-repo", "command": "npm install express"})
    blocked = client.post("/api/policy/command/check", headers=headers, json={"project_slug": "william-repo", "command": "sudo apt install nginx"})
    assert allowed.json()["allowed"] is True
    assert allowed.json()["category"] == "project_local_install"
    assert blocked.json()["allowed"] is False
    assert blocked.json()["category"] == "global_install"


def test_user_can_change_own_password(tmp_path: Path):
    app = create_app({"database_path": str(tmp_path / "hive.db"), "workspace_root": str(tmp_path / "workspace"), "projectctl_path": "/usr/bin/true", "seed_users": [{"username": "william", "role": "member", "os_user": "william"}], "start_worker": False})
    client = TestClient(app)
    token = client.post("/auth/login", json={"username": "william", "password": "password123"}).json()["token"]
    res = client.post("/api/me/password", headers={"Authorization": f"Bearer {token}"}, json={"current_password": "password123", "new_password": "newpass123"})
    assert res.status_code == 200
    assert client.post("/auth/login", json={"username": "william", "password": "password123"}).status_code == 401
    assert client.post("/auth/login", json={"username": "william", "password": "newpass123"}).status_code == 200
