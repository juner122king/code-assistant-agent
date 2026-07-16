"""解析用户输入的仓库标识，创建对应 Backend。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from app.config import Settings, get_settings
from app.repo.base import RepoBackend
from app.repo.github_client import GitHubBackend, parse_github_url
from app.repo.local_fs import LocalFsBackend


def is_github_url(value: str) -> bool:
    v = value.strip().lower()
    if "github.com/" in v:
        return True
    # owner/repo 简写（不含路径分隔过多）
    parts = value.strip("/").split("/")
    if len(parts) == 2 and not value.startswith(".") and not Path(value).exists():
        # 仅当不像本地路径时
        if not Path(value).is_absolute() and "\\" not in value:
            # 仍优先本地：若相对路径存在则本地
            return True
    return False


def resolve_repo(
    repo: str,
    branch: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> Tuple[RepoBackend, str]:
    """
    返回 (backend, source)。

    source: 'local' | 'github'
    """
    settings = settings or get_settings()
    raw = repo.strip()

    # 1) 明确 GitHub URL
    if "github.com/" in raw.lower():
        owner, name = parse_github_url(raw)
        backend = GitHubBackend(
            owner=owner,
            repo=name,
            token=settings.github_token,
            branch=branch,
        )
        return backend, "github"

    # 2) 本地路径（存在则优先）
    path = Path(raw).expanduser()
    if path.exists():
        return LocalFsBackend(path), "local"

    # 3) owner/repo 简写
    if raw.count("/") == 1 and not raw.startswith("."):
        try:
            owner, name = parse_github_url(raw)
            backend = GitHubBackend(
                owner=owner,
                repo=name,
                token=settings.github_token,
                branch=branch,
            )
            return backend, "github"
        except ValueError:
            pass

    raise FileNotFoundError(
        f"无法解析仓库: {repo}（本地路径不存在，且不是有效 GitHub URL）"
    )
