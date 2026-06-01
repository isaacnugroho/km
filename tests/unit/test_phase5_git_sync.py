"""Phase 5 tests: git sync, inheritance, merge policies, export-case."""

from __future__ import annotations

import subprocess
from pathlib import Path

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.infrastructure.config.models import BranchMergePolicy
from km.infrastructure.git.context import read_git_context
from km.infrastructure.git.merge_base import detect_parent_branch
from tests.fixtures_data import SAMPLE_CASE_TURTLE


def _checkout(ws: Path, branch: str, *, create: bool = False) -> None:
    if create:
        subprocess.run(["git", "checkout", "-b", branch], cwd=ws, check=True, capture_output=True)
    else:
        subprocess.run(["git", "checkout", branch], cwd=ws, check=True, capture_output=True)


def test_git_context_refresh_on_branch_switch(tmp_workspace: Path) -> None:
    _checkout(tmp_workspace, "feature/test", create=True)
    ctx = read_git_context(tmp_workspace)
    assert ctx.branch_path == "feature/test"
    assert ctx.graph_uri == "http://km.local/graphs/feature-test"


def test_detect_parent_branch_from_reflog(tmp_workspace: Path) -> None:
    _checkout(tmp_workspace, "feature/child", create=True)
    parent = detect_parent_branch(tmp_workspace, "feature/child")
    assert parent == "main"


def test_branch_inheritance_clones_parent_graph(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        _checkout(tmp_workspace, "feature/inherited", create=True)
        app.git.refresh()
        copied = app.branch_inheritance.ensure_inherited(app.git, tmp_workspace)
        assert copied == 1
        content = app.case_ingest.serialize_active_graph(app.git_context)
        assert "my_core" in content
    finally:
        app.shutdown()


def test_auto_merge_copies_all_facts(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        _checkout(tmp_workspace, "feature/auto", create=True)
        app.git.refresh()
        app.branch_inheritance.ensure_inherited(app.git, tmp_workspace)
        mcp_tools.handle_ingest_case_facts(
            app,
            """
            @prefix app: <http://app.local/test#> .
            app:featureNode app:marker "feature-only" .
            """,
            "turtle",
        )
        result = app.merge_resolver.handle_merge(
            "feature/auto",
            "main",
            BranchMergePolicy.AUTO_MERGE,
            event_fingerprint="test-auto",
        )
        assert result is not None
        assert result.triples_imported >= 1
        from km.infrastructure.git.context import _context_from_branch

        main_graph = app.case_ingest.serialize_active_graph(_context_from_branch("main"))
        assert "feature-only" in main_graph
        gov_files = list((tmp_workspace / "case-exports" / "governance").glob("*.ttl"))
        assert gov_files
    finally:
        app.shutdown()


def test_auto_merge_exception_prompt_and_merge_resolve(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        propose = mcp_tools.handle_propose_local_exception(
            app,
            "http://architecture.org/hexagonal#AdapterDependencyShape",
            "http://app.local/test#node",
            "test exception",
        )
        mcp_tools.handle_approve_local_exception(
            app, propose["exception_id"], "dev", "signed"
        )
        _checkout(tmp_workspace, "feature/partial", create=True)
        app.git.refresh()
        app.branch_inheritance.ensure_inherited(app.git, tmp_workspace)
        mcp_tools.handle_ingest_case_facts(
            app,
            """
            @prefix app: <http://app.local/test#> .
            app:extraFact app:marker "pending-merge" .
            """,
            "turtle",
        )
        result = app.merge_resolver.handle_merge(
            "feature/partial",
            "main",
            BranchMergePolicy.AUTO_MERGE_EXCEPTION,
            event_fingerprint="test-partial",
        )
        assert result is not None
        assert result.prompt_written is True
        prompt_path = tmp_workspace / ".km" / f"pending-merge-{result.event_id}.json"
        assert prompt_path.is_file()

        resolved = app.merge_resolver.resolve_prompt(result.event_id, "MERGE")
        assert resolved["resolution"] == "MERGE"
        assert resolved["triples_imported"] >= 1
        assert not prompt_path.is_file()
    finally:
        app.shutdown()


def test_git_watcher_handle_change_runs_inheritance(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        _checkout(tmp_workspace, "feature/watcher", create=True)
        app.git_watcher.handle_git_change()
        content = app.case_ingest.serialize_active_graph(app.git_context)
        assert "my_core" in content
    finally:
        app.shutdown()
