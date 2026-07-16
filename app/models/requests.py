"""HTTP 请求体模型。"""

from typing import Literal, Optional

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
