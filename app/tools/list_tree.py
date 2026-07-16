"""list_directory_tree 工具。"""

from __future__ import annotations

from typing import Any, Dict

from app.repo.base import RepoBackend
from app.tools.registry import Tool


def handle(
    backend: RepoBackend,
    path: str = "",
    max_depth: int = 3,
    max_file_bytes: int = 30_000,
    max_tree_entries: int = 200,
    **_: Any,
) -> Dict[str, Any]:
    entries = backend.list_tree(
        path=path or "",
        max_depth=int(max_depth or 3),
        max_entries=int(max_tree_entries),
    )
    return {
        "path": path or ".",
        "max_depth": max_depth,
        "count": len([e for e in entries if not str(e).startswith("...")]),
        "entries": entries,
    }


TOOL = Tool(
    name="list_directory_tree",
    description=(
        "列出仓库目录树（相对路径）。用于了解项目结构。"
        "可指定子路径与最大深度。目录以 / 结尾。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "相对仓库根的子路径，默认根目录",
            },
            "max_depth": {
                "type": "integer",
                "description": "最大深度，默认 3",
                "default": 3,
            },
        },
        "required": [],
    },
    handler=handle,
)
