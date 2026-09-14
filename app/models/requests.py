"""HTTP 请求体模型。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """分析仓库请求。

    repo 支持：
    - 本地路径：/path/to/repo 或 ./relative
    - GitHub URL：https://github.com/owner/repo
    """

    repo: str = Field(..., min_length=1, description="本地路径或 GitHub 仓库 URL")
    branch: Optional[str] = Field(None, description="GitHub 分支，默认使用仓库 default branch")
    focus: Literal["general", "security", "bugs"] = Field(
        "general",
        description="分析侧重点",
    )
    max_steps: Optional[int] = Field(
        None,
        ge=1,
        le=40,
        description="Agent 最大步数；省略则使用服务端 AGENT_MAX_STEPS",
    )
    model: Optional[str] = Field(
        None,
        description="覆盖本次分析使用的模型 ID，如 Qwen/Qwen3-8B",
    )


class BugPayload(BaseModel):
    """分析报告中的单条 Bug，用于发起修复。"""

    title: str
    severity: Literal["high", "medium", "low"] = "medium"
    location: str = ""
    evidence: str = ""
    suggestion: str = ""


class FixProposeRequest(BaseModel):
    """为某条 Bug 生成修复提案（不落盘）。"""

    repo: str = Field(..., min_length=1, description="本地路径或 GitHub 仓库 URL")
    branch: Optional[str] = Field(None, description="GitHub 分支")
    bug: BugPayload


class FixApplyRequest(BaseModel):
    """确认后将提案写入本地仓库。"""

    fix_id: str = Field(..., min_length=1)
    paths: Optional[List[str]] = Field(
        None,
        description="仅应用这些路径；默认应用提案中全部文件",
    )
    force: bool = Field(
        False,
        description="为 true 时忽略 original 冲突检测",
    )


class FixOpenPrRequest(BaseModel):
    """确认后通过 GitHub API 建分支并开 PR（无 clone）。"""

    fix_id: str = Field(..., min_length=1)
    title: Optional[str] = None
    body: Optional[str] = None
    branch_name: Optional[str] = Field(
        None,
        description="新分支名；默认 fix/<slug>-<shortid>",
    )
