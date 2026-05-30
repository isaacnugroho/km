"""Unit tests for MCP tool handlers."""

from __future__ import annotations

from pathlib import Path

import pytest

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.exceptions import FeatureNotImplementedError


def test_handle_get_system_status(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_get_system_status(app)
        assert result["active_branch"] == "main"
        assert len(result["learning_ontologies"]) == 1
    finally:
        app.shutdown()


def test_handle_ingest_stub(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with pytest.raises(FeatureNotImplementedError, match="ingest_case_facts"):
            mcp_tools.handle_ingest_case_facts(app, "{}", "json-ld")
    finally:
        app.shutdown()
