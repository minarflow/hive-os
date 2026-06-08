from fastapi.testclient import TestClient
from hive_os_api.main import create_app


def _app(tmp_path):
    return create_app({"database_path": str(tmp_path / "h.db"), "workspace_root": str(tmp_path / "ws"), "projectctl_path": "/usr/bin/true", "start_worker": False})


def test_profile_defaults_to_hermes(tmp_path):
    c = TestClient(_app(tmp_path))
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    profs = c.get("/api/profiles", headers={"Authorization": f"Bearer {tok}"}).json()["profiles"]
    assert profs[0]["runner_id"] == "hermes"


def test_create_profile_with_claude_code_runner(tmp_path):
    c = TestClient(_app(tmp_path))
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/api/profiles", headers=h, json={"name": "CC", "slug": "cc", "runner_id": "claude-code"})
    assert r.status_code in (200, 201), r.text
    assert r.json()["runner_id"] == "claude-code"


def test_unknown_runner_rejected(tmp_path):
    c = TestClient(_app(tmp_path))
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert c.post("/api/profiles", headers=h, json={"name": "X", "slug": "x", "runner_id": "bogus"}).status_code == 400


def test_bootstrap_sets_runner(tmp_path):
    c = TestClient(_app(tmp_path))
    r = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default", "runner_id": "claude-code"})
    assert r.status_code == 201, r.text
    tok = r.json()["token"]
    profs = c.get("/api/profiles", headers={"Authorization": f"Bearer {tok}"}).json()["profiles"]
    assert profs[0]["runner_id"] == "claude-code"


def test_bootstrap_rejects_unknown_runner(tmp_path):
    c = TestClient(_app(tmp_path))
    r = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default", "runner_id": "bogus"})
    assert r.status_code == 400


def test_change_profile_runner(tmp_path):
    c = TestClient(_app(tmp_path))
    tok = c.post("/api/setup/bootstrap", json={"username": "k", "password": "password123", "profile_name": "D", "profile_slug": "default"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = c.get("/api/profiles", headers=h).json()["profiles"][0]["id"]
    r = c.patch(f"/api/profiles/{pid}", headers=h, json={"runner_id": "codex"})
    assert r.status_code == 200 and r.json()["runner_id"] == "codex"
    assert c.patch(f"/api/profiles/{pid}", headers=h, json={"runner_id": "nope"}).status_code == 400
