"""本地文件系统后端测试。"""

from pathlib import Path

import pytest

from app.repo.local_fs import LocalFsBackend

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_list_tree_and_readme():
    backend = LocalFsBackend(FIXTURE)
    entries = backend.list_tree(max_depth=3)
    joined = "\n".join(entries)
    assert "README.md" in joined
    assert "src/" in joined or "src/app.py" in joined


def test_read_file():
    backend = LocalFsBackend(FIXTURE)
    result = backend.read_file("src/app.py")
    assert result.error is None
    assert "API_KEY" in result.content


def test_path_escape_blocked():
    backend = LocalFsBackend(FIXTURE)
    with pytest.raises(PermissionError):
        backend._safe_join("../outside")


def test_search():
    backend = LocalFsBackend(FIXTURE)
    hits = backend.search("app.py")
    assert any("app.py" in h for h in hits)


def test_detect_git_branch():
    from app.repo.local_fs import detect_git_branch, list_git_branches

    # Current repo is a git repository
    current_root = Path(__file__).resolve().parent.parent
    branch = detect_git_branch(current_root)
    assert branch is not None
    assert branch == "main" or len(branch) > 0

    curr, branches = list_git_branches(current_root)
    assert curr == branch
    assert isinstance(branches, list)
    assert branch in branches

    # FIXTURE does not have .git directory, should return None
    assert detect_git_branch(FIXTURE) is None
    assert list_git_branches(FIXTURE) == (None, [])


def test_repo_branch_api():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. current repo ./
    res = client.get("/repo/branch", params={"repo": "./"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_git"] is True
    assert data["branch"] is not None
    assert isinstance(data["branches"], list)
    assert data["branch"] in data["branches"]

    # 2. non-git directory fixture
    res = client.get("/repo/branch", params={"repo": str(FIXTURE)})
    assert res.status_code == 200
    data = res.json()
    assert data["is_git"] is False
    assert data["branch"] is None
    assert data["branches"] == []

    # 3. remote github url
    res = client.get(
        "/repo/branch", params={"repo": "https://github.com/fastapi/fastapi"}
    )
    assert res.status_code == 200
    assert res.json()["is_git"] is False
    assert res.json()["branches"] == []
