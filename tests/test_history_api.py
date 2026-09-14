"""分析记录与模型目录 HTTP API。"""

from app.history.store import AnalysisStore
from app.main import app
from fastapi.testclient import TestClient
import app.history.store as history_store


def _client(tmp_path):
    history_store.reset_analysis_store()
    history_store._store = AnalysisStore(path=tmp_path / "runs.json", max_runs=10)
    return TestClient(app)


def test_models_catalog_includes_free_and_paid():
    client = TestClient(app)
    res = client.get("/analyze/models")
    assert res.status_code == 200
    body = res.json()
    ids = [m["id"] for m in body["models"]]
    assert "Qwen/Qwen3-8B" in ids
    assert "Qwen/Qwen3-Coder-30B-A3B-Instruct" in ids
    assert "deepseek-ai/DeepSeek-V3" in ids
    assert body["defaults"]["enable_thinking"] is False
    assert any(m["tier"] == "paid" for m in body["models"])


def test_runs_list_detail_delete(tmp_path):
    client = _client(tmp_path)
    store = history_store._store
    run = store.begin(repo="/repo/demo", focus="bugs")
    store.append_event(run["id"], "start", {"repo": "/repo/demo", "source": "local", "model": "Qwen/Qwen3-8B"})
    store.finish(
        run["id"],
        report={
            "repo": "/repo/demo",
            "source": "local",
            "structure": {"summary": "x", "tree_preview": "", "tech_stack": []},
            "risks": [],
            "bugs": [],
            "agent_steps": 1,
            "model": "Qwen/Qwen3-8B",
            "tool_calls": [],
        },
    )

    listed = client.get("/analyze/runs")
    assert listed.status_code == 200
    runs = listed.json()["runs"]
    assert runs[0]["id"] == run["id"]
    assert runs[0]["repo_short"] == "demo"

    detail = client.get(f"/analyze/runs/{run['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["events"][0]["type"] == "start"
    assert body["report"]["repo"] == "/repo/demo"

    deleted = client.delete(f"/analyze/runs/{run['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/analyze/runs/{run['id']}").status_code == 404


def test_missing_run_404(tmp_path):
    client = _client(tmp_path)
    assert client.get("/analyze/runs/nope").status_code == 404
