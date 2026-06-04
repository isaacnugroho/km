"""Integration tests for MCP server surface."""

from __future__ import annotations

from pathlib import Path

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.application.services.feature_gate import FEATURES

EXPECTED_TOOLS = {
    "ingest_case_facts",
    "validate_constraints",
    "propose_local_exception",
    "approve_local_exception",
    "query_semantic_graph",
    "propose_semantic_mr",
    "status",
    "export_case",
    "approve_semantic_mr",
    "sync_pending_branch_merges",
    "resolve_branch_merge",
}


def test_all_tool_feature_keys_registered() -> None:
    for tool in EXPECTED_TOOLS:
        assert tool in FEATURES


def test_bootstrap_and_status_integration(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_status(app)
        assert "active_branch" in result
        assert result["learning_ontologies"][0]["cache_path"]
        assert "pending_branch_merges" in result
    finally:
        app.shutdown()
