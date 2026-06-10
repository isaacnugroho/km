"""Unit tests for git merge-base detection."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from km.infrastructure.git.merge_base import (
    detect_parent_branch,
    detect_recent_merge,
)

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "km-test",
    "GIT_AUTHOR_EMAIL": "km-test@example.com",
    "GIT_COMMITTER_NAME": "km-test",
    "GIT_COMMITTER_EMAIL": "km-test@example.com",
}


def _run_git(ws: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=ws, check=True, capture_output=True, env=_GIT_ENV)


def test_detect_parent_branch_main_returns_none(tmp_workspace: Path) -> None:
    assert detect_parent_branch(tmp_workspace, "main") is None
    assert detect_parent_branch(tmp_workspace, "master") is None


def test_detect_parent_branch_from_branch_log(tmp_workspace: Path) -> None:
    log_dir = tmp_workspace / ".git" / "logs" / "refs" / "heads" / "feature"
    log_dir.mkdir(parents=True)
    (log_dir / "child").write_text(
        "abc\tdef\tcheckout: moving from develop to feature/child\n",
        encoding="utf-8",
    )
    assert detect_parent_branch(tmp_workspace, "feature/child") == "develop"


def test_detect_parent_branch_via_git_reflog(tmp_workspace: Path) -> None:
    _run_git(tmp_workspace, "checkout", "-b", "feature/reflog-child")
    log_path = (
        tmp_workspace
        / ".git"
        / "logs"
        / "refs"
        / "heads"
        / "feature"
        / "reflog-child"
    )
    log_path.unlink(missing_ok=True)
    (tmp_workspace / ".git" / "logs" / "HEAD").write_text("", encoding="utf-8")
    assert detect_parent_branch(tmp_workspace, "feature/reflog-child") == "main"


def test_detect_parent_branch_fallback_to_master(tmp_path: Path) -> None:
    _run_git(tmp_path, "init", "-b", "master")
    _run_git(tmp_path, "commit", "--allow-empty", "-m", "init")
    _run_git(tmp_path, "branch", "orphan-feature")
    assert detect_parent_branch(tmp_path, "orphan-feature") == "master"


def test_detect_recent_merge_from_reflog(tmp_workspace: Path) -> None:
    log_path = tmp_workspace / ".git" / "logs" / "refs" / "heads" / "main"
    merge_line = "abc123\tdef456\tmerge feature/merged: Fast-forward\n"
    log_path.write_text(log_path.read_text(encoding="utf-8") + merge_line, encoding="utf-8")
    result = detect_recent_merge(tmp_workspace, "main")
    assert result is not None
    source, fingerprint = result
    assert source == "feature/merged"
    last_line = log_path.read_text(encoding="utf-8").splitlines()[-1]
    assert fingerprint == hashlib.sha256(last_line.encode("utf-8")).hexdigest()[:16]


def test_detect_recent_merge_missing_log(tmp_path: Path) -> None:
    assert detect_recent_merge(tmp_path, "main") is None
