"""Phase 2 tests for case ingest, query, and export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from km.adapters.mcp import resources as resource_handlers
from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.application.services.case_export_service import CaseExportService
from km.exceptions import KmError
from km.infrastructure.rdf.ref_mapping import (
    branch_path_to_graph_uri,
    ref_to_branch_path,
    ref_to_export_filename,
)
from tests.fixtures_data import SAMPLE_CASE_JSONLD, SAMPLE_CASE_TURTLE


def test_ref_mapping_round_trip() -> None:
    ref = "refs/heads/feature/collaborative-canvas"
    assert ref_to_export_filename(ref) == "refs-heads-feature-collaborative-canvas.ttl"
    branch = ref_to_branch_path(ref)
    assert branch == "feature/collaborative-canvas"
    assert branch_path_to_graph_uri(branch) == "http://km.local/graphs/feature/collaborative-canvas"


def test_ingest_turtle(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        assert result == {"status": "success", "triples_added": 1}
    finally:
        app.shutdown()


def test_ingest_json_ld(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_JSONLD, "json-ld")
        assert result["status"] == "success"
        assert result["triples_added"] >= 1
    finally:
        app.shutdown()


def test_ingest_empty_returns_error(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_ingest_case_facts(app, "  ", "turtle")
        assert result == {"status": "error", "triples_added": 0}
    finally:
        app.shutdown()


def test_ingest_idempotent(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        first = mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        second = mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        assert first["triples_added"] == 1
        assert second["triples_added"] == 0
    finally:
        app.shutdown()


def test_ingest_on_write_exports(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        export_file = tmp_workspace_on_write / "case-exports" / "graphs" / "refs-heads-main.ttl"
        assert export_file.is_file()
        assert "http://km.local/cases/my_core" in export_file.read_text()
        assert (tmp_workspace_on_write / "case-exports" / "sync-manifest.json").is_file()
    finally:
        app.shutdown()


def test_ingest_on_commit_does_not_export(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        export_file = tmp_workspace / "case-exports" / "graphs" / "refs-heads-main.ttl"
        assert not export_file.exists()
    finally:
        app.shutdown()


def test_query_select_case_fact(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        result = mcp_tools.handle_query_semantic_graph(
            app,
            "SELECT ?s WHERE { ?s a <http://architecture.org/hexagonal#ApplicationCore> }",
        )
        values = [b["s"]["value"] for b in result["results"]["bindings"]]
        assert "http://km.local/cases/my_core" in values
    finally:
        app.shutdown()


def test_query_ask(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        result = mcp_tools.handle_query_semantic_graph(
            app,
            "ASK { <http://km.local/cases/my_core> a <http://architecture.org/hexagonal#ApplicationCore> }",
        )
        assert result["results"]["boolean"] is True
    finally:
        app.shutdown()


def test_query_union_includes_lo_classes(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_query_semantic_graph(
            app,
            "ASK { <http://architecture.org/hexagonal#ApplicationCore> a <http://www.w3.org/2002/07/owl#Class> }",
        )
        assert result["results"]["boolean"] is True
    finally:
        app.shutdown()


def test_query_rejects_insert(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with pytest.raises(KmError, match="read-only"):
            mcp_tools.handle_query_semantic_graph(
                app,
                "INSERT { ?s ?p ?o } WHERE { ?s ?p ?o }",
            )
    finally:
        app.shutdown()


def test_export_deterministic(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        path = tmp_workspace_on_write / "case-exports" / "graphs" / "refs-heads-main.ttl"
        first = path.read_bytes()
        app.case_export.export_branch(app.git_context)
        second = path.read_bytes()
        assert first == second
    finally:
        app.shutdown()


def test_bootstrap_from_exports(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
    finally:
        app.shutdown()

    app2 = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        result = mcp_tools.handle_query_semantic_graph(
            app2,
            "ASK { <http://km.local/cases/my_core> a <http://architecture.org/hexagonal#ApplicationCore> }",
        )
        assert result["results"]["boolean"] is True
    finally:
        app2.shutdown()


def test_active_graph_resource(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
        content, mime = resource_handlers.read_resource(app, "km://case/active-graph")
        assert mime == "text/turtle"
        assert "http://km.local/cases/my_core" in content
        assert "GRAPH <http://km.local/graphs/main>" in content
    finally:
        app.shutdown()
