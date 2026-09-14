"""分析记录 API 模型。"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.responses import AnalyzeResponse


class AnalysisEvent(BaseModel):
    type: str
    data: Any = None
    at: int = 0


class AnalysisRunSummary(BaseModel):
    id: str
    status: Literal["running", "done", "error"]
    repo: str = ""
    repo_short: str = ""
    branch: Optional[str] = None
    focus: str = "general"
    source: str = ""
    model: str = ""
    max_steps: Optional[int] = None
    agent_steps: int = 0
    event_count: int = 0
    risk_count: int = 0
    bug_count: int = 0
    created_at: int = 0
    finished_at: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


class AnalysisRunDetail(AnalysisRunSummary):
    events: List[AnalysisEvent] = Field(default_factory=list)
    report: Optional[AnalyzeResponse] = None


class AnalysisRunList(BaseModel):
    runs: List[AnalysisRunSummary] = Field(default_factory=list)
