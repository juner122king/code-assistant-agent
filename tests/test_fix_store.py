"""FixStore TTL 与 applied 标记。"""

import time

from app.fix.store import FixStore, reset_fix_store
from app.models.requests import BugPayload
from app.models.responses import FileChange


def setup_function():
    reset_fix_store()


def test_create_and_get():
    store = FixStore(ttl_seconds=60)
    bug = BugPayload(title="t", location="a.py")
    ch = FileChange(path="a.py", proposed="x", original="y", unified_diff="")
    item = store.create(
        repo="/tmp/r",
        source="local",
        bug=bug,
        summary="s",
        changes=[ch],
    )
    got = store.get(item.fix_id)
    assert got is not None
    assert got.summary == "s"
    prop = got.to_proposal()
    assert prop.fix_id == item.fix_id
    assert prop.expires_at


def test_expired():
    store = FixStore(ttl_seconds=1)
    item = store.create(
        repo="/tmp/r",
        source="local",
        bug=BugPayload(title="t"),
        summary="s",
        changes=[],
    )
    item.expires_at = time.time() - 1
    assert store.get(item.fix_id) is None


def test_mark_applied():
    store = FixStore(ttl_seconds=60)
    item = store.create(
        repo="/tmp/r",
        source="local",
        bug=BugPayload(title="t"),
        summary="s",
        changes=[],
    )
    store.mark_applied(item.fix_id)
    got = store.get(item.fix_id)
    assert got is not None
    assert got.applied is True
