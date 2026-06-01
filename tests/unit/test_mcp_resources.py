"""Unit tests for MCP resource handlers."""

from __future__ import annotations

from pathlib import Path

import pytest

from km.adapters.mcp import resources as resource_handlers
from km.application.bootstrap import KMApplication
from tests.fixtures_data import SAMPLE_CASE_TURTLE


def test_schemas_resource_implemented(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        content, mime = resource_handlers.read_resource(app, "km://schemas/learning-ontologies")
        assert mime == "application/ld+json"
        assert "learning_ontologies" in content
    finally:
        app.shutdown()


def test_active_graph_resource_not_stub(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        from km.adapters.mcp import tools as mcp_tools

        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        content, mime = resource_handlers.read_resource(app, "km://case/active-graph")
        assert mime == "text/turtle"
        assert "my_core" in content
    finally:
        app.shutdown()


def test_lo_canonical_resource(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        content, mime = resource_handlers.read_resource(
            app, "km://learning-ontologies/hexagonal-architecture/canonical"
        )
        assert mime == "text/turtle"
        assert "hex:ApplicationCore" in content
        assert "GRAPH <http://km.local/learning-ontologies/hexagonal-architecture/canonical>" in content
    finally:
        app.shutdown()


def test_lo_governance_resource_empty_graph(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        content, mime = resource_handlers.read_resource(
            app, "km://learning-ontologies/hexagonal-architecture/governance"
        )
        assert mime == "text/turtle"
        assert "http://km.local/learning-ontologies/hexagonal-architecture/governance" in content
    finally:
        app.shutdown()


def test_pending_merges_resource(tmp_workspace: Path) -> None:
    import subprocess

    from km.adapters.mcp import tools as mcp_tools

    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        subprocess.run(
            ["git", "checkout", "-b", "feature/res"],
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
            app:resFact app:marker "res-merge" .
            """,
            "turtle",
        )
        proposed = mcp_tools.handle_propose_branch_merge(
            app, "feature/res", "main", event_fingerprint="res-test"
        )
        event_id = proposed["event_id"]

        list_content, list_mime = resource_handlers.read_resource(
            app, "km://case/pending-merges"
        )
        assert list_mime == "application/json"
        assert event_id in list_content

        item_content, item_mime = resource_handlers.read_resource(
            app, f"km://case/pending-merges/{event_id}"
        )
        assert item_mime == "application/json"
        assert proposed["source_branch"] in item_content
    finally:
        app.shutdown()


def test_lo_governance_resource_includes_export_shard(
    tmp_workspace: Path, lo_package: Path
) -> None:
    gov_graph = "http://km.local/learning-ontologies/hexagonal-architecture/governance"
    shard = lo_package / "exports" / "governance" / "MR-TEST-001.ttl"
    shard.write_text(
        f"""@prefix km: <http://km.local/governance#> .

GRAPH <{gov_graph}> {{
    km:MR-TEST-001 a km:SemanticMergeRequest ;
        km:status "PENDING_APPROVAL" .
}}
""",
        encoding="utf-8",
    )
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        content, mime = resource_handlers.read_resource(
            app, "km://learning-ontologies/hexagonal-architecture/governance"
        )
        assert mime == "text/turtle"
        assert "MR-TEST-001" in content
        assert "PENDING_APPROVAL" in content
    finally:
        app.shutdown()
