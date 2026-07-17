"""FastAPI 入口。"""

from pathlib import Path

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

app = FastAPI(
    title="Code Assistant Agent",
    description=(
        "学习型代码仓库分析 Agent："
        "输入本地路径或 GitHub URL → 工具调用闭环 → 输出结构 / 风险 / Bug"
    ),
    version="0.1.0",
)
app.include_router(router)

_has_frontend = FRONTEND_DIST.is_dir() and FRONTEND_INDEX.is_file()

if _has_frontend:
    if FRONTEND_ASSETS.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(FRONTEND_ASSETS)),
            name="frontend-assets",
        )

    @app.get("/")
    def spa_index():
        return FileResponse(FRONTEND_INDEX)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        """非 API 路径：返回静态文件或 SPA index.html。

        API 路由（/health、/analyze）与 /docs 在 include_router 中优先注册。
        """
        candidate = (FRONTEND_DIST / full_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            return FileResponse(FRONTEND_INDEX)

        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_INDEX)

else:

    @app.get("/")
    def root():
        return {
            "name": "code-assistant-agent",
            "docs": "/docs",
            "health": "/health",
            "analyze": "POST /analyze",
            "hint": "前端未构建：cd frontend && npm install && npm run build",
        }
