"""工具注册与执行测试。"""

from pathlib import Path

from app.repo.local_fs import LocalFsBackend
from app.tools.registry import build_default_registry

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_registry_schemas_and_execute():
    backend = LocalFsBackend(FIXTURE)
    reg = build_default_registry()
    names = {s["name"] for s in reg.schemas()}
    assert names == {
        "get_repo_meta",
        "list_directory_tree",
        "read_file",
        "search_files",
    }

    meta = reg.execute("get_repo_meta", {}, backend)
    assert "local" in meta

    tree = reg.execute("list_directory_tree", {"max_depth": 2}, backend)
    assert "README.md" in tree or "src" in tree

    content = reg.execute("read_file", {"path": "src/app.py"}, backend)
    assert "API_KEY" in content

    search = reg.execute("search_files", {"pattern": "settings"}, backend)
    assert "settings" in search.lower()
