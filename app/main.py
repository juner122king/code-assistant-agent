"""FastAPI 入口。"""

import logging

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Code Assistant Agent",
    description=(
        "学习型代码仓库分析 Agent："
        "输入本地路径或 GitHub URL → 工具调用闭环 → 输出结构 / 风险 / Bug"
    ),
    version="0.1.0",
)
app.include_router(router)


@app.get("/")
def root():
    return {
        "name": "code-assistant-agent",
        "docs": "/docs",
        "health": "/health",
        "analyze": "POST /analyze",
    }
