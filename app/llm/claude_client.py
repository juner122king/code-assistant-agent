"""Anthropic 兼容 API 封装（支持官方与中转 BASE_URL）。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from anthropic import APIConnectionError, APIStatusError, Anthropic, RateLimitError

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# 可重试的 HTTP 状态码（中转站上游抖动 / 限流）
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, RateLimitError, httpx.RequestError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return int(getattr(exc.response, "status_code", 0) or 0) in _RETRYABLE_STATUS
    if isinstance(exc, APIStatusError):
        return int(getattr(exc, "status_code", 0) or 0) in _RETRYABLE_STATUS
    text = str(exc).lower()
    for needle in (
        "502",
        "503",
        "504",
        "429",
        "连接上游",
        "rate limit",
        "timeout",
        "temporarily",
        "not available",
        "connection",
    ):
        if needle in text:
            return True
    return False


def _friendly_llm_error(exc: BaseException) -> str:
    """把中转站错误翻译成更可读的说明。"""
    status = getattr(exc, "status_code", None)
    body = ""
    try:
        resp = getattr(exc, "response", None)
        if status is None:
            status = getattr(resp, "status_code", None)
        if resp is not None and hasattr(resp, "text"):
            body = (resp.text or "")[:400]
    except Exception:
        body = ""
    msg = str(exc)
    combined = f"{msg}\n{body}"
    if (
        status == 429
        or "rate" in combined.lower()
        or "频率" in combined
        or "rate_limit" in combined.lower()
    ):
        return (
            "中转站上游请求频率受限（429）。"
            "本 Agent 会连续多轮 tool 调用，比「其它工具单次对话」更容易触发限流；"
            "请等待 30–60 秒后再分析，并避免同时用同一 token 跑其它客户端。"
            f" 原始: {msg}"
        )
    if status == 502 or "连接上游" in combined:
        return (
            "中转站返回 502「连接上游服务失败」。"
            "在本环境实测：单次/少轮请求通常成功，连续多轮分析更容易触发中转上游抖动或限流"
            "（其它工具单次调用正常不能证明连发也正常）。"
            "请间隔半分钟重试、降低最大步数，或暂时只在一个客户端使用该 token。"
            f" 原始: {msg}"
        )
    if status == 500 and "not available" in combined.lower():
        return (
            "中转站模型通道暂不可用（not available）。请稍后重试或更换模型。"
            f" 原始: {msg}"
        )
    return msg


class ClaudeClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        api_key = self.settings.anthropic_api_key or self.settings.anthropic_auth_token
        if not api_key:
            logger.warning("未设置 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN，调用会失败")

        timeout = float(getattr(self.settings, "llm_timeout_seconds", 120) or 120)
        # 默认不读系统代理 / HTTP_PROXY，避免 Clash 把私有中转绕飞
        trust_env = bool(getattr(self.settings, "llm_trust_env_proxy", False))
        self._http = httpx.Client(
            trust_env=trust_env,
            timeout=httpx.Timeout(timeout, connect=30.0),
        )
        client_kwargs: Dict[str, Any] = {
            "api_key": api_key or "missing",
            "timeout": timeout,
            "max_retries": 0,  # 自行控制重试
            "http_client": self._http,
        }
        if self.settings.anthropic_base_url:
            client_kwargs["base_url"] = self.settings.anthropic_base_url
            logger.info(
                "使用自定义 Anthropic BASE_URL: %s (trust_env_proxy=%s)",
                self.settings.anthropic_base_url,
                trust_env,
            )
        else:
            logger.info("使用官方 Anthropic API (trust_env_proxy=%s)", trust_env)

        if not trust_env:
            logger.info("LLM HTTP 直连：已禁用系统代理/环境变量代理")

        self._client = Anthropic(**client_kwargs)
        self.model = self.settings.anthropic_model
        self.max_attempts = int(getattr(self.settings, "llm_max_retries", 3) or 3)
        self.retry_base_seconds = float(
            getattr(self.settings, "llm_retry_base_seconds", 1.5) or 1.5
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

        last_exc: Optional[BaseException] = None
        attempts = max(1, self.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                t0 = time.time()
                result = self._client.messages.create(**kwargs)
                logger.info(
                    "LLM ok attempt=%d latency=%.0fms stop=%s",
                    attempt,
                    (time.time() - t0) * 1000,
                    getattr(result, "stop_reason", None),
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
                # 429/频率：长退避；502：中等退避
                delay = self.retry_base_seconds * (2 ** (attempt - 1))
                err_s = str(exc)
                if isinstance(exc, RateLimitError) or "429" in err_s or "频率" in err_s:
                    delay = max(delay, 8.0 * attempt)
                elif "502" in err_s or "连接上游" in err_s:
                    delay = max(delay, 4.0 * attempt)
                logger.info("LLM retry sleep %.1fs", delay)
                time.sleep(delay)

        assert last_exc is not None
        raise RuntimeError(_friendly_llm_error(last_exc)) from last_exc
