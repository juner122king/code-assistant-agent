"""按配置选择 Anthropic 或 OpenAI 兼容客户端。"""

from __future__ import annotations

from typing import Optional, Union

from app.config import Settings, get_settings
from app.llm.claude_client import ClaudeClient
from app.llm.openai_client import OpenAIClient

LlmClient = Union[ClaudeClient, OpenAIClient]


def get_llm_client(settings: Optional[Settings] = None) -> LlmClient:
    settings = settings or get_settings()
    if settings.resolved_provider == "openai":
        return OpenAIClient(settings)
    return ClaudeClient(settings)
