"""分析记录存储。"""

from app.history.store import AnalysisStore


def test_begin_append_finish_list_delete(tmp_path):
    store = AnalysisStore(path=tmp_path / "runs.json", max_runs=10)
    run = store.begin(repo="/tmp/sample", focus="security", max_steps=8)
    rid = run["id"]
    store.append_event(rid, "start", {"repo": "/tmp/sample", "source": "local", "model": "Qwen/Qwen3-8B"})
    store.append_event(
        rid,
        "tool",
        {"name": "read_file", "status": "ok", "input_summary": "src/app.py", "preview": "print(1)"},
    )
    report = {
        "repo": "/tmp/sample",
        "source": "local",
        "structure": {"summary": "demo", "tree_preview": "", "tech_stack": ["Python"]},
        "risks": [{"title": "r", "severity": "low", "evidence": "", "recommendation": ""}],
        "bugs": [
            {"title": "sql", "severity": "high", "location": "src/app.py", "evidence": "", "suggestion": ""}
        ],
        "agent_steps": 2,
        "model": "Qwen/Qwen3-8B",
        "tool_calls": ["read_file(src/app.py)"],
    }
    store.append_event(rid, "done", report)
    finished = store.finish(rid, report=report)
    assert finished["status"] == "done"

    listed = store.list_runs()
    assert listed[0]["id"] == rid
    assert listed[0]["bug_count"] == 1
    assert listed[0]["risk_count"] == 1
    assert listed[0]["event_count"] == 3

    detail = store.get(rid)
    assert detail["events"][0]["type"] == "start"
    assert detail["events"][-1]["type"] == "done"
    assert detail["events"][-1]["data"]["bugs"] == 1
    assert detail["report"]["bugs"][0]["title"] == "sql"

    assert store.delete(rid) is True
    assert store.get(rid) is None
    assert store.list_runs() == []


def test_max_runs_drops_oldest(tmp_path):
    store = AnalysisStore(path=tmp_path / "runs.json", max_runs=2)
    a = store.begin(repo="a")
    b = store.begin(repo="b")
    c = store.begin(repo="c")
    ids = [x["id"] for x in store.list_runs()]
    assert c["id"] in ids
    assert b["id"] in ids
    assert a["id"] not in ids


def test_reload_from_disk(tmp_path):
    path = tmp_path / "runs.json"
    s1 = AnalysisStore(path=path, max_runs=5)
    run = s1.begin(repo="disk")
    s1.finish(run["id"], report={"repo": "disk", "source": "local"})
    s2 = AnalysisStore(path=path, max_runs=5)
    assert s2.get(run["id"])["repo"] == "disk"
