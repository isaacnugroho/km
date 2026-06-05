"""Tests for workspaces without Learning Ontology bindings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication


@pytest.fixture
def tmp_workspace_no_lo(tmp_path: Path) -> Path:
    from tests.conftest import _init_git_repo

    ws = tmp_path / "workspace_no_lo"
    ws.mkdir()
    _init_git_repo(ws)
    km_dir = ws / ".km"
    km_dir.mkdir()
    config = {
        "workspace_id": "test-workspace-no-lo",
        "learning_ontologies": [],
        "lo_cache": {"base_path": "./.km/lo-cache"},
        "case_exports": {"base_path": "./case-exports", "export_policy": "on_commit"},
        "branch_merge": {"policy": "auto_merge_exception"},
    }
    (km_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (ws / "case-exports" / "graphs").mkdir(parents=True)
    (ws / "case-exports" / "governance").mkdir(parents=True)
    return ws


def test_bootstrap_no_lo_workspace(tmp_workspace_no_lo: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_no_lo)
    try:
        status = mcp_tools.handle_status(app)
        assert status["learning_ontologies"] == []
    finally:
        app.shutdown()


def test_validate_constraints_without_lo_shapes(tmp_workspace_no_lo: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_no_lo)
    try:
        result = mcp_tools.handle_validate_constraints(app)
        assert result["conforms"] is True
        assert result["violations"] == []
    finally:
        app.shutdown()


def test_ingest_and_query_case_facts_without_lo(tmp_workspace_no_lo: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_no_lo)
    try:
        turtle = """\
@prefix app: <http://app.local/test#> .

app:Feature a app:FeatureSpec .
"""
        ingest = mcp_tools.handle_ingest_case_facts(app, turtle, "turtle")
        assert ingest["triples_added"] > 0
        query = mcp_tools.handle_query_semantic_graph(
            app,
            "PREFIX app: <http://app.local/test#> "
            "ASK { app:Feature a app:FeatureSpec }",
        )
        assert query["results"]["boolean"] is True
    finally:
        app.shutdown()
