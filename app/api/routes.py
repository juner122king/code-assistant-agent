"""API 路由。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.fix_loop import FixAgentLoop
from app.agent.loop import AgentLoop
from app.config import get_settings
from app.fix.service import apply_proposal
from app.fix.store import get_fix_store
from app.history.store import get_analysis_store, run_summary
from app.llm.catalog import catalog_payload
from app.models.events import format_sse
from app.models.history import AnalysisRunDetail, AnalysisRunList, AnalysisRunSummary
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
from app.repo.local_fs import LocalFsBackend, detect_git_branch, list_git_branches
from app.repo.resolver import resolve_repo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/repo/branch")
def repo_branch(repo: str) -> dict:
    """自动检测本地目录的当前 git 分支与所有可用分支列表。非 git 目录或远端返回 is_git=False, branch=None, branches=[]。"""
    raw = (repo or "").strip()
    if not raw:
        return {"is_git": False, "branch": None, "branches": []}

    # 排除显式的 GitHub 仓库或简写
    if "github.com/" in raw.lower() or (
        raw.count("/") == 1 and not raw.startswith(".") and not Path(raw).exists()
    ):
        return {"is_git": False, "branch": None, "branches": []}

    try:
        path = Path(raw).expanduser()
        if not path.exists() or not path.is_dir():
            return {"is_git": False, "branch": None, "branches": []}
        curr_branch, branches = list_git_branches(path)
        if curr_branch or branches:
            return {"is_git": True, "branch": curr_branch, "branches": branches}
    except Exception:
        pass

    return {"is_git": False, "branch": None, "branches": []}


@router.get("/health")
def health():
    """健康检查；附带当前 LLM 配置摘要（不含密钥），便于排查连错中转站。"""
    settings = get_settings()
    token = settings.resolved_api_key or ""
    if settings.resolved_provider == "openai":
        default_url = "https://api.siliconflow.cn/v1"
    else:
        default_url = "https://api.anthropic.com"
    return {
        "status": "ok",
        "llm": {
            "provider": settings.resolved_provider,
            "base_url": settings.resolved_base_url or default_url,
            "model": settings.resolved_model,
            "has_credentials": settings.has_llm_credentials,
            "token_prefix": (token[:8] + "…") if token else "",
            "max_steps_default": settings.agent_max_steps,
            "max_steps_cap": settings.agent_max_steps_cap,
            "trust_env_proxy": settings.llm_trust_env_proxy,
            "direct_connect": not settings.llm_trust_env_proxy,
            "enable_thinking": settings.llm_enable_thinking,
            "step_delay_seconds": settings.resolved_step_delay,
        },
    }


def _ensure_credentials() -> None:
    settings = get_settings()
    if not settings.has_llm_credentials:
        raise HTTPException(
            status_code=500,
            detail=(
                "未配置 LLM 凭证。"
                "OpenAI 兼容（硅基流动）请设置 LLM_PROVIDER=openai、LLM_API_KEY、LLM_MODEL；"
                "Anthropic 中转请设置 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN，以及 BASE_URL / MODEL"
            ),
        )


def _sse_headers() -> dict:
    return {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def _apply_request_model(agent: AgentLoop, model: Optional[str]) -> None:
    name = (model or "").strip()
    if name:
        agent.claude.model = name


def _dump_report(data: Any) -> Dict[str, Any]:
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if isinstance(data, dict):
        return data
    return {}


@router.get("/analyze/models")
def analyze_models() -> dict:
    """适合本 Agent 的模型目录（含免费/付费与性价比说明）。"""
    return catalog_payload()


@router.get("/analyze/runs", response_model=AnalysisRunList)
def analyze_runs() -> AnalysisRunList:
    """分析记录列表（新的在前）。"""
    items = get_analysis_store().list_runs()
    return AnalysisRunList(runs=[AnalysisRunSummary.model_validate(x) for x in items])


@router.get("/analyze/runs/{run_id}", response_model=AnalysisRunDetail)
def analyze_run_detail(run_id: str) -> AnalysisRunDetail:
    """单条分析记录：过程事件 + 报告。"""
    run = get_analysis_store().get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="analysis run not found")
    summary = run_summary(run)
    report = run.get("report")
    return AnalysisRunDetail.model_validate(
        {
            **summary,
            "events": run.get("events") or [],
            "report": report,
        }
    )


@router.delete("/analyze/runs/{run_id}")
def analyze_run_delete(run_id: str) -> dict:
    ok = get_analysis_store().delete(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="analysis run not found")
    return {"ok": True, "id": run_id}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """分析本地路径或 GitHub 仓库，返回结构 / 风险 / Bug。"""
    _ensure_credentials()
    settings = get_settings()
    store = get_analysis_store()
    run = store.begin(
        repo=body.repo,
        branch=body.branch,
        focus=body.focus,
        max_steps=body.max_steps,
    )

    backend = None
    try:
        backend, source = resolve_repo(body.repo, branch=body.branch, settings=settings)
        logger.info("resolved repo source=%s", source)
        agent = AgentLoop(backend, settings=settings)
        _apply_request_model(agent, body.model)
        result = agent.run(focus=body.focus, max_steps=body.max_steps)
        payload = result.model_dump()
        store.append_event(run["id"], "done", payload)
        store.finish(run["id"], report=payload)
        return result
    except FileNotFoundError as exc:
        store.finish(run["id"], error=str(exc))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        store.finish(run["id"], error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        store.finish(run["id"], error=str(exc))
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analyze failed")
        store.finish(run["id"], error=str(exc))
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
        store = None
        run_id = None
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
            store = get_analysis_store()
            run = store.begin(
                repo=body.repo,
                branch=body.branch,
                focus=body.focus,
                max_steps=body.max_steps,
            )
            run_id = run["id"]
            status_payload = {
                "message": f"仓库已解析（{source}），启动 Agent…",
                "run_id": run_id,
            }
            store.append_event(run_id, "status", status_payload)
            yield format_sse("status", status_payload)

            agent = AgentLoop(backend, settings=settings)
            _apply_request_model(agent, body.model)
            for etype, data in agent.iter_run(
                focus=body.focus, max_steps=body.max_steps
            ):
                if etype == "done":
                    payload = _dump_report(data)
                    payload["run_id"] = run_id
                    store.append_event(run_id, "done", payload)
                    store.finish(run_id, report=payload)
                    yield format_sse("done", payload)
                else:
                    payload = data if isinstance(data, dict) else {"value": data}
                    if etype == "start":
                        payload = dict(payload)
                        payload["run_id"] = run_id
                    store.append_event(run_id, etype, payload)
                    yield format_sse(etype, payload)
        except Exception as exc:
            logger.exception("analyze stream failed")
            detail = f"上游服务失败: {exc}"
            if store is not None and run_id:
                try:
                    store.append_event(
                        run_id, "error", {"detail": detail, "status": 502}
                    )
                    store.finish(run_id, error=detail)
                except Exception:
                    pass
            yield format_sse("error", {"detail": detail, "status": 502})
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
