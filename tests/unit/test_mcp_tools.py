"""Unit tests for MCP tool handlers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.exceptions import FeatureNotImplementedError
from km.infrastructure.config.models import BranchMergePolicy
from tests.fixtures_data import SAMPLE_CASE_TURTLE


def test_handle_status(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_status(app)
        assert result["active_branch"] == "main"
        assert len(result["learning_ontologies"]) == 1
        assert result["pending_branch_merges"] == []
    finally:
        app.shutdown()


def test_handle_export_case(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        result = mcp_tools.handle_export_case(app)
        assert result["status"] == "success"
        export_path = tmp_workspace / "case-exports" / "graphs" / "refs-heads-main.ttl"
        assert Path(result["export_path"]) == export_path
        assert export_path.is_file()
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


def test_handle_validate_bindings(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_validate_bindings(app)
        assert result["valid"] is True
        assert len(result["bindings"]) == 1
        assert result["bindings"][0]["ontology_id"] == "hexagonal-architecture"
        assert result["errors"] == []
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


def test_handle_sync_pending_branch_merges_and_resolve(tmp_workspace: Path) -> None:
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
        synced = mcp_tools.handle_sync_pending_branch_merges(
            app,
            "feature/mcp-merge",
            "main",
            event_fingerprint="mcp-test",
        )
        assert synced["status"] == "PENDING_RESOLUTION"
        assert synced["approval_command"].startswith("resolve_branch_merge ")
        event_id = synced["event_id"]

        resolved = mcp_tools.handle_resolve_branch_merge(app, event_id, "MERGE")
        assert resolved["status"] == "success"
        assert resolved["resolution"] == "MERGE"
        assert resolved["triples_imported"] >= 1
        assert app.get_system_status().pending_branch_merges_count == 0
    finally:
        app.shutdown()


def test_sync_pending_branch_merges_already_synced_after_restart(tmp_workspace: Path) -> None:
    event_fingerprint = "persist-test"
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        subprocess.run(
            ["git", "checkout", "-b", "feature/persist"],
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
            app:branchFact app:marker "persist" .
            """,
            "turtle",
        )
        first = mcp_tools.handle_sync_pending_branch_merges(
            app,
            "feature/persist",
            "main",
            event_fingerprint=event_fingerprint,
        )
        assert first["status"] == "PENDING_RESOLUTION"
        event_id = first["event_id"]
        gov_before = list((tmp_workspace / "case-exports" / "governance").glob("*.ttl"))
    finally:
        app.shutdown()

    app2 = KMApplication.bootstrap(tmp_workspace)
    try:
        again = mcp_tools.handle_sync_pending_branch_merges(
            app2,
            "feature/persist",
            "main",
            event_fingerprint=event_fingerprint,
        )
        assert again["status"] == "PENDING_RESOLUTION"
        assert again["event_id"] == event_id

        mcp_tools.handle_resolve_branch_merge(app2, event_id, "MERGE")
    finally:
        app2.shutdown()

    app3 = KMApplication.bootstrap(tmp_workspace)
    try:
        synced = mcp_tools.handle_sync_pending_branch_merges(
            app3,
            "feature/persist",
            "main",
            event_fingerprint=event_fingerprint,
        )
        assert synced["status"] == "ALREADY_SYNCED"
        gov_after = list((tmp_workspace / "case-exports" / "governance").glob("*.ttl"))
        assert len(gov_after) == len(gov_before)
    finally:
        app3.shutdown()


def test_handle_propose_mr_read_only_rejected(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        from km.exceptions import PermissionError

        with pytest.raises(PermissionError):
            mcp_tools.handle_propose_semantic_mr(app, "hexagonal-architecture", "r", "t")
    finally:
        app.shutdown()
