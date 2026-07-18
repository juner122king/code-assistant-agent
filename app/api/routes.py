"""API 路由。"""

from __future__ import annotations

import logging
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.fix_loop import FixAgentLoop
from app.agent.loop import AgentLoop
from app.config import get_settings
from app.fix.service import apply_proposal
from app.fix.store import get_fix_store
from app.models.events import format_sse
from app.models.requests import (
    AnalyzeRequest,
    FixApplyRequest,
    FixOpenPrRequest,
    FixProposeRequest,
)
from app.models.responses import (
    AnalyzeResponse,
    FixApplyResponse,
    FixOpenPrResponse,
    FixProposal,
)
from app.repo.github_client import GitHubBackend
from app.repo.local_fs import LocalFsBackend
from app.repo.resolver import resolve_repo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


def _ensure_credentials() -> None:
    settings = get_settings()
    if not settings.has_anthropic_credentials:
        raise HTTPException(
            status_code=500,
            detail=(
                "未配置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN；"
                "中转站请同时设置 ANTHROPIC_BASE_URL 与 ANTHROPIC_MODEL"
            ),
        )


def _sse_headers() -> dict:
    return {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """分析本地路径或 GitHub 仓库，返回结构 / 风险 / Bug。"""
    _ensure_credentials()
    settings = get_settings()

    backend = None
    try:
        backend, source = resolve_repo(body.repo, branch=body.branch, settings=settings)
        logger.info("resolved repo source=%s", source)
        agent = AgentLoop(backend, settings=settings)
        return agent.run(focus=body.focus)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analyze failed")
        raise HTTPException(status_code=502, detail=f"上游服务失败: {exc}") from exc
    finally:
        if isinstance(backend, GitHubBackend):
            backend.close()


@router.post("/analyze/stream")
def analyze_stream(body: AnalyzeRequest) -> StreamingResponse:
    """流式分析：SSE 推送过程事件，最后 event=done 携带完整报告。

    事件类型见 app.models.events 文档：start / step / tool / status / done / error。
    """
    _ensure_credentials()
    settings = get_settings()

    def event_gen() -> Iterator[str]:
        backend = None
        try:
            try:
                backend, source = resolve_repo(
                    body.repo, branch=body.branch, settings=settings
                )
            except FileNotFoundError as exc:
                yield format_sse("error", {"detail": str(exc), "status": 404})
                return
            except ValueError as exc:
                yield format_sse("error", {"detail": str(exc), "status": 400})
                return
            except PermissionError as exc:
                yield format_sse("error", {"detail": str(exc), "status": 403})
                return

            logger.info("stream resolved repo source=%s", source)
            yield format_sse(
                "status",
                {"message": f"仓库已解析（{source}），启动 Agent…"},
            )

            agent = AgentLoop(backend, settings=settings)
            for etype, data in agent.iter_run(focus=body.focus):
                if etype == "done":
                    payload = data.model_dump() if hasattr(data, "model_dump") else data
                    yield format_sse("done", payload)
                else:
                    yield format_sse(etype, data)
        except Exception as exc:
            logger.exception("analyze stream failed")
            yield format_sse("error", {"detail": f"上游服务失败: {exc}", "status": 502})
        finally:
            if isinstance(backend, GitHubBackend):
                backend.close()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


# ---------- Fix: propose → confirm → apply / open-pr ----------


@router.post("/fix/propose", response_model=FixProposal)
def fix_propose(body: FixProposeRequest) -> FixProposal:
    """为单条 Bug 生成修复提案（不落盘）。"""
    _ensure_credentials()
    settings = get_settings()
    backend = None
    try:
        backend, source = resolve_repo(body.repo, branch=body.branch, settings=settings)
        logger.info("fix propose source=%s bug=%s", source, body.bug.title)
        agent = FixAgentLoop(backend, settings=settings)
        return agent.run(body.bug, repo=body.repo, branch=body.branch)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("fix propose failed")
        raise HTTPException(status_code=502, detail=f"上游服务失败: {exc}") from exc
    finally:
        if isinstance(backend, GitHubBackend):
            backend.close()


@router.post("/fix/propose/stream")
def fix_propose_stream(body: FixProposeRequest) -> StreamingResponse:
    """流式生成修复提案；done 事件携带 FixProposal。"""
    _ensure_credentials()
    settings = get_settings()

    def event_gen() -> Iterator[str]:
        backend = None
        try:
            try:
                backend, source = resolve_repo(
                    body.repo, branch=body.branch, settings=settings
                )
            except FileNotFoundError as exc:
                yield format_sse("error", {"detail": str(exc), "status": 404})
                return
            except ValueError as exc:
                yield format_sse("error", {"detail": str(exc), "status": 400})
                return
            except PermissionError as exc:
                yield format_sse("error", {"detail": str(exc), "status": 403})
                return

            yield format_sse(
                "status",
                {"message": f"仓库已解析（{source}），启动修复 Agent…"},
            )
            agent = FixAgentLoop(backend, settings=settings)
            for etype, data in agent.iter_run(
                body.bug, repo=body.repo, branch=body.branch
            ):
                if etype == "done":
                    payload = data.model_dump() if hasattr(data, "model_dump") else data
                    yield format_sse("done", payload)
                else:
                    yield format_sse(etype, data)
        except Exception as exc:
            logger.exception("fix propose stream failed")
            yield format_sse("error", {"detail": f"上游服务失败: {exc}", "status": 502})
        finally:
            if isinstance(backend, GitHubBackend):
                backend.close()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=_sse_headers(),
    )


