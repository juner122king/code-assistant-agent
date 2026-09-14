"""分析预取与步数/延迟策略。"""

from pathlib import Path

from app.agent.bootstrap import collect_bootstrap
from app.agent.loop import AgentLoop
from app.agent.prompts import step_system_prompt
from app.config import Settings
from app.repo.local_fs import LocalFsBackend
from app.tools.registry import build_default_registry

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def _settings(**kwargs) -> Settings:
    defaults = dict(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_step_delay_seconds=0,
        agent_max_steps=8,
        agent_max_tokens=4096,
        agent_tool_max_tokens=1024,
    )
    defaults.update(kwargs)
    return Settings(**defaults)


def test_bootstrap_sample_repo_includes_tree_and_readme():
    backend = LocalFsBackend(FIXTURE)
    settings = _settings()
    result = collect_bootstrap(build_default_registry(), backend, settings)
    names = [item.name for item in result.items]
    assert "get_repo_meta" in names
    assert "list_directory_tree" in names
    assert "read_file" in names
    assert "README.md" in result.briefing
    assert "requirements.txt" in result.briefing
    assert "src/" in result.briefing or "src" in result.briefing
    assert "请勿再调用" in result.briefing
    assert "入口源码" in result.briefing
    assert all(item.ok for item in result.items)


def test_loop_injects_bootstrap_without_llm():
    backend = LocalFsBackend(FIXTURE)
    settings = _settings()
    class Dummy:
        model = "dummy"

        def create_message(self, **kwargs):
            raise AssertionError("LLM should not be called before first step event")

    loop = AgentLoop(backend, settings=settings, claude=Dummy())  # type: ignore[arg-type]
    events = []
    gen = loop.iter_run(focus="general", max_steps=3)
    for etype, data in gen:
        events.append((etype, data))
        if etype == "step" and data.get("phase") == "llm":
            break
    kinds = [e[0] for e in events]
    assert kinds[0] == "start"
    assert "status" in kinds
    assert kinds.count("tool") >= 3
    tool_names = [d["name"] for t, d in events if t == "tool"]
    assert "get_repo_meta" in tool_names
    assert "list_directory_tree" in tool_names


def test_default_max_steps_is_eight():
    backend = LocalFsBackend(FIXTURE)
    loop = AgentLoop(backend, settings=_settings(), claude=object())  # type: ignore[arg-type]
    assert loop._resolve_max_steps(None) == 8


def test_openai_step_delay_zero_anthropic_default():
    openai = Settings(
        llm_provider="openai",
        llm_api_key="x",
        llm_step_delay_seconds=None,
    )
    assert openai.resolved_step_delay == 0.0
    anthropic = Settings(
        llm_provider="anthropic",
        anthropic_api_key="x",
        llm_step_delay_seconds=None,
    )
    assert anthropic.resolved_step_delay == 2.5
    explicit = Settings(
        llm_provider="openai",
        llm_api_key="x",
        llm_step_delay_seconds=0,
    )
    assert explicit.resolved_step_delay == 0.0


def test_intermediate_max_tokens_then_full_on_last_steps():
    loop = AgentLoop(
        LocalFsBackend(FIXTURE),
        settings=_settings(),
        claude=object(),  # type: ignore[arg-type]
    )
    assert loop._max_tokens_for_step(1, 8) == 1024
    assert loop._max_tokens_for_step(2, 8) == 4096
    assert loop._max_tokens_for_step(8, 8) == 4096


def test_last_steps_prompt_asks_for_json_only():
    early = step_system_prompt(1, 8)
    late = step_system_prompt(7, 8)
    assert "并行" in early
    assert "只输出 JSON" in late
    assert "禁止新的探索" in late
