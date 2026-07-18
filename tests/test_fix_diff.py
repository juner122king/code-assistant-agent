"""unified diff 与 enrich/apply。"""

from pathlib import Path

import pytest

from app.fix.diffutil import make_unified_diff
from app.fix.service import apply_proposal, build_file_change, enrich_changes
from app.fix.store import FixStore
from app.models.requests import BugPayload
from app.repo.local_fs import LocalFsBackend

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_unified_diff_modify():
    diff = make_unified_diff("a.py", "hello\n", "hello\nworld\n")
    assert "a/a.py" in diff
    assert "b/a.py" in diff
    assert "+world" in diff


def test_unified_diff_create():
    diff = make_unified_diff("new.py", None, "x\n", action="create")
    assert "/dev/null" in diff
    assert "+x" in diff


def test_write_and_path_escape(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "f.txt").write_text("old", encoding="utf-8")
    backend = LocalFsBackend(root)
    backend.write_file("f.txt", "new")
    assert (root / "f.txt").read_text(encoding="utf-8") == "new"
    backend.write_file("sub/g.txt", "nested")
    assert (root / "sub" / "g.txt").read_text(encoding="utf-8") == "nested"
    with pytest.raises(PermissionError):
        backend.write_file("../outside.txt", "nope")


def test_enrich_and_apply(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    # 用 bytes 避免 Windows 文本模式把 \n 转成 \r\n
    (root / "app.py").write_bytes(b"print(1)\n")
    backend = LocalFsBackend(root)

    changes = enrich_changes(
        backend,
        [{"path": "app.py", "action": "modify", "proposed": "print(2)\n"}],
    )
    assert len(changes) == 1
    assert changes[0].original == "print(1)\n"
    assert "print(2)" in changes[0].unified_diff

    store = FixStore(ttl_seconds=60)
    item = store.create(
        repo=str(root),
        source="local",
        bug=BugPayload(title="x"),
        summary="bump",
        changes=changes,
    )
    result = apply_proposal(store, item.fix_id, backend)
    assert result.applied == ["app.py"]
    assert not result.conflicts
    assert (root / "app.py").read_bytes() == b"print(2)\n"

    # 重复 apply
    with pytest.raises(ValueError, match="already applied"):
        apply_proposal(store, item.fix_id, backend)


def test_conflict_detection(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_bytes(b"v1\n")
    backend = LocalFsBackend(root)
    ch = build_file_change("a.py", proposed="v2\n", original="v1\n")
    store = FixStore(ttl_seconds=60)
    item = store.create(
        repo=str(root),
        source="local",
        bug=BugPayload(title="c"),
        summary="s",
        changes=[ch],
    )
    # 磁盘被改
    (root / "a.py").write_bytes(b"v1-changed\n")
    result = apply_proposal(store, item.fix_id, backend, force=False)
    assert not result.applied
    assert result.conflicts
    # force 可写入
    result2 = apply_proposal(store, item.fix_id, backend, force=True)
    assert result2.applied == ["a.py"]


def test_sample_repo_readable():
    backend = LocalFsBackend(FIXTURE)
    r = backend.read_file("src/app.py")
    assert r.error is None
