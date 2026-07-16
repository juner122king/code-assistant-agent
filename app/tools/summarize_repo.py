"""get_repo_meta 工具。"""

from __future__ import annotations

from typing import Any, Dict

from app.repo.base import RepoBackend
from app.tools.registry import Tool


def handle(
    backend: RepoBackend,
    max_file_bytes: int = 30_000,
    max_tree_entries: int = 200,
    **_: Any,
) -> Dict[str, Any]:
    return backend.meta().to_dict()


TOOL = Tool(
    name="get_repo_meta",
    description=(
        "获取仓库元信息：来源(local/github)、标识、默认分支、描述、主语言、是否有 README 等。"
        "分析开始时建议先调用。"
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=handle,
)
