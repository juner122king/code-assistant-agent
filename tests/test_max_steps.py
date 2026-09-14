"""max_steps 解析与请求字段校验。"""

from app.agent.loop import AgentLoop
from app.config import Settings
from app.models.requests import AnalyzeRequest
from app.repo.local_fs import LocalFsBackend
from pathlib import Path
from pydantic import ValidationError
import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_resolve_max_steps_default_and_clamp():
    backend = LocalFsBackend(FIXTURE)
    settings = Settings(
        anthropic_api_key="x",
        agent_max_steps=12,
        agent_max_steps_cap=40,
    )
    loop = AgentLoop(backend, settings=settings, claude=object())  # type: ignore[arg-type]
    assert loop._resolve_max_steps(None) == 12
    assert loop._resolve_max_steps(20) == 20
    assert loop._resolve_max_steps(1) == 1
    assert loop._resolve_max_steps(100) == 40
    assert loop._resolve_max_steps(0) == 1


def test_analyze_request_max_steps_bounds():
    AnalyzeRequest(repo="/tmp/r", max_steps=12)
    AnalyzeRequest(repo="/tmp/r", max_steps=None)
    with pytest.raises(ValidationError):
        AnalyzeRequest(repo="/tmp/r", max_steps=0)
    with pytest.raises(ValidationError):
        AnalyzeRequest(repo="/tmp/r", max_steps=41)
