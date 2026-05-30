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


def test_handle_propose_mr_read_only_rejected(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        from km.exceptions import PermissionError

        with pytest.raises(PermissionError):
            mcp_tools.handle_propose_semantic_mr(app, "hexagonal-architecture", "r", "t")
    finally:
        app.shutdown()
