"""修复 Agent：只读工具 + 输出 FixProposal（不落盘）。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.agent.fix_prompts import FIX_SYSTEM_PROMPT, build_fix_user_message
from app.agent.loop import (
    _content_blocks_to_api,
    _extract_text,
    _extract_tool_uses,
    _parse_report_json,
)
from app.agent.session import AgentSession
from app.config import Settings, get_settings
from app.fix.service import enrich_changes
from app.fix.store import FixStore, get_fix_store
from app.llm.claude_client import ClaudeClient
from app.models.events import preview_text, tool_input_summary
from app.models.requests import BugPayload
from app.models.responses import FixProposal
from app.repo.base import RepoBackend
from app.tools.registry import ToolRegistry, build_default_registry

logger = logging.getLogger(__name__)


def _parse_fix_json(text: str) -> Optional[Dict[str, Any]]:
    data = _parse_report_json(text)
    if data is not None:
        return data
    if not text:
        return None
    # 宽松：找含 changes 的对象
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    return None


class FixAgentLoop:
    def __init__(
        self,
        backend: RepoBackend,
        *,
        settings: Optional[Settings] = None,
        claude: Optional[ClaudeClient] = None,
        registry: Optional[ToolRegistry] = None,
        store: Optional[FixStore] = None,
    ):
        self.backend = backend
        self.settings = settings or get_settings()
        self.claude = claude or ClaudeClient(self.settings)
        self.registry = registry or build_default_registry()
        self.store = store or get_fix_store(self.settings.fix_proposal_ttl_seconds)

    def run(
        self,
        bug: BugPayload,
        *,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> FixProposal:
        result: Optional[FixProposal] = None
        for etype, data in self.iter_run(bug, repo=repo, branch=branch):
            if etype == "done":
                result = data  # type: ignore[assignment]
        if result is None:
            raise RuntimeError("FixAgentLoop.iter_run 未产生 done 事件")
        return result

    def iter_run(
        self,
        bug: BugPayload,
        *,
        repo: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Iterator[Tuple[str, Any]]:
        meta = self.backend.meta()
        repo_label = repo or meta.identifier
        source = meta.source
        session = AgentSession(
            repo_label=repo_label,
            source=source,
            focus="fix",
        )
        session.messages = [
            {
                "role": "user",
                "content": build_fix_user_message(repo_label, source, bug),
            }
        ]

        tools = self.registry.schemas()
        final_text = ""
        max_steps = self.settings.fix_max_steps

        yield (
            "start",
            {
                "repo": repo_label,
                "source": source,
                "max_steps": max_steps,
                "mode": "fix",
                "bug_title": bug.title,
                "model": self.claude.model,
            },
        )

        for step in range(1, max_steps + 1):
            session.steps = step
            logger.info("=== Fix Agent step %d/%d ===", step, max_steps)

            yield (
                "step",
                {
                    "step": step,
                    "max_steps": max_steps,
                    "phase": "llm",
                    "message": f"第 {step}/{max_steps} 步：规划/生成修复…",
                },
            )

            response = self.claude.create_message(
                messages=session.messages,
                system=FIX_SYSTEM_PROMPT,
                tools=tools,
            )

            assistant_blocks = _content_blocks_to_api(response.content)
            session.messages.append({"role": "assistant", "content": assistant_blocks})

            tool_uses = _extract_tool_uses(response.content)
            if not tool_uses:
                final_text = _extract_text(response.content)
                yield (
                    "step",
                    {
                        "step": step,
                        "max_steps": max_steps,
                        "phase": "finished",
                        "message": "模型已输出修复提案，正在整理…",
                    },
                )
                break

            yield (
                "step",
                {
                    "step": step,
                    "max_steps": max_steps,
                    "phase": "tools",
                    "message": f"第 {step}/{max_steps} 步：执行 {len(tool_uses)} 个工具…",
                    "tool_count": len(tool_uses),
                },
            )

            tool_results: List[Dict[str, Any]] = []
            for tu in tool_uses:
                name = tu["name"]
                tool_input = tu.get("input") or {}
                summary = tool_input_summary(tool_input)
                session.record_tool(name, tool_input)

                yield (
                    "tool",
                    {
                        "step": step,
                        "name": name,
                        "input_summary": summary,
                        "status": "running",
                    },
                )

                try:
                    result_str = self.registry.execute(
                        name,
                        tool_input,
                        self.backend,
                        max_file_bytes=self.settings.agent_max_file_bytes,
                        max_tree_entries=self.settings.agent_max_tree_entries,
                    )
                    if len(result_str) > 80_000:
                        result_str = result_str[:80_000] + "\n...[tool result truncated]"
                    yield (
                        "tool",
                        {
                            "step": step,
                            "name": name,
                            "input_summary": summary,
                            "status": "ok",
                            "preview": preview_text(result_str),
                        },
                    )
                except Exception as exc:
                    logger.exception("tool %s failed", name)
                    result_str = f"error: {exc}"
                    yield (
                        "tool",
                        {
                            "step": step,
                            "name": name,
                            "input_summary": summary,
                            "status": "error",
                            "preview": preview_text(str(exc)),
                        },
                    )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": result_str,
                    }
                )
            session.messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("Fix Agent hit max_steps=%d", max_steps)
            yield (
                "status",
                {"message": f"已达最大步数 {max_steps}，尝试基于已有信息生成提案…"},
            )
            final_text = _extract_text(
                session.messages[-1]["content"]
                if session.messages and session.messages[-1]["role"] == "assistant"
                else []
            )
            if not final_text:
                final_text = json.dumps(
                    {
                        "summary": f"达到最大步数 {max_steps}，未能完成修复提案",
                        "changes": [],
                    },
                    ensure_ascii=False,
                )

        parsed = _parse_fix_json(final_text)
        if parsed is None and final_text:
            yield (
                "status",
                {"message": "提案格式需修正，正在请求模型输出标准 JSON…"},
            )
            try:
                repair_messages = session.messages + [
                    {
                        "role": "user",
                        "content": (
                            "请把修复结论严格改写成单个 JSON 对象，"
                            "不要 markdown。字段：summary, changes"
                            "（changes[].path/action/proposed）。"
                        ),
                    }
                ]
                repair = self.claude.create_message(
                    messages=repair_messages,
                    system=FIX_SYSTEM_PROMPT,
                    tools=[],
                    max_tokens=4096,
                )
                final_text = _extract_text(repair.content)
                parsed = _parse_fix_json(final_text)
                session.steps += 1
            except Exception:
                logger.exception("fix JSON repair failed")
                yield ("status", {"message": "JSON 修复失败，将返回空 changes。"})

        summary = ""
        raw_changes: List[Any] = []
        if parsed:
            summary = str(parsed.get("summary") or "")
            raw = parsed.get("changes") or []
            if isinstance(raw, list):
                raw_changes = raw
        else:
            summary = "未能解析结构化修复提案"

        changes = enrich_changes(
            self.backend,
            raw_changes,
            max_files=self.settings.fix_max_files,
            max_file_bytes=self.settings.agent_max_file_bytes,
        )

        stored = self.store.create(
            repo=repo_label,
            source=source,
            branch=branch,
            bug=bug,
            summary=summary,
            changes=changes,
            agent_steps=session.steps,
            model=self.claude.model,
            tool_calls=session.tool_calls,
            raw_summary=None if parsed else (final_text[:8000] if final_text else None),
        )
        yield ("done", stored.to_proposal())
