"""本地文件系统仓库后端。"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from app.repo.base import FileReadResult, RepoBackend, RepoMeta

logger = logging.getLogger(__name__)


def list_git_branches(root: Union[str, Path]) -> Tuple[Optional[str], List[str]]:
    """检测本地目录是否为 git 仓库，并获取当前活跃分支及所有可用分支列表。

    返回: (current_branch, [all_branches])
    若非 git 目录，返回 (None, [])。
    """
    try:
        p = Path(root).expanduser().resolve()
        if not p.is_dir():
            return None, []
        git_target = p / ".git"
        if not git_target.exists():
            return None, []

        head_file: Optional[Path] = None
        git_dir: Optional[Path] = None
        if git_target.is_dir():
            git_dir = git_target
            head_file = git_target / "HEAD"
        elif git_target.is_file():
            content = git_target.read_text(encoding="utf-8", errors="ignore").strip()
            if content.startswith("gitdir:"):
                raw_dir = content.split(":", 1)[1].strip()
                git_dir = (p / raw_dir).resolve()
                head_file = git_dir / "HEAD"

        current_branch: Optional[str] = None
        if head_file and head_file.is_file():
            head_content = head_file.read_text(encoding="utf-8", errors="ignore").strip()
            if head_content.startswith("ref: refs/heads/"):
                current_branch = head_content[len("ref: refs/heads/"):].strip()
            elif head_content.startswith("ref:"):
                current_branch = head_content.split("/")[-1].strip()

        branch_set = set()
        if current_branch:
            branch_set.add(current_branch)

        if git_dir and git_dir.is_dir():
            heads_dir = git_dir / "refs" / "heads"
            if heads_dir.is_dir():
                for f in heads_dir.rglob("*"):
                    if f.is_file():
                        rel = str(f.relative_to(heads_dir)).replace("\\", "/")
                        if rel and rel not in ("origin", "upstream", "HEAD"):
                            branch_set.add(rel)

            remotes_dir = git_dir / "refs" / "remotes"
            if remotes_dir.is_dir():
                for remote in remotes_dir.iterdir():
                    if remote.is_dir():
                        for f in remote.rglob("*"):
                            if f.is_file():
                                b_name = str(f.relative_to(remote)).replace("\\", "/")
                                if b_name and b_name not in ("origin", "upstream", "HEAD") and not b_name.endswith("/HEAD"):
                                    branch_set.add(b_name)

            packed = git_dir / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith(("#", "^")):
                        parts = line.split()
                        if len(parts) >= 2:
                            ref = parts[1]
                            if ref.startswith("refs/heads/"):
                                b = ref[len("refs/heads/"):]
                                if b and b not in ("origin", "upstream", "HEAD"):
                                    branch_set.add(b)
                            elif ref.startswith("refs/remotes/"):
                                r_parts = ref[len("refs/remotes/"):].split("/", 1)
                                if len(r_parts) == 2 and r_parts[1] not in ("origin", "upstream", "HEAD") and not r_parts[1].endswith("/HEAD"):
                                    branch_set.add(r_parts[1])

        res = subprocess.run(
            ["git", "-C", str(p), "branch", "-a", "--format=%(refname:short)"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                b = line.strip()
                if not b or b.startswith("(") or b in ("origin", "upstream", "HEAD") or "/HEAD" in b:
                    continue
                if b.startswith("origin/"):
                    b = b[len("origin/"):]
                branch_set.add(b)

        all_branches = sorted(branch_set)
        if current_branch and current_branch in all_branches:
            all_branches.remove(current_branch)
            all_branches.insert(0, current_branch)
        elif not current_branch and all_branches:
            current_branch = all_branches[0]

        return current_branch, all_branches
    except Exception:
        pass

    return None, []


def detect_git_branch(root: Union[str, Path]) -> Optional[str]:
    """检测本地目录是否为 git 仓库，并获取当前所在分支名称。若非 git 目录则返回 None。"""
    curr, _ = list_git_branches(root)
    return curr

# 跳过常见噪音目录
SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "target",
    ".idea",
    ".vscode",
}


class LocalFsBackend(RepoBackend):
    def __init__(self, root: Union[str, Path]):
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"本地路径不存在: {self.root}")
        if not self.root.is_dir():
            raise NotADirectoryError(f"不是目录: {self.root}")

    def _safe_join(self, relative: str) -> Path:
        """防止路径逃逸：resolve 后必须仍在 root 下。"""
        rel = (relative or "").lstrip("/").replace("\\", "/")
        target = (self.root / rel).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(f"路径越界，拒绝访问: {relative}") from exc
        return target

    def meta(self) -> RepoMeta:
        has_readme = any(
            (self.root / name).is_file()
            for name in ("README.md", "README.rst", "README.txt", "README")
        )
        branch = detect_git_branch(self.root)
        extra = {"root": str(self.root)}
        if branch:
            extra["git_branch"] = branch
        return RepoMeta(
            source="local",
            identifier=str(self.root),
            has_readme=has_readme,
            extra=extra,
        )

    def list_tree(
        self,
        path: str = "",
        max_depth: int = 3,
        max_entries: int = 200,
    ) -> List[str]:
        base = self._safe_join(path) if path else self.root
        if not base.exists():
            return [f"[error] path not found: {path}"]
        if not base.is_dir():
            return [str(Path(path).as_posix())]

        entries: List[str] = []
        base_depth = len(base.parts)

        for dirpath, dirnames, filenames in os.walk(base):
            current = Path(dirpath)
            depth = len(current.parts) - base_depth
            # 原地过滤跳过目录
            dirnames[:] = sorted(
                d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
            )
            if depth >= max_depth:
                dirnames[:] = []
                continue

            rel_dir = current.relative_to(self.root).as_posix()
            if rel_dir == ".":
                rel_dir = ""

            for d in dirnames:
                rel = f"{rel_dir}/{d}/" if rel_dir else f"{d}/"
                entries.append(rel)
                if len(entries) >= max_entries:
                    entries.append(f"... truncated at {max_entries} entries")
                    return entries

            for f in sorted(filenames):
                if f.startswith(".") and f not in (".env.example", ".gitignore"):
                    continue
                rel = f"{rel_dir}/{f}" if rel_dir else f
                entries.append(rel)
                if len(entries) >= max_entries:
                    entries.append(f"... truncated at {max_entries} entries")
                    return entries

        return entries

    def read_file(self, path: str, max_bytes: int = 30_000) -> FileReadResult:
        try:
            target = self._safe_join(path)
        except PermissionError as exc:
            return FileReadResult(path=path, content="", error=str(exc))

        if not target.exists():
            return FileReadResult(path=path, content="", error="file not found")
        if not target.is_file():
            return FileReadResult(path=path, content="", error="not a file")

        try:
            data = target.read_bytes()
        except OSError as exc:
            return FileReadResult(path=path, content="", error=str(exc))

        size = len(data)
        truncated = size > max_bytes
        if truncated:
            data = data[:max_bytes]

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = data.decode("latin-1")
            except Exception:
                return FileReadResult(
                    path=path,
                    content="",
                    size_bytes=size,
                    error="binary or undecodable file",
                )

        return FileReadResult(
            path=path,
            content=text,
            truncated=truncated,
            size_bytes=size,
        )

    def search(self, pattern: str, max_hits: int = 20) -> List[str]:
        if not pattern:
            return []
        needle = pattern.lower()
        hits: List[str] = []
        # 扩大 depth 以便搜索
        for entry in self.list_tree(max_depth=8, max_entries=2000):
            if entry.startswith("...") or entry.startswith("["):
                continue
            if needle in entry.lower():
                hits.append(entry)
                if len(hits) >= max_hits:
                    break
        return hits

    def write_file(self, path: str, content: str) -> None:
        """写入 UTF-8 文本；自动创建父目录；路径必须在 root 内。

        使用 write_bytes，避免 Windows 文本模式把 \\n 转成 \\r\\n。
        """
        target = self._safe_join(path)
        if target.exists() and target.is_dir():
            raise IsADirectoryError(f"目标是目录，无法写入文件: {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        data = (content if content is not None else "").encode("utf-8")
        target.write_bytes(data)

    def delete_file(self, path: str) -> None:
        target = self._safe_join(path)
        if not target.exists():
            return
        if target.is_dir():
            raise IsADirectoryError(f"目标是目录，无法删除: {path}")
        target.unlink()
