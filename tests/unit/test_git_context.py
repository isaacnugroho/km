"""Unit tests for git context."""

from __future__ import annotations

from pathlib import Path

from km.infrastructure.git.context import read_git_context


def test_branch_ref_maps_to_graph_uri(tmp_workspace: Path) -> None:
    ctx = read_git_context(tmp_workspace)
    assert ctx.branch_path == "main"
    assert ctx.graph_uri == "http://km.local/graphs/main"


def test_feature_branch_ref(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    refs_dir = git_dir / "refs" / "heads" / "feature"
    refs_dir.mkdir(parents=True)
    (refs_dir / "foo").write_text("abc123\n", encoding="utf-8")
    (git_dir / "HEAD").write_text("ref: refs/heads/feature/foo\n", encoding="utf-8")

    ctx = read_git_context(tmp_path)
    assert ctx.branch_path == "feature/foo"
    assert ctx.graph_uri == "http://km.local/graphs/feature/foo"


def test_no_git_defaults_to_main(tmp_path: Path) -> None:
    ctx = read_git_context(tmp_path)
    assert ctx.branch_path == "main"
