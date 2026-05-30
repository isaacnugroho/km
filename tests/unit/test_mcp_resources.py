"""Unit tests for MCP resource handlers."""

from __future__ import annotations

from pathlib import Path

import pytest

from km.adapters.mcp import resources as resource_handlers
from km.application.bootstrap import KMApplication
from km.exceptions import FeatureNotImplementedError


@pytest.mark.parametrize(
    "uri",
    [
        "km://schemas/learning-ontologies",
        "km://case/active-graph",
        "km://case/active-exceptions",
        "km://learning-ontologies/hexagonal-architecture/canonical",
        "km://learning-ontologies/hexagonal-architecture/governance",
        "km://mr/hexagonal-architecture/MR-001",
    ],
)
def test_resource_stubs_raise(tmp_workspace: Path, uri: str) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with pytest.raises(FeatureNotImplementedError):
            resource_handlers.read_resource(app, uri)
    finally:
        app.shutdown()
