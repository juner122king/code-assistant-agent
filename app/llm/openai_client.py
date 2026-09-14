"""OpenAI 兼容 Chat Completions 客户端（硅基流动等）。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings, get_settings
from app.llm.claude_client import _friendly_llm_error, _is_retryable
from app.llm.openai_compat import (
    anthropic_messages_to_openai,
    anthropic_tools_to_openai,
    openai_response_to_anthropic,
)

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        api_key = self.settings.resolved_api_key
        if not api_key:
            logger.warning("未设置 LLM_API_KEY，调用会失败")

        timeout = float(getattr(self.settings, "llm_timeout_seconds", 120) or 120)
        trust_env = bool(getattr(self.settings, "llm_trust_env_proxy", False))
        self._http = httpx.Client(
            trust_env=trust_env,
            timeout=httpx.Timeout(timeout, connect=30.0),
        )
        self.model = self.settings.resolved_model
        self.base_url = (self.settings.resolved_base_url or "").rstrip("/")
        self._api_key = api_key or "missing"
        self.max_attempts = int(getattr(self.settings, "llm_max_retries", 3) or 3)
        self.retry_base_seconds = float(
            getattr(self.settings, "llm_retry_base_seconds", 1.5) or 1.5
        )
        logger.info(
            "使用 OpenAI 兼容 BASE_URL: %s model=%s (trust_env_proxy=%s)",
            self.base_url,
            self.model,
            trust_env,
        )

    def create_message(
        self,
        *,
        messages: List[Dict[str, Any]],
        system: str,
        tools: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        tool_choice: Optional[str] = None,
    ) -> Any:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages_to_openai(messages, system),
            "max_tokens": max_tokens or self.settings.agent_max_tokens,
        }
        if tools:
            payload["tools"] = anthropic_tools_to_openai(tools)
            payload["tool_choice"] = tool_choice or "auto"
        payload["enable_thinking"] = bool(self.settings.llm_enable_thinking)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        logger.info(
            "LLM request provider=openai model=%s base_url=%s messages=%d tools=%d",
            self.model,
            self.base_url,
            len(payload["messages"]),
            len(tools or []),
        )

        last_exc: Optional[BaseException] = None
        attempts = max(1, self.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                t0 = time.time()
                resp = self._http.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code} {resp.text[:400]}",
                        request=resp.request,
                        response=resp,
                    )
                data = resp.json()
                result = openai_response_to_anthropic(data)
                logger.info(
                    "LLM ok attempt=%d latency=%.0fms stop=%s",
                    attempt,
                    (time.time() - t0) * 1000,
                    result.stop_reason,
                )
                return result
            except Exception as exc:
                last_exc = exc
                retryable = _is_retryable(exc)
                logger.warning(
                    "LLM call failed attempt=%d/%d retryable=%s err=%s",
                    attempt,
                    attempts,
                    retryable,
                    exc,
                )
                if not retryable or attempt >= attempts:
                    break
                delay = self.retry_base_seconds * (2 ** (attempt - 1))
                err_s = str(exc)
                if "429" in err_s or "频率" in err_s:
                    delay = max(delay, 8.0 * attempt)
                elif "502" in err_s or "连接上游" in err_s:
                    delay = max(delay, 4.0 * attempt)
                logger.info("LLM retry sleep %.1fs", delay)
                time.sleep(delay)

        assert last_exc is not None
        raise RuntimeError(_friendly_llm_error(last_exc)) from last_exc
