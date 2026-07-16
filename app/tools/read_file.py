"""read_file 工具。"""

from __future__ import annotations

from typing import Any, Dict

from app.repo.base import RepoBackend
from app.tools.registry import Tool


def handle(
    backend: RepoBackend,
    path: str = "",
    max_file_bytes: int = 30_000,
    max_tree_entries: int = 200,
    **_: Any,
) -> Dict[str, Any]:
    if not path:
        return {"error": "path is required"}
    result = backend.read_file(path, max_bytes=int(max_file_bytes))
    return result.to_dict()


TOOL = Tool(
    name="read_file",
    description=(
        "读取仓库中某个文本文件的内容。用于查看 README、配置、源码。"
        "大文件会被截断并标记 truncated=true。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "相对仓库根的文件路径，例如 README.md 或 src/app.py",
            },
        },
        "required": ["path"],
    },
    handler=handle,
)
