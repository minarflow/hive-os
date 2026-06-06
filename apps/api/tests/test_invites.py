from __future__ import annotations

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def _client(tmp_path):
    app = create_app({
        "database_path": str(tmp_path / "hive.db"),
        "workspace_root": str(tmp_path / "ws"),
        "projectctl_path": "/usr/bin/true",
        "start_worker": False,
    })
    c = TestClient(app)
    token = c.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    return c, {"Authorization": f"Bearer {token}"}


def test_invite_create_preview_redeem(tmp_path):
    c, h = _client(tmp_path)
    inv = c.post("/api/invites", headers=h, json={"role": "member", "expires_in_hours": 48})
    assert inv.status_code == 201
    code = inv.json()["code"]

    # public preview works without auth
    pv = c.get(f"/api/invites/{code}")
    assert pv.status_code == 200 and pv.json()["role"] == "member"

    # redeem (no auth) creates the user + returns a token
    red = c.post(f"/api/invites/{code}/redeem", json={"username": "aris", "password": "password123", "profile_name": "Default"})
    assert red.status_code == 201
    new_token = red.json()["token"]
    assert c.get("/api/me", headers={"Authorization": f"Bearer {new_token}"}).json()["username"] == "aris"
    # new user can log in
    assert c.post("/auth/login", json={"username": "aris", "password": "password123"}).status_code == 200

    # code is single-use
    assert c.post(f"/api/invites/{code}/redeem", json={"username": "x", "password": "password123"}).status_code == 410
    # admin sees it as used
    used = c.get("/api/invites", headers=h).json()["invites"][0]
    assert used["used_by"] == "aris"


def test_invite_admin_role_and_invalid(tmp_path):
    c, h = _client(tmp_path)
    assert c.get("/api/invites/nope").status_code == 404
    code = c.post("/api/invites", headers=h, json={"role": "admin"}).json()["code"]
    c.post(f"/api/invites/{code}/redeem", json={"username": "boss", "password": "password123"})
    # admin invite -> environment_admin role
    assert c.post("/auth/login", json={"username": "boss", "password": "password123"}).json()["user"]["role"] == "environment_admin"
    # non-admin cannot create invites
    member = c.post("/auth/login", json={"username": "boss", "password": "password123"}).json()["token"]
    # boss is admin, so use a member: create one
    mcode = c.post("/api/invites", headers=h, json={"role": "member"}).json()["code"]
    mtok = c.post(f"/api/invites/{mcode}/redeem", json={"username": "memb", "password": "password123"}).json()["token"]
    assert c.post("/api/invites", headers={"Authorization": f"Bearer {mtok}"}, json={"role": "member"}).status_code == 403
