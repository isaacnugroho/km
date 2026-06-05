"""Integration tests for MCP server surface."""

from __future__ import annotations

import json
from pathlib import Path

from km.adapters.mcp import resources as resource_handlers
from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.application.services.feature_gate import FEATURES
from tests.fixtures_data import SAMPLE_CASE_TURTLE

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

HEX = "http://architecture.org/hexagonal#"
CASE = "http://km.local/cases/"

VIOLATING_ADAPTER_TURTLE = f"""\
@prefix hex: <{HEX}> .
@prefix case: <{CASE}> .

case:api a hex:DrivingAdapter .
"""

DRIVING_ADAPTER_SHAPE = f"{HEX}DrivingAdapterInvocationShape"


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


def test_mcp_ingest_validate_query_export_loop(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        ingest = mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        assert ingest["triples_added"] > 0

        validation = mcp_tools.handle_validate_constraints(app)
        assert validation["conforms"] is True

        query = mcp_tools.handle_query_semantic_graph(
            app,
            "PREFIX case: <http://km.local/cases/> "
            "ASK { case:my_core a <http://architecture.org/hexagonal#ApplicationCore> }",
        )
        assert query["results"]["boolean"] is True

        export = mcp_tools.handle_export_case(app)
        assert export["status"] == "success"
        assert Path(export["export_path"]).is_file()
    finally:
        app.shutdown()


def test_mcp_exception_loop(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        failed = mcp_tools.handle_validate_constraints(app)
        assert failed["conforms"] is False

        proposed = mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}api",
            "Integration test bypass",
        )
        mcp_tools.handle_approve_local_exception(
            app,
            proposed["exception_id"],
            "integration-dev",
            "sig_integration",
        )
        passed = mcp_tools.handle_validate_constraints(app)
        assert passed["conforms"] is True
    finally:
        app.shutdown()


def test_schemas_resource_integration(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        content, mime = resource_handlers.read_resource(app, "km://schemas/learning-ontologies")
        assert mime == "application/ld+json"
        doc = json.loads(content)
        assert doc["learning_ontologies"]
        assert doc["learning_ontologies"][0]["ontology_id"] == "hexagonal-architecture"
    finally:
        app.shutdown()
