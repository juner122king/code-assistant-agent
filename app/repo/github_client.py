"""GitHub API 仓库后端（轻量，不完整 clone）。"""

from __future__ import annotations

import base64
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.repo.base import FileReadResult, RepoBackend, RepoMeta

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REPO_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/"
    r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def parse_github_url(url: str) -> Tuple[str, str]:
    """从 GitHub URL 解析 owner/repo。"""
    cleaned = url.strip()
    m = REPO_URL_RE.match(cleaned)
    if m:
        return m.group("owner"), m.group("repo")
    # 兼容 owner/repo 简写
    parts = cleaned.strip("/").split("/")
    if len(parts) == 2 and "github.com" not in cleaned:
        name = parts[1]
        if name.endswith(".git"):
            name = name[:-4]
        return parts[0], name
    raise ValueError(f"无法解析 GitHub 仓库 URL: {url}")


class GitHubBackend(RepoBackend):
    def __init__(
        self,
        owner: str,
        repo: str,
        token: str = "",
        branch: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self._token = token
        self._timeout = timeout
        self._tree_cache: Optional[List[Dict[str, Any]]] = None
        self._repo_info: Optional[Dict[str, Any]] = None

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "code-assistant-agent",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=GITHUB_API,
            headers=headers,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubBackend":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _get(self, path: str, **params: Any) -> Any:
        resp = self._client.get(path, params=params or None)
        if resp.status_code == 404:
            raise FileNotFoundError(f"GitHub 资源不存在: {path}")
        if resp.status_code == 403:
            raise PermissionError(
                f"GitHub API 拒绝访问 (可能 rate limit 或私有仓需 token): {resp.text[:200]}"
            )
        resp.raise_for_status()
        return resp.json()

    def _load_repo_info(self) -> Dict[str, Any]:
        if self._repo_info is None:
            self._repo_info = self._get(f"/repos/{self.owner}/{self.repo}")
            if not self.branch:
                self.branch = self._repo_info.get("default_branch") or "main"
        return self._repo_info

    def _load_tree(self) -> List[Dict[str, Any]]:
        if self._tree_cache is not None:
            return self._tree_cache
        info = self._load_repo_info()
        branch = self.branch or info.get("default_branch") or "main"
        # 获取分支 tip commit 的 tree
        ref = self._get(f"/repos/{self.owner}/{self.repo}/git/ref/heads/{branch}")
        commit_sha = ref["object"]["sha"]
        commit = self._get(f"/repos/{self.owner}/{self.repo}/git/commits/{commit_sha}")
        tree_sha = commit["tree"]["sha"]
        tree = self._get(
            f"/repos/{self.owner}/{self.repo}/git/trees/{tree_sha}",
            recursive="1",
        )
        self._tree_cache = tree.get("tree") or []
        if tree.get("truncated"):
            logger.warning("GitHub tree 被 API 截断（超大仓库）")
        return self._tree_cache

    def meta(self) -> RepoMeta:
        info = self._load_repo_info()
        tree = self._load_tree()
        has_readme = any(
            (item.get("path") or "").lower() in {
                "readme.md",
                "readme.rst",
                "readme.txt",
                "readme",
            }
            for item in tree
            if item.get("type") == "blob"
        )
        return RepoMeta(
            source="github",
            identifier=f"{self.owner}/{self.repo}",
            default_branch=info.get("default_branch"),
            description=info.get("description"),
            language=info.get("language"),
            has_readme=has_readme,
            extra={
                "stars": info.get("stargazers_count"),
                "html_url": info.get("html_url"),
                "private": info.get("private"),
            },
        )

    def list_tree(
        self,
        path: str = "",
        max_depth: int = 3,
        max_entries: int = 200,
    ) -> List[str]:
        prefix = (path or "").strip("/").replace("\\", "/")
        if prefix:
            prefix = prefix + "/"

        entries: List[str] = []
        seen_dirs: set[str] = set()

        for item in self._load_tree():
            p = item.get("path") or ""
            if prefix and not p.startswith(prefix):
                continue
            rel = p[len(prefix) :] if prefix else p
            if not rel:
                continue
            depth = rel.count("/") + (0 if item.get("type") == "blob" else 1)
            # 用路径段数控制深度
            segments = rel.strip("/").split("/")
            if item.get("type") == "tree":
                if len(segments) > max_depth:
                    continue
                display = rel if rel.endswith("/") else rel + "/"
                # 只展示不超过 max_depth 的目录
                if len(segments) <= max_depth and display not in seen_dirs:
                    seen_dirs.add(display)
                    entries.append(display)
            else:
                if len(segments) > max_depth:
                    continue
                entries.append(rel)

            if len(entries) >= max_entries:
                entries.append(f"... truncated at {max_entries} entries")
                break

        return entries

    def read_file(self, path: str, max_bytes: int = 30_000) -> FileReadResult:
        clean = (path or "").lstrip("/").replace("\\", "/")
        if ".." in clean.split("/"):
            return FileReadResult(path=path, content="", error="invalid path")
        try:
            data = self._get(
                f"/repos/{self.owner}/{self.repo}/contents/{clean}",
                ref=self.branch or "",
            )
        except FileNotFoundError:
            return FileReadResult(path=path, content="", error="file not found")
        except Exception as exc:
            return FileReadResult(path=path, content="", error=str(exc))

        if isinstance(data, list):
            return FileReadResult(path=path, content="", error="path is a directory")

        if data.get("encoding") == "base64" and data.get("content"):
            raw = base64.b64decode(data["content"])
        elif data.get("download_url"):
            r = self._client.get(data["download_url"])
            r.raise_for_status()
            raw = r.content
        else:
            return FileReadResult(path=path, content="", error="empty or unsupported content")

        size = len(raw)
        truncated = size > max_bytes
        if truncated:
            raw = raw[:max_bytes]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("latin-1")
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
        for item in self._load_tree():
            p = item.get("path") or ""
            if item.get("type") != "blob":
                continue
            if needle in p.lower():
                hits.append(p)
                if len(hits) >= max_hits:
                    break
        return hits

    def _post(self, path: str, json_body: Dict[str, Any]) -> Any:
        resp = self._client.post(path, json=json_body)
        if resp.status_code == 403:
            raise PermissionError(
                f"GitHub API 拒绝写入 (检查 token 权限): {resp.text[:300]}"
            )
        if resp.status_code == 404:
            raise FileNotFoundError(f"GitHub 资源不存在: {path}")
        if resp.status_code >= 400:
            raise RuntimeError(
                f"GitHub API 错误 {resp.status_code}: {resp.text[:400]}"
            )
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def create_pull_request(
        self,
        *,
        changes: List[Any],
        title: str,
        body: str = "",
        branch_name: Optional[str] = None,
        base_branch: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """无 clone：blob → tree → commit → ref → pull。

        changes: 含 path / action / proposed 的对象列表（如 FileChange）。
        """
        if not self._token:
            raise PermissionError("创建 PR 需要 GITHUB_TOKEN")
        if not changes:
            raise ValueError("changes 为空")

        info = self._load_repo_info()
        base = base_branch or self.branch or info.get("default_branch") or "main"

        ref = self._get(f"/repos/{self.owner}/{self.repo}/git/ref/heads/{base}")
        base_commit_sha = ref["object"]["sha"]
        commit = self._get(
            f"/repos/{self.owner}/{self.repo}/git/commits/{base_commit_sha}"
        )
        base_tree_sha = commit["tree"]["sha"]

        tree_items: List[Dict[str, Any]] = []
        for ch in changes:
            path = getattr(ch, "path", None) or (ch.get("path") if isinstance(ch, dict) else None)
            action = getattr(ch, "action", None) or (
                ch.get("action") if isinstance(ch, dict) else "modify"
            )
            proposed = getattr(ch, "proposed", None)
            if proposed is None and isinstance(ch, dict):
                proposed = ch.get("proposed") or ""
            path = (path or "").lstrip("/").replace("\\", "/")
            if not path or ".." in path.split("/"):
                continue
            action = (action or "modify").lower()
            if action == "delete":
                tree_items.append(
                    {
                        "path": path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": None,
                    }
                )
            else:
                blob = self._post(
                    f"/repos/{self.owner}/{self.repo}/git/blobs",
                    {
                        "content": proposed or "",
                        "encoding": "utf-8",
                    },
                )
                tree_items.append(
                    {
                        "path": path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob["sha"],
                    }
                )

        if not tree_items:
            raise ValueError("没有有效的文件变更可提交")

        new_tree = self._post(
            f"/repos/{self.owner}/{self.repo}/git/trees",
            {
                "base_tree": base_tree_sha,
                "tree": tree_items,
            },
        )

        msg = commit_message or title or "fix: automated patch"
        new_commit = self._post(
            f"/repos/{self.owner}/{self.repo}/git/commits",
            {
                "message": msg,
                "tree": new_tree["sha"],
                "parents": [base_commit_sha],
            },
        )

        if not branch_name:
            slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", (title or "fix")[:40]).strip("-").lower()
            if not slug:
                slug = "fix"
            branch_name = f"fix/{slug}-{uuid.uuid4().hex[:8]}"
        # 确保分支名合法
        branch_name = branch_name.lstrip("/").replace(" ", "-")

        try:
            self._post(
                f"/repos/{self.owner}/{self.repo}/git/refs",
                {
                    "ref": f"refs/heads/{branch_name}",
                    "sha": new_commit["sha"],
                },
            )
        except RuntimeError as exc:
            # 分支已存在时追加后缀重试一次
            if "422" in str(exc) or "Reference already exists" in str(exc):
                branch_name = f"{branch_name}-{int(time.time()) % 10000}"
                self._post(
                    f"/repos/{self.owner}/{self.repo}/git/refs",
                    {
                        "ref": f"refs/heads/{branch_name}",
                        "sha": new_commit["sha"],
                    },
                )
            else:
                raise

        pr = self._post(
            f"/repos/{self.owner}/{self.repo}/pulls",
            {
                "title": title,
                "head": branch_name,
                "base": base,
                "body": body or "",
            },
        )
        return {
            "html_url": pr.get("html_url") or "",
            "number": pr.get("number") or 0,
            "branch": branch_name,
            "commit_sha": new_commit.get("sha"),
        }
