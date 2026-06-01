"""Unit tests for MCP tool handlers."""

from __future__ import annotations

from pathlib import Path

import pytest

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.exceptions import FeatureNotImplementedError
from tests.fixtures_data import SAMPLE_CASE_TURTLE


def test_handle_get_system_status(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_get_system_status(app)
        assert result["active_branch"] == "main"
        assert len(result["learning_ontologies"]) == 1
    finally:
        app.shutdown()


def test_handle_ingest_success(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        assert result["status"] == "success"
        assert result["triples_added"] == 1
    finally:
        app.shutdown()


def test_handle_validate_constraints(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_validate_constraints(app)
        assert result["conforms"] is True
        assert result["violations"] == []
    finally:
        app.shutdown()


def test_handle_propose_branch_merge_and_resolve(tmp_workspace: Path) -> None:
    import subprocess

    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        subprocess.run(
            ["git", "checkout", "-b", "feature/mcp-merge"],
            cwd=tmp_workspace,
            check=True,
            capture_output=True,
        )
        app.git.refresh()
        app.branch_inheritance.ensure_inherited(app.git, tmp_workspace)
        mcp_tools.handle_ingest_case_facts(
            app,
            """
            @prefix app: <http://app.local/test#> .
            app:extraFact app:marker "mcp-merge" .
            """,
            "turtle",
        )
        proposed = mcp_tools.handle_propose_branch_merge(
            app,
            "feature/mcp-merge",
            "main",
            event_fingerprint="mcp-test",
        )
        assert proposed["status"] == "PENDING_RESOLUTION"
        assert proposed["approval_command"].startswith("resolve_branch_merge ")
        event_id = proposed["event_id"]

        resolved = mcp_tools.handle_resolve_branch_merge(app, event_id, "MERGE")
        assert resolved["status"] == "success"
        assert resolved["resolution"] == "MERGE"
        assert resolved["triples_imported"] >= 1
        assert app.get_system_status().pending_branch_merges_count == 0
    finally:
        app.shutdown()


def test_handle_propose_mr_read_only_rejected(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        from km.exceptions import PermissionError

        with pytest.raises(PermissionError):
            mcp_tools.handle_propose_semantic_mr(app, "hexagonal-architecture", "r", "t")
    finally:
        app.shutdown()
