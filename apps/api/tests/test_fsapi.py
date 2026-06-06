from __future__ import annotations

import pytest

from hive_os_api import fsapi


def _project(tmp_path):
    root = tmp_path / "proj"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("hello", encoding="utf-8")
    (root / "sub" / "b.md").write_text("# title", encoding="utf-8")
    return root


def test_resolve_in_project_rejects_traversal(tmp_path):
    root = _project(tmp_path)
    with pytest.raises(fsapi.FsError):
        fsapi.resolve_in_project(root, "../secret")
    with pytest.raises(fsapi.FsError):
        fsapi.resolve_in_project(root, "/etc/passwd")


def test_resolve_in_project_allows_inside(tmp_path):
    root = _project(tmp_path)
    assert fsapi.resolve_in_project(root, "sub/b.md") == (root / "sub" / "b.md").resolve()
    assert fsapi.resolve_in_project(root, "") == root.resolve()


def test_list_tree_returns_sorted_dirs_first(tmp_path):
    root = _project(tmp_path)
    entries = fsapi.list_tree(root, "")
    assert entries[0] == {"name": "sub", "type": "dir", "size": 0}
    assert {"name": "a.txt", "type": "file", "size": 5} in entries


def test_read_and_write_file(tmp_path):
    root = _project(tmp_path)
    assert fsapi.read_file(root, "a.txt") == "hello"
    fsapi.write_file(root, "sub/c.txt", "new content")
    assert (root / "sub" / "c.txt").read_text(encoding="utf-8") == "new content"


def test_read_file_rejects_too_large(tmp_path):
    root = _project(tmp_path)
    (root / "big.txt").write_text("x" * (fsapi.MAX_READ_BYTES + 1), encoding="utf-8")
    with pytest.raises(fsapi.FsError):
        fsapi.read_file(root, "big.txt")


def test_mkdir_rename_delete(tmp_path):
    root = _project(tmp_path)
    fsapi.mkdir(root, "newdir")
    assert (root / "newdir").is_dir()
    fsapi.rename(root, "a.txt", "renamed.txt")
    assert (root / "renamed.txt").exists() and not (root / "a.txt").exists()
    fsapi.delete(root, "renamed.txt")
    assert not (root / "renamed.txt").exists()
    fsapi.delete(root, "sub")
    assert not (root / "sub").exists()
