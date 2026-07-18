"""API 路由。"""

from __future__ import annotations

import logging
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.loop import AgentLoop
from app.config import get_settings
from app.models.events import format_sse
from app.models.requests import AnalyzeRequest
from app.models.responses import AnalyzeResponse
from app.repo.github_client import GitHubBackend
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
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
