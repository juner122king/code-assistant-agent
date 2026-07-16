"""search_files 工具：按路径/文件名子串匹配。"""

from __future__ import annotations

from typing import Any, Dict

from app.repo.base import RepoBackend
from app.tools.registry import Tool


def handle(
    backend: RepoBackend,
    pattern: str = "",
    max_hits: int = 20,
    max_file_bytes: int = 30_000,
    max_tree_entries: int = 200,
    **_: Any,
) -> Dict[str, Any]:
    if not pattern:
        return {"error": "pattern is required"}
    hits = backend.search(pattern, max_hits=int(max_hits or 20))
    return {"pattern": pattern, "count": len(hits), "matches": hits}


TOOL = Tool(
    name="search_files",
    description=(
        "按路径或文件名子串搜索文件（不区分大小写）。"
        "例如搜索 'test'、'Dockerfile'、'.env'、'secret'、'config'。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "要匹配的路径子串",
            },
            "max_hits": {
                "type": "integer",
                "description": "最多返回条数，默认 20",
                "default": 20,
            },
        },
        "required": ["pattern"],
    },
    handler=handle,
)
