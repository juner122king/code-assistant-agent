"""Anthropic 兼容 API 封装（支持官方与中转 BASE_URL）。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        api_key = self.settings.anthropic_api_key or self.settings.anthropic_auth_token
        if not api_key:
            logger.warning("未设置 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN，调用会失败")

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key or "missing",
        }
        if self.settings.anthropic_base_url:
            client_kwargs["base_url"] = self.settings.anthropic_base_url
            logger.info("使用自定义 Anthropic BASE_URL: %s", self.settings.anthropic_base_url)

        self._client = Anthropic(**client_kwargs)
        self.model = self.settings.anthropic_model

    def create_message(
        self,
        *,
        messages: List[Dict[str, Any]],
        system: str,
        tools: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.settings.agent_max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        logger.info(
            "LLM request model=%s base_url=%s messages=%d tools=%d",
            self.model,
            self.settings.anthropic_base_url or "default(api.anthropic.com)",
            len(messages),
            len(tools),
        )
        return self._client.messages.create(**kwargs)
