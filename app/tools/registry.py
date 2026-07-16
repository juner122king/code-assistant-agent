"""Tool 协议与注册表。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.repo.base import RepoBackend

logger = logging.getLogger(__name__)

Handler = Callable[..., Any]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Handler

    def to_anthropic_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> List[Dict[str, Any]]:
        return [t.to_anthropic_schema() for t in self._tools.values()]

    def execute(
        self,
        name: str,
        tool_input: Optional[Dict[str, Any]],
        backend: RepoBackend,
        *,
        max_file_bytes: int = 30_000,
        max_tree_entries: int = 200,
    ) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
        kwargs = dict(tool_input or {})
        try:
            result = tool.handler(
                backend,
                max_file_bytes=max_file_bytes,
                max_tree_entries=max_tree_entries,
                **kwargs,
            )
        except TypeError:
            # handler 可能不接受额外 kwargs
            try:
                result = tool.handler(backend, **kwargs)
            except Exception as exc:
                logger.exception("tool %s failed", name)
                return json.dumps({"error": str(exc)}, ensure_ascii=False)
        except Exception as exc:
            logger.exception("tool %s failed", name)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, indent=2)


def build_default_registry() -> ToolRegistry:
    from app.tools.list_tree import TOOL as list_tree_tool
    from app.tools.read_file import TOOL as read_file_tool
    from app.tools.search_code import TOOL as search_tool
    from app.tools.summarize_repo import TOOL as meta_tool

    reg = ToolRegistry()
    for t in (meta_tool, list_tree_tool, read_file_tool, search_tool):
        reg.register(t)
    return reg
