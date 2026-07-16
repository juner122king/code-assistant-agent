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
