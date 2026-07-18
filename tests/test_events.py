"""SSE 事件格式化单元测试。"""

from app.models.events import format_sse, preview_text, tool_input_summary


def test_format_sse_basic():
    raw = format_sse("tool", {"name": "read_file", "status": "running"})
    assert raw.startswith("event: tool\n")
    assert 'data: {"name": "read_file", "status": "running"}' in raw
    assert raw.endswith("\n\n")


def test_tool_input_summary_prefers_path():
    assert tool_input_summary({"path": "src/app.py", "limit": 10}) == "src/app.py"
    assert tool_input_summary({"pattern": "TODO"}) == "TODO"
    assert tool_input_summary({}) == ""


def test_preview_text_truncates():
    long = "a" * 300
    out = preview_text(long, limit=50)
    assert len(out) == 50
    assert out.endswith("...")
