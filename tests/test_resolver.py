"""resolver 单元测试。"""

from pathlib import Path

import pytest

from app.repo.github_client import parse_github_url
from app.repo.local_fs import LocalFsBackend
from app.repo.resolver import resolve_repo

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_parse_github_url():
    owner, repo = parse_github_url("https://github.com/anthropics/anthropic-sdk-python")
    assert owner == "anthropics"
    assert repo == "anthropic-sdk-python"

    owner, repo = parse_github_url("https://github.com/foo/bar.git")
    assert owner == "foo" and repo == "bar"


def test_resolve_local():
    backend, source = resolve_repo(str(FIXTURE))
    assert source == "local"
    assert isinstance(backend, LocalFsBackend)
    meta = backend.meta()
    assert meta.has_readme is True


def test_resolve_missing():
    with pytest.raises(FileNotFoundError):
        resolve_repo("/this/path/definitely/does/not/exist-xyz")
