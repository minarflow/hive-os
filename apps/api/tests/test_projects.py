from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def make_projectctl(tmp_path: Path) -> Path:
    log_path = tmp_path / "projectctl.log"
    script = tmp_path / "fake-hiveosctl"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"log = pathlib.Path({str(log_path)!r})\n"
        "log.write_text(log.read_text() + ' '.join(sys.argv[1:]) + '\\n' if log.exists() else ' '.join(sys.argv[1:]) + '\\n')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def client(tmp_path: Path) -> TestClient:
    ctl = make_projectctl(tmp_path)
    app = create_app(
        {
            "database_path": str(tmp_path / "hiveos.db"),
            "workspace_root": str(tmp_path / "runtime"),
            "projectctl_path": str(ctl),
            "seed_users": [
                {"username": "kuya", "os_user": "kuya", "role": "environment_admin"},
                {"username": "aris", "os_user": "aris", "role": "member"},
            ],
        }
    )
    return TestClient(app)


def login_headers(api: TestClient, username: str) -> dict[str, str]:
    res = api.post("/auth/login", json={"username": username, "password": "password123"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['token']}"}


def test_project_creator_sees_private_project_but_environment_admin_does_not_until_invited(tmp_path: Path):
    api = client(tmp_path)
    aris = login_headers(api, "aris")
    kuya = login_headers(api, "kuya")

    created = api.post("/api/projects", json={"slug": "deltapack", "name": "Deltapack"}, headers=aris)

    assert created.status_code == 201
    assert created.json()["slug"] == "deltapack"
    assert created.json()["owner"] == "aris"

    aris_projects = api.get("/api/projects", headers=aris)
    kuya_projects = api.get("/api/projects", headers=kuya)

    assert [p["slug"] for p in aris_projects.json()["projects"]] == ["deltapack"]
    assert kuya_projects.json()["projects"] == []

    invite = api.post("/api/projects/deltapack/invite", json={"username": "kuya"}, headers=aris)
    assert invite.status_code == 200

    kuya_projects = api.get("/api/projects", headers=kuya)
    assert [p["slug"] for p in kuya_projects.json()["projects"]] == ["deltapack"]

    remove = api.post("/api/projects/deltapack/remove", json={"username": "kuya"}, headers=aris)
    assert remove.status_code == 200

    kuya_projects = api.get("/api/projects", headers=kuya)
    assert kuya_projects.json()["projects"] == []


def test_non_member_cannot_read_project_detail(tmp_path: Path):
    api = client(tmp_path)
    aris = login_headers(api, "aris")
    kuya = login_headers(api, "kuya")

    api.post("/api/projects", json={"slug": "private-x", "name": "Private X"}, headers=aris)

    denied = api.get("/api/projects/private-x", headers=kuya)
    allowed = api.get("/api/projects/private-x", headers=aris)

    assert denied.status_code == 404
    assert allowed.status_code == 200
    assert allowed.json()["slug"] == "private-x"


def test_only_owner_can_invite_members(tmp_path: Path):
    api = client(tmp_path)
    aris = login_headers(api, "aris")
    kuya = login_headers(api, "kuya")

    api.post("/api/projects", json={"slug": "owned-by-aris", "name": "Owned"}, headers=aris)

    denied = api.post("/api/projects/owned-by-aris/invite", json={"username": "kuya"}, headers=kuya)

    assert denied.status_code == 404
