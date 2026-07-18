"""修复提案构建与本地应用。"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from app.fix.diffutil import make_unified_diff
from app.fix.store import FixStore, StoredFix
from app.models.responses import FileChange, FixApplyResponse
from app.repo.base import RepoBackend

logger = logging.getLogger(__name__)


def build_file_change(
    path: str,
    *,
    proposed: str = "",
    original: Optional[str] = None,
    action: str = "modify",
) -> FileChange:
    if action not in ("modify", "create", "delete"):
        action = "modify"
    diff = make_unified_diff(path, original, proposed, action=action)
    return FileChange(
        path=path,
        action=action,  # type: ignore[arg-type]
        original=original,
        proposed=proposed if action != "delete" else "",
        unified_diff=diff,
    )


def enrich_changes(
    backend: RepoBackend,
    raw_changes: Sequence[dict],
    *,
    max_files: int = 8,
    max_file_bytes: int = 30_000,
) -> List[FileChange]:
    """根据模型输出的 path/proposed/action，回读 original 并生成 diff。"""
    result: List[FileChange] = []
    for item in raw_changes:
        if len(result) >= max_files:
            break
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip().lstrip("/").replace("\\", "/")
        if not path or ".." in path.split("/"):
            continue
        action = str(item.get("action") or "modify").lower()
        if action not in ("modify", "create", "delete"):
            action = "modify"
        proposed = str(item.get("proposed") or "")
        if len(proposed.encode("utf-8", errors="replace")) > max_file_bytes * 2:
            logger.warning("skip oversized proposed file: %s", path)
            continue

        original: Optional[str] = None
        if action != "create":
            read = backend.read_file(path, max_bytes=max_file_bytes * 2)
            if read.error and action == "modify":
                # 文件不存在时当作 create
                if "not found" in (read.error or "").lower():
                    action = "create"
                    original = None
                else:
                    logger.warning("skip %s: %s", path, read.error)
                    continue
            elif not read.error:
                original = read.content
                if read.truncated:
                    logger.warning("original truncated for %s, conflict check may be weak", path)

        if action == "delete":
            proposed = ""
        elif action == "modify" and original is not None and proposed == original:
            continue
        elif action == "create" and not proposed:
            continue

        result.append(
            build_file_change(
                path,
                proposed=proposed,
                original=original,
                action=action,
            )
        )
    return result


def apply_proposal(
    store: FixStore,
    fix_id: str,
    backend: RepoBackend,
    *,
    paths: Optional[List[str]] = None,
    force: bool = False,
) -> FixApplyResponse:
    """将已确认的提案写入 backend（通常是 LocalFsBackend）。"""
    item = store.get(fix_id)
    if item is None:
        raise KeyError(f"fix proposal not found or expired: {fix_id}")
    if item.applied:
        raise ValueError(f"fix proposal already applied: {fix_id}")
    if item.source != "local":
        raise ValueError("仅本地仓库支持 /fix/apply；GitHub 请使用 /fix/open-pr")

    path_filter = None
    if paths:
        path_filter = {p.strip().lstrip("/").replace("\\", "/") for p in paths if p}

    applied: List[str] = []
    skipped: List[str] = []
    conflicts: List[str] = []

    for change in item.changes:
        rel = change.path.strip().lstrip("/").replace("\\", "/")
        if path_filter is not None and rel not in path_filter:
            skipped.append(rel)
            continue

        try:
            if not force and change.action != "create" and change.original is not None:
                current = backend.read_file(rel, max_bytes=max(len(change.original) * 2, 30_000) + 1000)
                if current.error and "not found" not in (current.error or "").lower():
                    conflicts.append(f"{rel}: read error {current.error}")
                    continue
                disk = "" if current.error else current.content
                if disk != change.original:
                    conflicts.append(f"{rel}: file changed since proposal")
                    continue

            if change.action == "delete":
                backend.delete_file(rel)
            else:
                backend.write_file(rel, change.proposed or "")
            applied.append(rel)
        except PermissionError as exc:
            conflicts.append(f"{rel}: {exc}")
        except Exception as exc:
            logger.exception("apply failed for %s", rel)
            conflicts.append(f"{rel}: {exc}")

    if applied and not conflicts:
        store.mark_applied(fix_id)
        message = f"已应用 {len(applied)} 个文件"
    elif applied and conflicts:
        # 部分成功：仍标记 applied，避免重复写入已改文件；也可不标记
        store.mark_applied(fix_id)
        message = f"部分应用：成功 {len(applied)}，冲突/失败 {len(conflicts)}"
    elif conflicts:
        message = "未写入任何文件：存在冲突或错误"
    else:
        message = "没有可应用的文件"

    return FixApplyResponse(
        fix_id=fix_id,
        applied=applied,
        skipped=skipped,
        conflicts=conflicts,
        message=message,
    )


def require_stored(store: FixStore, fix_id: str) -> StoredFix:
    item = store.get(fix_id)
    if item is None:
        raise KeyError(f"fix proposal not found or expired: {fix_id}")
    return item
