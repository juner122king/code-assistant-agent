"""Unified diff 生成。"""

from __future__ import annotations

import difflib
from typing import Optional


def make_unified_diff(
    path: str,
    original: Optional[str],
    proposed: str,
    *,
    action: str = "modify",
) -> str:
    """生成 unified diff 文本；create/delete 时用 /dev/null 风格。"""
    if action == "create":
        from_file = "/dev/null"
        to_file = f"b/{path}"
        old_lines: list[str] = []
        new_lines = _to_diff_lines(proposed)
    elif action == "delete":
        from_file = f"a/{path}"
        to_file = "/dev/null"
        old_lines = _to_diff_lines(original)
        new_lines = []
    else:
        from_file = f"a/{path}"
        to_file = f"b/{path}"
        old_lines = _to_diff_lines(original)
        new_lines = _to_diff_lines(proposed)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=from_file,
        tofile=to_file,
        lineterm="\n",
    )
    return "".join(diff)


def _to_diff_lines(text: Optional[str]) -> list[str]:
    if text is None or text == "":
        return []
    return [ln + "\n" for ln in text.splitlines()]
