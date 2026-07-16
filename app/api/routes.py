"""API 路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.agent.loop import AgentLoop
from app.config import get_settings
from app.models.requests import AnalyzeRequest
from app.models.responses import AnalyzeResponse
from app.repo.github_client import GitHubBackend
from app.repo.resolver import resolve_repo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """分析本地路径或 GitHub 仓库，返回结构 / 风险 / Bug。"""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=500,
            detail="未配置 ANTHROPIC_API_KEY，请复制 .env.example 为 .env 并填入密钥",
        )

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
