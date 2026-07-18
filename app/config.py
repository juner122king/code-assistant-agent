"""应用配置：从环境变量 / .env 加载。"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 官方字段；中转站常用 ANTHROPIC_AUTH_TOKEN
    anthropic_api_key: str = ""
    anthropic_auth_token: str = ""
    # 自定义网关，如 https://newapi.example.com 或带 /v1
    anthropic_base_url: Optional[str] = None
    anthropic_model: str = "claude-sonnet-5"

    github_token: str = ""

    agent_max_steps: int = 12
    agent_max_file_bytes: int = 30_000
    agent_max_tree_entries: int = 200
    agent_max_tokens: int = 8192

    # Fix / PR 流程
    fix_proposal_ttl_seconds: int = 1800
    fix_max_steps: int = 10
    fix_max_files: int = 8

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _merge_auth(self) -> "Settings":
        # 兼容 Claude Code 风格：ANTHROPIC_AUTH_TOKEN
        if not self.anthropic_api_key and self.anthropic_auth_token:
            self.anthropic_api_key = self.anthropic_auth_token
        if self.anthropic_base_url:
            self.anthropic_base_url = self.anthropic_base_url.rstrip("/")
        return self

    @property
    def has_anthropic_credentials(self) -> bool:
        return bool(self.anthropic_api_key or self.anthropic_auth_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
