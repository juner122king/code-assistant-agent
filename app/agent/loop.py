"""Agent 主循环：Claude tool-use ↔ 本地工具执行。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.agent.prompts import SYSTEM_PROMPT, build_user_message
from app.agent.session import AgentSession
from app.config import Settings, get_settings
from app.llm.claude_client import ClaudeClient
from app.models.responses import (
    AnalyzeResponse,
    BugItem,
    RiskItem,
    StructureReport,
)
from app.repo.base import RepoBackend
from app.tools.registry import ToolRegistry, build_default_registry

logger = logging.getLogger(__name__)


def _block_get(block: Any, key: str, default: Any = None) -> Any:
    """兼容 SDK 对象与 dict 两种 content block。"""
    if isinstance(block, dict):
        return block.get(key, default)
    return getattr(block, key, default)


def _content_blocks_to_api(content: Any) -> List[Dict[str, Any]]:
    """把 SDK 返回的 content blocks 转成可序列化 messages 格式。"""
    blocks: List[Dict[str, Any]] = []
    for block in content:
        btype = _block_get(block, "type")
        if btype == "text":
            blocks.append({"type": "text", "text": _block_get(block, "text", "") or ""})
        elif btype == "tool_use":
            tool_input = _block_get(block, "input")
            if tool_input is None:
                tool_input = {}
            blocks.append(
                {
                    "type": "tool_use",
                    "id": _block_get(block, "id"),
                    "name": _block_get(block, "name"),
                    "input": tool_input,
                }
            )
        else:
            # 忽略 thinking 等其它块
            logger.debug("skip content block type=%s", btype)
    return blocks


def _extract_text(content: Any) -> str:
    parts: List[str] = []
    for block in content:
        if _block_get(block, "type") == "text":
            parts.append(_block_get(block, "text", "") or "")
    return "\n".join(parts).strip()


def _extract_tool_uses(content: Any) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for block in content:
        if _block_get(block, "type") == "tool_use":
            tool_input = _block_get(block, "input")
            if tool_input is None:
                tool_input = {}
            tools.append(
                {
                    "id": _block_get(block, "id"),
                    "name": _block_get(block, "name"),
                    "input": tool_input,
                }
            )
    return tools


def _parse_report_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    # 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 去掉 ```json 围栏
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 取最外层大括号
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _to_response(
    *,
    repo: str,
    source: str,
    data: Optional[Dict[str, Any]],
    raw_text: str,
    session: AgentSession,
    model: str,
) -> AnalyzeResponse:
    if not data:
        return AnalyzeResponse(
            repo=repo,
            source=source,  # type: ignore[arg-type]
            structure=StructureReport(summary="未能解析结构化报告，请查看 raw_summary"),
            risks=[],
            bugs=[],
            agent_steps=session.steps,
            model=model,
            raw_summary=raw_text[:8000] if raw_text else None,
            tool_calls=session.tool_calls,
        )

    structure_raw = data.get("structure") or {}
    if isinstance(structure_raw, str):
        structure = StructureReport(summary=structure_raw)
    else:
        structure = StructureReport(
            summary=str(structure_raw.get("summary") or ""),
            tree_preview=str(structure_raw.get("tree_preview") or ""),
            tech_stack=list(structure_raw.get("tech_stack") or []),
        )

    risks: List[RiskItem] = []
    for item in data.get("risks") or []:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "medium").lower()
        if sev not in ("high", "medium", "low"):
            sev = "medium"
        risks.append(
            RiskItem(
                title=str(item.get("title") or "未命名风险"),
                severity=sev,  # type: ignore[arg-type]
                evidence=str(item.get("evidence") or ""),
                recommendation=str(item.get("recommendation") or ""),
            )
        )

    bugs: List[BugItem] = []
    for item in data.get("bugs") or []:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "medium").lower()
        if sev not in ("high", "medium", "low"):
            sev = "medium"
        bugs.append(
            BugItem(
                title=str(item.get("title") or "未命名问题"),
                severity=sev,  # type: ignore[arg-type]
                location=str(item.get("location") or ""),
                evidence=str(item.get("evidence") or ""),
                suggestion=str(item.get("suggestion") or ""),
            )
        )

    return AnalyzeResponse(
        repo=repo,
        source=source,  # type: ignore[arg-type]
        structure=structure,
        risks=risks,
        bugs=bugs,
        agent_steps=session.steps,
        model=model,
        raw_summary=None,
        tool_calls=session.tool_calls,
    )


class AgentLoop:
    def __init__(
        self,
        backend: RepoBackend,
        *,
        settings: Optional[Settings] = None,
        claude: Optional[ClaudeClient] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self.backend = backend
        self.settings = settings or get_settings()
        self.claude = claude or ClaudeClient(self.settings)
        self.registry = registry or build_default_registry()

    def run(self, *, focus: str = "general") -> AnalyzeResponse:
        meta = self.backend.meta()
        session = AgentSession(
            repo_label=meta.identifier,
            source=meta.source,
            focus=focus,
        )
        session.messages = [
            {
                "role": "user",
                "content": build_user_message(meta.identifier, meta.source, focus),
            }
        ]

        tools = self.registry.schemas()
        final_text = ""
        max_steps = self.settings.agent_max_steps

        for step in range(1, max_steps + 1):
            session.steps = step
            logger.info("=== Agent step %d/%d ===", step, max_steps)

            response = self.claude.create_message(
                messages=session.messages,
                system=SYSTEM_PROMPT,
                tools=tools,
            )

            assistant_blocks = _content_blocks_to_api(response.content)
            session.messages.append({"role": "assistant", "content": assistant_blocks})

            tool_uses = _extract_tool_uses(response.content)
            stop_reason = getattr(response, "stop_reason", None)

            if not tool_uses:
                final_text = _extract_text(response.content)
                logger.info("Agent finished (stop_reason=%s), no more tools", stop_reason)
                break

            # 执行所有 tool_use，组装 tool_result
            tool_results: List[Dict[str, Any]] = []
            for tu in tool_uses:
                name = tu["name"]
                tool_input = tu.get("input") or {}
                session.record_tool(name, tool_input)
                logger.info("tool_use: %s input=%s", name, tool_input)
                result_str = self.registry.execute(
                    name,
                    tool_input,
                    self.backend,
                    max_file_bytes=self.settings.agent_max_file_bytes,
                    max_tree_entries=self.settings.agent_max_tree_entries,
                )
                # 防止单次结果过大
                if len(result_str) > 80_000:
                    result_str = result_str[:80_000] + "\n...[tool result truncated]"
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": result_str,
                    }
                )
            session.messages.append({"role": "user", "content": tool_results})
        else:
            # 步数耗尽
            logger.warning("Agent hit max_steps=%d", max_steps)
            final_text = _extract_text(
                session.messages[-1]["content"]
                if session.messages and session.messages[-1]["role"] == "assistant"
                else []
            )
            if not final_text:
                final_text = json.dumps(
                    {
                        "structure": {
                            "summary": f"达到最大步数 {max_steps}，分析可能不完整",
                            "tree_preview": "",
                            "tech_stack": [],
                        },
                        "risks": [],
                        "bugs": [],
                    },
                    ensure_ascii=False,
                )

        parsed = _parse_report_json(final_text)
        if parsed is None and final_text:
            # 一次修复尝试：要求只输出 JSON
            logger.info("JSON parse failed, requesting repair")
            try:
                repair_messages = session.messages + [
                    {
                        "role": "user",
                        "content": (
                            "请把你的最终结论严格改写成单个 JSON 对象，"
                            "不要 markdown，不要其它说明。字段：structure, risks, bugs。"
                        ),
                    }
                ]
                repair = self.claude.create_message(
                    messages=repair_messages,
                    system=SYSTEM_PROMPT,
                    tools=[],  # 不再给工具，强制文本输出
                    max_tokens=4096,
                )
                final_text = _extract_text(repair.content)
                parsed = _parse_report_json(final_text)
                session.steps += 1
            except Exception:
                logger.exception("JSON repair failed")

        return _to_response(
            repo=meta.identifier,
            source=meta.source,
            data=parsed,
            raw_text=final_text,
            session=session,
            model=self.claude.model,
        )
