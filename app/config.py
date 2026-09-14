"""应用配置：从环境变量 / .env 加载。"""

from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple, Type

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# 固定项目根目录的 .env，避免工作目录变化读错文件
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 官方字段；中转站常用 ANTHROPIC_AUTH_TOKEN
    anthropic_api_key: str = ""
    anthropic_auth_token: str = ""
    # 自定义网关，如 https://newapi.example.com 或带 /v1
    anthropic_base_url: Optional[str] = None
    anthropic_model: str = "claude-sonnet-5"

    # OpenAI 兼容（硅基流动等）：LLM_PROVIDER=openai
    llm_provider: str = ""
    llm_base_url: Optional[str] = None
    llm_api_key: str = ""
    llm_model: str = ""
    # Qwen3 等默认可能开 thinking，Agent tool 循环应关掉
    llm_enable_thinking: bool = False
    # 中转站抖动：超时与重试
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3
    llm_retry_base_seconds: float = 1.5
    # False=直连中转，忽略系统代理/HTTP_PROXY（推荐；避免 Clash 劫持）
    llm_trust_env_proxy: bool = False

    github_token: str = ""

    agent_max_steps: int = 8
    agent_max_steps_cap: int = 40
    agent_max_file_bytes: int = 30_000
    agent_max_tree_entries: int = 200
    # 免费中转对大 max_tokens + 连发更敏感，默认 4096 更稳
    agent_max_tokens: int = 4096
    # 中间 tool 步的 max_tokens；收束/repair 仍用 agent_max_tokens
    agent_tool_max_tokens: int = 1024
    # 每步 LLM 调用间隔。None=按 provider：openai 0，anthropic 2.5
    llm_step_delay_seconds: Optional[float] = None

    # 分析记录
    analyze_history_max: int = 50

    # Fix / PR 流程
    fix_proposal_ttl_seconds: int = 1800
    fix_max_steps: int = 10
    fix_max_files: int = 8

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """优先项目 .env，再系统环境变量。

        本机若设置了全局 ANTHROPIC_BASE_URL（如其它 NewAPI），
        会覆盖 .env 导致分析连错中转站；学习项目以仓库 .env 为准。
        """
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    @model_validator(mode="after")
    def _merge_auth(self) -> "Settings":
        # 兼容 Claude Code 风格：ANTHROPIC_AUTH_TOKEN
        if not self.anthropic_api_key and self.anthropic_auth_token:
            self.anthropic_api_key = self.anthropic_auth_token
        if self.anthropic_base_url:
            self.anthropic_base_url = self.anthropic_base_url.rstrip("/")
        if self.llm_base_url:
            self.llm_base_url = self.llm_base_url.rstrip("/")
        return self

    @property
    def resolved_provider(self) -> str:
        p = (self.llm_provider or "").strip().lower()
        if p in ("openai", "siliconflow"):
            return "openai"
        if p in ("anthropic", "claude"):
            return "anthropic"
        if (self.llm_api_key or "").strip() or (self.llm_base_url or "").strip():
            return "openai"
        return "anthropic"

    @property
    def resolved_base_url(self) -> Optional[str]:
        if self.resolved_provider == "openai":
            url = (self.llm_base_url or "https://api.siliconflow.cn/v1").rstrip("/")
            if not url.endswith("/v1"):
                url = url + "/v1"
            return url
        return self.anthropic_base_url

    @property
    def resolved_model(self) -> str:
        if self.resolved_provider == "openai":
            return (self.llm_model or "").strip() or "Qwen/Qwen3-8B"
        return self.anthropic_model

    @property
    def resolved_api_key(self) -> str:
        if self.resolved_provider == "openai":
            return (self.llm_api_key or "").strip()
        return (self.anthropic_api_key or self.anthropic_auth_token or "").strip()

    @property
    def resolved_step_delay(self) -> float:
        if self.llm_step_delay_seconds is not None:
            return max(0.0, float(self.llm_step_delay_seconds))
        return 2.5 if self.resolved_provider == "anthropic" else 0.0

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.resolved_api_key)

    @property
    def has_anthropic_credentials(self) -> bool:
        return self.has_llm_credentials


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
