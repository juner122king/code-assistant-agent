"""仓库后端抽象与公共类型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RepoMeta:
    source: str  # local | github
    identifier: str  # 路径或 owner/repo
    default_branch: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    has_readme: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "identifier": self.identifier,
            "default_branch": self.default_branch,
            "description": self.description,
            "language": self.language,
            "has_readme": self.has_readme,
            **self.extra,
        }


@dataclass
class FileReadResult:
    path: str
    content: str
    truncated: bool = False
    size_bytes: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "truncated": self.truncated,
            "size_bytes": self.size_bytes,
            "error": self.error,
        }


class RepoBackend(ABC):
    """统一仓库访问接口：Local 与 GitHub 实现同一套方法。"""

    @abstractmethod
    def meta(self) -> RepoMeta:
        ...

    @abstractmethod
    def list_tree(
        self,
        path: str = "",
        max_depth: int = 3,
        max_entries: int = 200,
    ) -> List[str]:
        """返回相对路径列表（目录以 / 结尾）。"""
        ...

    @abstractmethod
    def read_file(self, path: str, max_bytes: int = 30_000) -> FileReadResult:
        ...

    @abstractmethod
    def search(self, pattern: str, max_hits: int = 20) -> List[str]:
        """按路径/文件名子串匹配（轻量）。"""
        ...
