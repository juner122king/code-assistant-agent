"""单次分析会话状态。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentSession:
    repo_label: str
    source: str
    focus: str = "general"
    messages: List[Dict[str, Any]] = field(default_factory=list)
    steps: int = 0
    tool_calls: List[str] = field(default_factory=list)

    def record_tool(self, name: str, tool_input: Optional[Dict[str, Any]]) -> None:
        path = ""
        if tool_input:
            path = str(tool_input.get("path") or tool_input.get("pattern") or "")
        label = f"{name}({path})" if path else name
        self.tool_calls.append(label)
