"""分析过程 SSE 事件约定。

事件类型（SSE event 字段）：
- start  : 仓库已解析，开始分析
- step   : 进入 Agent 第 N 步（phase: llm | tools | finished）
- tool   : 单次工具调用（status: running | ok | error）
- status : 阶段文案（如 JSON 修复）
- done   : 分析完成，data 为完整 AnalyzeResponse
- error  : 失败，data.detail 为错误信息
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping


def format_sse(event: str, data: Mapping[str, Any] | Dict[str, Any]) -> str:
    """将事件格式化为 SSE 文本帧。"""
    payload = json.dumps(data, ensure_ascii=False, default=_json_default)
    # 多行 data 按 SSE 规范每行前加 data:
    lines = payload.split("\n")
    data_lines = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{data_lines}\n\n"


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"Object of type {type(obj)!r} is not JSON serializable")


def tool_input_summary(tool_input: Dict[str, Any] | None) -> str:
    """从工具入参提取适合 UI 展示的短摘要。"""
    if not tool_input:
        return ""
    for key in ("path", "pattern", "query", "glob", "prefix"):
        val = tool_input.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    # 兜底：紧凑 JSON 截断
    try:
        raw = json.dumps(tool_input, ensure_ascii=False)
    except TypeError:
        raw = str(tool_input)
    return raw if len(raw) <= 120 else raw[:117] + "..."


def preview_text(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
