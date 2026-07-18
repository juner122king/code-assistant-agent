"""HTTP 响应体模型。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.requests import BugPayload


class StructureReport(BaseModel):
    summary: str = Field("", description="项目结构文字摘要")
    tree_preview: str = Field("", description="目录树预览")
    tech_stack: List[str] = Field(default_factory=list, description="识别到的技术栈")


class RiskItem(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"] = "medium"
    evidence: str = ""
    recommendation: str = ""


class BugItem(BaseModel):
    title: str
    severity: Literal["high", "medium", "low"] = "medium"
    location: str = ""
    evidence: str = ""
    suggestion: str = ""


class AnalyzeResponse(BaseModel):
    repo: str
    source: Literal["local", "github"]
    structure: StructureReport = Field(default_factory=StructureReport)
    risks: List[RiskItem] = Field(default_factory=list)
    bugs: List[BugItem] = Field(default_factory=list)
    agent_steps: int = 0
    model: str = ""
    raw_summary: Optional[str] = Field(
        None,
        description="解析失败时保留模型原始文本",
    )
    tool_calls: List[str] = Field(
        default_factory=list,
        description="本次分析中工具调用轨迹，便于学习观察 Agent 行为",
    )


class FileChange(BaseModel):
    path: str
    action: Literal["modify", "create", "delete"] = "modify"
    original: Optional[str] = Field(
        None,
        description="提案生成时的原文；apply 时用于冲突检测",
    )
    proposed: str = Field(
        "",
        description="完整新内容；delete 时可为空",
    )
    unified_diff: str = Field("", description="展示用 unified diff")


class FixProposal(BaseModel):
    fix_id: str
    repo: str
    source: Literal["local", "github"]
    bug: BugPayload
    summary: str = ""
    changes: List[FileChange] = Field(default_factory=list)
    agent_steps: int = 0
    model: str = ""
    tool_calls: List[str] = Field(default_factory=list)
    expires_at: Optional[str] = None
    applied: bool = False
    raw_summary: Optional[str] = Field(
        None,
        description="解析失败时保留模型原始文本",
    )


class FixApplyResponse(BaseModel):
    fix_id: str
    applied: List[str] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    message: str = ""


class FixOpenPrResponse(BaseModel):
    fix_id: str
    pr_url: str
    branch: str
    number: int
    message: str = ""
