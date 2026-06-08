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


def _failing_ctl(tmp_path: Path) -> Path:
    """A projectctl that always fails — stands in for hiveosctl needing root."""
    script = tmp_path / "failing-ctl"
    script.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit('must run as root/sudo')\n", encoding="utf-8")
    script.chmod(0o755)
    return script


def test_project_create_works_without_privileged_helper(tmp_path: Path):
    # Default manage_os_acl=False (single-user $HOME install): creating a project
    # must NOT invoke the privileged hiveosctl helper. Point projectctl at a
    # script that always fails to prove it is never called.
    app = create_app({
        "database_path": str(tmp_path / "h.db"),
        "workspace_root": str(tmp_path / "rt"),
        "projectctl_path": str(_failing_ctl(tmp_path)),
        "seed_users": [{"username": "aris", "os_user": "aris", "role": "member"}],
    })
    api = TestClient(app)
    res = api.post("/api/projects", json={"slug": "freshproj", "name": "Fresh"}, headers=login_headers(api, "aris"))
    assert res.status_code == 201, res.text
    assert (tmp_path / "rt" / "projects" / "freshproj").is_dir()  # dir scaffolded on disk


def test_project_create_invokes_helper_when_manage_os_acl(tmp_path: Path):
    # The /srv multi-user deployment opts in: the helper IS invoked, so a failing
    # one surfaces as a 500 (proving the privileged path runs when enabled).
    app = create_app({
        "database_path": str(tmp_path / "h.db"),
        "workspace_root": str(tmp_path / "rt"),
        "projectctl_path": str(_failing_ctl(tmp_path)),
        "manage_os_acl": True,
        "seed_users": [{"username": "aris", "os_user": "aris", "role": "member"}],
    })
    api = TestClient(app)
    res = api.post("/api/projects", json={"slug": "freshproj", "name": "Fresh"}, headers=login_headers(api, "aris"))
    assert res.status_code == 500
    assert "root" in res.text.lower()


def test_invitable_lists_non_members_and_shrinks_after_invite(tmp_path: Path):
    api = client(tmp_path)
    aris = login_headers(api, "aris")
    api.post("/api/projects", json={"slug": "proj-x", "name": "Proj X"}, headers=aris)

    before = api.get("/api/projects/proj-x/invitable", headers=aris)
    assert before.status_code == 200
    assert "kuya" in before.json()["users"]      # registered, not yet a member
    assert "aris" not in before.json()["users"]   # owner is already a member

    api.post("/api/projects/proj-x/invite", json={"username": "kuya"}, headers=aris)
    after = api.get("/api/projects/proj-x/invitable", headers=aris).json()["users"]
    assert "kuya" not in after                      # now a member, no longer invitable


def test_invitable_is_owner_only(tmp_path: Path):
    api = client(tmp_path)
    aris = login_headers(api, "aris")
    kuya = login_headers(api, "kuya")
    api.post("/api/projects", json={"slug": "proj-y", "name": "Proj Y"}, headers=aris)
    # non-member (kuya) cannot enumerate invitable users
    assert api.get("/api/projects/proj-y/invitable", headers=kuya).status_code == 404


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
