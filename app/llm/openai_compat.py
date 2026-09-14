"""Anthropic 形状 messages/tools ↔ OpenAI chat.completions。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def anthropic_tools_to_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for tool in tools:
        params = tool.get("input_schema") or {"type": "object", "properties": {}}
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name") or "",
                    "description": tool.get("description") or "",
                    "parameters": params,
                },
            }
        )
    return out


def _join_text(parts: List[str]) -> str:
    return "\n".join(p for p in parts if p)


def anthropic_messages_to_openai(
    messages: List[Dict[str, Any]],
    system: str = "",
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "assistant":
            out.append(_assistant_to_openai(content))
        elif role == "user":
            out.extend(_user_to_openai(content))
        else:
            out.append(msg)
    return out


def _assistant_to_openai(content: Any) -> Dict[str, Any]:
    if isinstance(content, str):
        return {"role": "assistant", "content": content}

    text_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text") or "")
        elif btype == "tool_use":
            inp = block.get("input")
            if inp is None:
                inp = {}
            tool_calls.append(
                {
                    "id": block.get("id") or "",
                    "type": "function",
                    "function": {
                        "name": block.get("name") or "",
                        "arguments": json.dumps(inp, ensure_ascii=False),
                    },
                }
            )
    item: Dict[str, Any] = {
        "role": "assistant",
        "content": _join_text(text_parts),
    }
    if tool_calls:
        item["tool_calls"] = tool_calls
    return item


def _user_to_openai(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, str):
        return [{"role": "user", "content": content}]

    texts: List[str] = []
    results: List[Dict[str, Any]] = []
    for block in content or []:
        if isinstance(block, str):
            texts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "tool_result":
            raw = block.get("content")
            if raw is None:
                text = ""
            elif isinstance(raw, str):
                text = raw
            else:
                text = json.dumps(raw, ensure_ascii=False)
            results.append(
                {
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id") or "",
                    "content": text,
                }
            )
        elif btype == "text":
            texts.append(block.get("text") or "")

    out: List[Dict[str, Any]] = []
    if texts:
        out.append({"role": "user", "content": _join_text(texts)})
    out.extend(results)
    return out


def _parse_tool_arguments(raw: Any) -> Dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"_raw": parsed}
    return {}


@dataclass
class CompatMessage:
    content: List[Dict[str, Any]] = field(default_factory=list)
    stop_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


def map_finish_reason(finish: Optional[str], has_tool_calls: bool) -> str:
    if finish == "tool_calls" or (has_tool_calls and finish != "stop"):
        return "tool_use"
    if finish == "length":
        return "max_tokens"
    return "end_turn"


def openai_response_to_anthropic(data: Dict[str, Any]) -> CompatMessage:
    choices = data.get("choices") or []
    choice = choices[0] if choices else {}
    msg = choice.get("message") or {}
    finish = choice.get("finish_reason")
    blocks: List[Dict[str, Any]] = []

    text = msg.get("content")
    if isinstance(text, str) and text:
        blocks.append({"type": "text", "text": text})

    tool_calls = msg.get("tool_calls") or []
    for tc in tool_calls:
        fn = tc.get("function") or {}
        blocks.append(
            {
                "type": "tool_use",
                "id": tc.get("id") or "",
                "name": fn.get("name") or "",
                "input": _parse_tool_arguments(fn.get("arguments")),
            }
        )

    return CompatMessage(
        content=blocks,
        stop_reason=map_finish_reason(finish, bool(tool_calls)),
        usage=data.get("usage"),
    )
