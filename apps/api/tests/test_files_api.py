from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hive_os_api.main import create_app


def client(tmp_path: Path) -> TestClient:
    app = create_app({
        "database_path": str(tmp_path / "hive.db"),
        "workspace_root": str(tmp_path / "ws"),
        "projectctl_path": "/usr/bin/true",
        "start_worker": False,
    })
    return TestClient(app)


def setup_project(c: TestClient, tmp_path: Path) -> dict:
    token = c.post("/api/setup/bootstrap", json={"username": "kuya", "password": "password123", "profile_name": "Default", "profile_slug": "default"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = c.post("/api/projects", headers=headers, json={"slug": "demo", "name": "Demo"}).json()
    # projectctl is /usr/bin/true so create the dir ourselves to mirror real behavior
    Path(proj["path"]).mkdir(parents=True, exist_ok=True)
    return headers


def test_tree_read_write_mkdir_rename_delete(tmp_path):
    c = client(tmp_path)
    headers = setup_project(c, tmp_path)

    assert c.put("/api/projects/demo/file?path=notes/a.txt", headers=headers, json={"content": "hello"}).status_code == 200
    tree = c.get("/api/projects/demo/tree?path=notes", headers=headers).json()["entries"]
    assert {"name": "a.txt", "type": "file", "size": 5} in tree

    body = c.get("/api/projects/demo/file?path=notes/a.txt", headers=headers).json()
    assert body["content"] == "hello"

    assert c.post("/api/projects/demo/fs/mkdir", headers=headers, json={"path": "newdir"}).status_code == 200
    assert c.post("/api/projects/demo/fs/rename", headers=headers, json={"from": "notes/a.txt", "to": "notes/b.txt"}).status_code == 200
    assert c.delete("/api/projects/demo/fs?path=notes/b.txt", headers=headers).status_code == 200


def test_traversal_is_rejected(tmp_path):
    c = client(tmp_path)
    headers = setup_project(c, tmp_path)
    assert c.get("/api/projects/demo/tree?path=../..", headers=headers).status_code == 400


def test_read_missing_file_returns_400(tmp_path):
    c = client(tmp_path)
    headers = setup_project(c, tmp_path)
    assert c.get("/api/projects/demo/file?path=does-not-exist", headers=headers).status_code == 400


def test_non_member_cannot_access(tmp_path):
    c = client(tmp_path)
    headers = setup_project(c, tmp_path)
    # create a second user via admin and log in as them
    c.post("/api/users", headers=headers, json={"username": "aris", "password": "password123", "role": "member", "profile_name": "Default", "profile_slug": "default"})
    other = c.post("/auth/login", json={"username": "aris", "password": "password123"}).json()["token"]
    oh = {"Authorization": f"Bearer {other}"}
    assert c.get("/api/projects/demo/tree", headers=oh).status_code == 404
