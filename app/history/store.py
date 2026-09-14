"""分析记录：过程事件 + 报告。内存为主，落盘以便重启后仍可回看。"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PATH = _PROJECT_ROOT / "data" / "analyze_runs.json"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compact_event_data(etype: str, data: Any) -> Any:
    if etype != "done" or not isinstance(data, dict):
        return data
    return {
        "agent_steps": data.get("agent_steps"),
        "model": data.get("model"),
        "repo": data.get("repo"),
        "source": data.get("source"),
        "tool_calls": data.get("tool_calls") or [],
        "risks": len(data.get("risks") or []),
        "bugs": len(data.get("bugs") or []),
    }


def run_summary(run: Dict[str, Any]) -> Dict[str, Any]:
    report = run.get("report") or {}
    risks = report.get("risks") if isinstance(report, dict) else None
    bugs = report.get("bugs") if isinstance(report, dict) else None
    created = int(run.get("created_at") or 0)
    finished = int(run.get("finished_at") or 0)
    duration_ms = (finished - created) if finished and created else None
    repo = str(run.get("repo") or "")
    short = repo.replace("\\", "/").rstrip("/")
    if "/" in short:
        short = short.rsplit("/", 1)[-1]
    return {
        "id": run.get("id"),
        "status": run.get("status"),
        "repo": repo,
        "repo_short": short or repo,
        "branch": run.get("branch"),
        "focus": run.get("focus") or "general",
        "source": run.get("source") or "",
        "model": run.get("model") or "",
        "max_steps": run.get("max_steps"),
        "agent_steps": (report.get("agent_steps") if isinstance(report, dict) else None)
        or run.get("agent_steps")
        or 0,
        "event_count": len(run.get("events") or []),
        "risk_count": len(risks or []),
        "bug_count": len(bugs or []),
        "created_at": created,
        "finished_at": finished or None,
        "duration_ms": duration_ms,
        "error": run.get("error"),
    }


class AnalysisStore:
    def __init__(self, path: Optional[Path] = None, max_runs: int = 50):
        self.path = Path(path) if path else _DEFAULT_PATH
        self.max_runs = max(1, int(max_runs))
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()
        self._mtime = 0.0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._runs = {}
            self._order = []
            self._mtime = 0.0
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("failed to load analysis history %s: %s", self.path, exc)
            return
        runs = raw.get("runs") if isinstance(raw, dict) else raw
        if not isinstance(runs, list):
            return
        self._runs = {}
        self._order = []
        for item in runs:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            rid = str(item["id"])
            self._runs[rid] = item
            self._order.append(rid)
        try:
            self._mtime = self.path.stat().st_mtime
        except OSError:
            self._mtime = 0.0

    def _reload_if_stale(self) -> None:
        if not self.path.exists():
            return
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return
        if mtime > self._mtime:
            self._load()

    def _save_unlocked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"runs": [self._runs[i] for i in self._order if i in self._runs]}
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)
        try:
            self._mtime = self.path.stat().st_mtime
        except OSError:
            pass

    def _trim_unlocked(self) -> None:
        while len(self._order) > self.max_runs:
            old = self._order.pop()
            self._runs.pop(old, None)

    def begin(
        self,
        *,
        repo: str,
        branch: Optional[str] = None,
        focus: str = "general",
        max_steps: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        rid = run_id or uuid.uuid4().hex[:12]
        run = {
            "id": rid,
            "status": "running",
            "repo": repo,
            "branch": branch,
            "focus": focus,
            "max_steps": max_steps,
            "source": "",
            "model": "",
            "created_at": _now_ms(),
            "finished_at": None,
            "events": [],
            "report": None,
            "error": None,
        }
        with self._lock:
            self._reload_if_stale()
            self._runs[rid] = run
            self._order.insert(0, rid)
            self._trim_unlocked()
            self._save_unlocked()
        return run

    def append_event(self, run_id: str, etype: str, data: Any) -> None:
        event = {
            "type": etype,
            "data": _compact_event_data(etype, data),
            "at": _now_ms(),
        }
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.setdefault("events", []).append(event)
            if etype == "start" and isinstance(data, dict):
                if data.get("source"):
                    run["source"] = data["source"]
                if data.get("model"):
                    run["model"] = data["model"]
                if data.get("max_steps") is not None:
                    run["max_steps"] = data["max_steps"]
                if data.get("repo"):
                    run["repo"] = data["repo"]
            self._save_unlocked()

    def finish(
        self,
        run_id: str,
        *,
        report: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            run["finished_at"] = _now_ms()
            if error:
                run["status"] = "error"
                run["error"] = error
            else:
                run["status"] = "done"
                run["error"] = None
            if report is not None:
                run["report"] = report
                run["source"] = report.get("source") or run.get("source") or ""
                run["model"] = report.get("model") or run.get("model") or ""
                run["agent_steps"] = report.get("agent_steps") or 0
            self._save_unlocked()
            return run

    def list_runs(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._reload_if_stale()
            return [run_summary(self._runs[i]) for i in self._order if i in self._runs]

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._reload_if_stale()
            run = self._runs.get(run_id)
            if run is None:
                return None
            return json.loads(json.dumps(run))

    def delete(self, run_id: str) -> bool:
        with self._lock:
            self._reload_if_stale()
            if run_id not in self._runs:
                return False
            self._runs.pop(run_id, None)
            self._order = [i for i in self._order if i != run_id]
            self._save_unlocked()
            return True

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()
            self._order.clear()
            self._save_unlocked()


_store: Optional[AnalysisStore] = None
_store_lock = threading.Lock()


def get_analysis_store() -> AnalysisStore:
    global _store
    with _store_lock:
        if _store is None:
            from app.config import get_settings

            settings = get_settings()
            max_runs = int(getattr(settings, "analyze_history_max", 50) or 50)
            _store = AnalysisStore(max_runs=max_runs)
        return _store


def reset_analysis_store() -> None:
    global _store
    with _store_lock:
        _store = None
