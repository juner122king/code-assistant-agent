"""进程内 FixProposal 存储（TTL）。"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.models.requests import BugPayload
from app.models.responses import FileChange, FixProposal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


@dataclass
class StoredFix:
    fix_id: str
    repo: str
    branch: Optional[str]
    source: str
    bug: BugPayload
    summary: str
    changes: list[FileChange]
    agent_steps: int = 0
    model: str = ""
    tool_calls: list[str] = field(default_factory=list)
    raw_summary: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    applied: bool = False
    pr_url: Optional[str] = None

    def is_expired(self, now: Optional[float] = None) -> bool:
        t = now if now is not None else time.time()
        return t >= self.expires_at

    def to_proposal(self) -> FixProposal:
        return FixProposal(
            fix_id=self.fix_id,
            repo=self.repo,
            source=self.source,  # type: ignore[arg-type]
            bug=self.bug,
            summary=self.summary,
            changes=self.changes,
            agent_steps=self.agent_steps,
            model=self.model,
            tool_calls=self.tool_calls,
            expires_at=_iso(datetime.fromtimestamp(self.expires_at, tz=timezone.utc)),
            applied=self.applied,
            raw_summary=self.raw_summary,
        )


class FixStore:
    def __init__(self, ttl_seconds: int = 1800):
        self.ttl_seconds = ttl_seconds
        self._items: Dict[str, StoredFix] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        repo: str,
        source: str,
        bug: BugPayload,
        summary: str,
        changes: list[FileChange],
        branch: Optional[str] = None,
        agent_steps: int = 0,
        model: str = "",
        tool_calls: Optional[list[str]] = None,
        raw_summary: Optional[str] = None,
        fix_id: Optional[str] = None,
    ) -> StoredFix:
        self.purge_expired()
        fid = fix_id or str(uuid.uuid4())
        now = time.time()
        item = StoredFix(
            fix_id=fid,
            repo=repo,
            branch=branch,
            source=source,
            bug=bug,
            summary=summary,
            changes=list(changes),
            agent_steps=agent_steps,
            model=model,
            tool_calls=list(tool_calls or []),
            raw_summary=raw_summary,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        with self._lock:
            self._items[fid] = item
        return item

    def get(self, fix_id: str) -> Optional[StoredFix]:
        with self._lock:
            item = self._items.get(fix_id)
            if item is None:
                return None
            if item.is_expired():
                del self._items[fix_id]
                return None
            return item

    def mark_applied(self, fix_id: str, *, pr_url: Optional[str] = None) -> StoredFix:
        with self._lock:
            item = self._items.get(fix_id)
            if item is None or item.is_expired():
                if item is not None:
                    del self._items[fix_id]
                raise KeyError(f"fix proposal not found or expired: {fix_id}")
            item.applied = True
            if pr_url:
                item.pr_url = pr_url
            return item

    def purge_expired(self) -> int:
        now = time.time()
        with self._lock:
            dead = [k for k, v in self._items.items() if v.is_expired(now)]
            for k in dead:
                del self._items[k]
            return len(dead)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_store: Optional[FixStore] = None
_store_lock = threading.Lock()


def get_fix_store(ttl_seconds: Optional[int] = None) -> FixStore:
    """进程级单例；测试可传入 ttl 并 clear。"""
    global _store
    with _store_lock:
        if _store is None:
            from app.config import get_settings

            ttl = ttl_seconds
            if ttl is None:
                ttl = get_settings().fix_proposal_ttl_seconds
            _store = FixStore(ttl_seconds=ttl)
        elif ttl_seconds is not None:
            _store.ttl_seconds = ttl_seconds
        return _store


def reset_fix_store() -> None:
    """测试用：重置单例。"""
    global _store
    with _store_lock:
        _store = None