@router.get("/fix/{fix_id}", response_model=FixProposal)
def fix_get(fix_id: str) -> FixProposal:
    """查询未过期的修复提案。"""
    store = get_fix_store()
    item = store.get(fix_id)
    if item is None:
        raise HTTPException(status_code=404, detail="fix proposal not found or expired")
    return item.to_proposal()


@router.post("/fix/apply", response_model=FixApplyResponse)
def fix_apply(body: FixApplyRequest) -> FixApplyResponse:
    """确认后将提案写入本地文件系统。"""
    settings = get_settings()
    store = get_fix_store(settings.fix_proposal_ttl_seconds)
    item = store.get(body.fix_id)
    if item is None:
        raise HTTPException(status_code=404, detail="fix proposal not found or expired")
    if item.applied:
        raise HTTPException(status_code=409, detail="fix proposal already applied")
    if item.source != "local":
        raise HTTPException(
            status_code=400,
            detail="仅本地仓库支持应用到磁盘；GitHub 请使用 /fix/open-pr",
        )

    backend = None
    try:
        backend, _source = resolve_repo(item.repo, branch=item.branch, settings=settings)
        if not isinstance(backend, LocalFsBackend):
            raise HTTPException(status_code=400, detail="本地路径解析失败")
        return apply_proposal(
            store,
            body.fix_id,
            backend,
            paths=body.paths,
            force=body.force,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("fix apply failed")
        raise HTTPException(status_code=500, detail=f"应用失败: {exc}") from exc


@router.post("/fix/open-pr", response_model=FixOpenPrResponse)
def fix_open_pr(body: FixOpenPrRequest) -> FixOpenPrResponse:
    """确认后通过 GitHub API 建分支、提交并开 PR（无 clone）。"""
    settings = get_settings()
    if not settings.github_token:
        raise HTTPException(
            status_code=403,
            detail="未配置 GITHUB_TOKEN，无法创建分支/PR",
        )

    store = get_fix_store(settings.fix_proposal_ttl_seconds)
    item = store.get(body.fix_id)
    if item is None:
        raise HTTPException(status_code=404, detail="fix proposal not found or expired")
    if item.applied:
        raise HTTPException(status_code=409, detail="fix proposal already applied")
    if item.source != "github":
        raise HTTPException(
            status_code=400,
            detail="仅 GitHub 仓库支持开 PR；本地请使用 /fix/apply",
        )
    if not item.changes:
        raise HTTPException(status_code=400, detail="提案无文件变更，无法开 PR")

    backend = None
    try:
        backend, _source = resolve_repo(item.repo, branch=item.branch, settings=settings)
        if not isinstance(backend, GitHubBackend):
            raise HTTPException(status_code=400, detail="GitHub 仓库解析失败")

        pr_title = body.title or f"fix: {item.bug.title}"
        pr_body = body.body or _default_pr_body(item)
        result = backend.create_pull_request(
            changes=item.changes,
            title=pr_title,
            body=pr_body,
            branch_name=body.branch_name,
            base_branch=item.branch,
            commit_message=pr_title,
        )
        store.mark_applied(body.fix_id, pr_url=result.get("html_url"))
        return FixOpenPrResponse(
            fix_id=body.fix_id,
            pr_url=result["html_url"],
            branch=result["branch"],
            number=int(result["number"]),
            message="PR 已创建",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("fix open-pr failed")
        raise HTTPException(status_code=502, detail=f"创建 PR 失败: {exc}") from exc
    finally:
        if isinstance(backend, GitHubBackend):
            backend.close()


def _default_pr_body(item) -> str:
    bug = item.bug
    lines = [
        "## Summary",
        item.summary or "(no summary)",
        "",
        "## Bug",
        f"- **Title:** {bug.title}",
        f"- **Severity:** {bug.severity}",
        f"- **Location:** {bug.location or 'n/a'}",
        f"- **Evidence:** {bug.evidence or 'n/a'}",
        "",
        "## Files",
    ]
    for ch in item.changes:
        lines.append(f"- `{ch.path}` ({ch.action})")
    lines.extend(
        [
            "",
            "---",
            "_Generated by Code Assistant Agent_",
        ]
    )
    return "\n".join(lines)
