from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from hive_os_api.main import create_app
from hive_os_api.runners import RunnerDefinition, detect_runners


def test_detect_runners_uses_hive_registry_and_controlled_path(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ["hermes", "codex", "aider"]:
        file = bin_dir / name
        file.write_text("#!/bin/sh\nexit 0\n")
        file.chmod(0o755)

    registry = (
        RunnerDefinition("hermes", "Hermes", ("hermes",), True),
        RunnerDefinition("claude-code", "Claude Code", ("definitely-missing-claude",), True),
        RunnerDefinition("codex", "Codex", ("codex",), True),
        RunnerDefinition("aider", "Aider", ("aider",), False, detection_only=True),
    )
    result = {runner["id"]: runner for runner in detect_runners(path_env=str(bin_dir), registry=registry)}

    assert result["hermes"]["installed"] is True
    assert result["hermes"]["runnable"] is True
    assert result["hermes"]["path"] == str(bin_dir / "hermes")

    assert result["codex"]["installed"] is True
    assert result["codex"]["runnable"] is True

    assert result["claude-code"]["installed"] is False
    assert result["claude-code"]["runnable"] is False

    assert result["aider"]["installed"] is True
    assert result["aider"]["hasAdapter"] is False
    assert result["aider"]["detectionOnly"] is True
    assert result["aider"]["runnable"] is False


def test_runners_detect_endpoint_requires_login(tmp_path: Path):
    app = create_app(
        {
            "database_path": str(tmp_path / "hive.db"),
            "workspace_root": str(tmp_path / "workspace"),
            "projectctl_path": "/usr/bin/true",
            "seed_users": [{"username": "aris", "role": "member", "os_user": "aris"}],
        }
    )
    client = TestClient(app)

    assert client.get("/api/runners/detect").status_code == 401

    token = client.post("/auth/login", json={"username": "aris", "password": "password123"}).json()["token"]
    res = client.get("/api/runners/detect", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    body = res.json()
    assert body["user"] == "aris"
    assert any(runner["id"] == "hermes" for runner in body["runners"])
    assert all(runner["id"] != "manual" for runner in body["runners"])
