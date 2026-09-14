"""分析开始前预取 meta / 目录树 / README / 依赖清单，少 2–3 轮 LLM。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.config import Settings
from app.repo.base import RepoBackend
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

README_CANDIDATES = ("README.md", "README.rst", "README.txt", "README")
MANIFEST_CANDIDATES = (
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "composer.json",
    "pom.xml",
)

_BRIEFING_CAP = 40_000
_TREE_CAP = 8_000
_FILE_SECTION_CAP = 8_000


@dataclass
class BootstrapItem:
    name: str
    tool_input: Dict[str, Any]
    result: str
    ok: bool = True


@dataclass
class BootstrapResult:
    briefing: str
    items: List[BootstrapItem] = field(default_factory=list)


def _run_tool(
    registry: ToolRegistry,
    backend: RepoBackend,
    settings: Settings,
    name: str,
    tool_input: Optional[Dict[str, Any]] = None,
) -> BootstrapItem:
    payload = dict(tool_input or {})
    try:
        result = registry.execute(
            name,
            payload,
            backend,
            max_file_bytes=settings.agent_max_file_bytes,
            max_tree_entries=settings.agent_max_tree_entries,
        )
        ok = True
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("error"):
                ok = False
        return BootstrapItem(name=name, tool_input=payload, result=result, ok=ok)
    except Exception as exc:
        logger.warning("bootstrap %s failed: %s", name, exc)
        return BootstrapItem(
            name=name,
            tool_input=payload,
            result=json.dumps({"error": str(exc)}, ensure_ascii=False),
            ok=False,
        )


def _section(title: str, body: str, cap: int) -> str:
    text = (body or "").strip()
    if len(text) > cap:
        text = text[:cap] + "\n...[truncated]"
    return f"## {title}\n{text}\n"


def collect_bootstrap(
    registry: ToolRegistry,
    backend: RepoBackend,
    settings: Settings,
) -> BootstrapResult:
    items: List[BootstrapItem] = []
    parts: List[str] = [
        "以下证据已由系统预取，请勿再调用 get_repo_meta 或 list_directory_tree，"
        "也不要重复读取下列已给出的文件。"
        "README 与依赖清单不足以下结论：本轮必须并行 read_file 入口源码"
        "（目录树里的 src/、app.py、main.py、index 等），必要时再 search_files。"
        "读完源码后再输出 JSON。",
    ]

    meta_item = _run_tool(registry, backend, settings, "get_repo_meta", {})
    items.append(meta_item)
    if meta_item.ok:
        parts.append(_section("仓库元信息", meta_item.result, 2_000))

    tree_item = _run_tool(
        registry,
        backend,
        settings,
        "list_directory_tree",
        {"path": "", "max_depth": 3},
    )
    items.append(tree_item)
    if tree_item.ok:
        parts.append(_section("目录树", tree_item.result, _TREE_CAP))

    readme_read = False
    for path in README_CANDIDATES:
        item = _run_tool(registry, backend, settings, "read_file", {"path": path})
        if not item.ok:
            continue
        items.append(item)
        parts.append(_section(path, item.result, _FILE_SECTION_CAP))
        readme_read = True
        break
    if not readme_read:
        logger.info("bootstrap: no README found")

    for path in MANIFEST_CANDIDATES:
        item = _run_tool(registry, backend, settings, "read_file", {"path": path})
        if not item.ok:
            continue
        items.append(item)
        parts.append(_section(path, item.result, _FILE_SECTION_CAP))

    briefing = "\n".join(parts).strip()
    if len(briefing) > _BRIEFING_CAP:
        briefing = briefing[:_BRIEFING_CAP] + "\n...[bootstrap truncated]"
    return BootstrapResult(briefing=briefing, items=items)
