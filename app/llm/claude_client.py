"""Anthropic Claude API 封装。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        if not self.settings.anthropic_api_key:
            logger.warning("ANTHROPIC_API_KEY 未设置，调用 Claude 会失败")
        self._client = Anthropic(api_key=self.settings.anthropic_api_key or "missing")
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
        logger.info("Claude request model=%s messages=%d tools=%d", self.model, len(messages), len(tools))
        return self._client.messages.create(**kwargs)
