"""MCP resource handlers."""

from __future__ import annotations

import json

from km.application.bootstrap import KMApplication
from km.application.services.feature_gate import require_implemented
from km.logging_config import get_logger

logger = get_logger("mcp.resources")


def read_resource(app: KMApplication, uri: str) -> tuple[str, str]:
    """Return (content, mime_type) for a km:// resource URI."""
    logger.debug("Resource read: %s", uri)

    if uri == "km://schemas/learning-ontologies":
        require_implemented("resource:schemas/learning-ontologies")
        return app.schemas.to_json(), "application/ld+json"

    if uri == "km://case/active-graph":
        require_implemented("resource:case/active-graph")
        content = app.case_ingest.serialize_active_graph(app.git_context)
        return content, "text/turtle"

    if uri == "km://case/active-exceptions":
        require_implemented("resource:case/active-exceptions")
        items = app.exceptions.list_exceptions(app.git_context)
        return json.dumps(items, indent=2), "application/json"

    if uri.startswith("km://case/active-exceptions/"):
        require_implemented("resource:case/active-exceptions")
        exception_id = uri.removeprefix("km://case/active-exceptions/")
        item = app.exceptions.get_exception(exception_id, app.git_context)
        return json.dumps(item, indent=2), "application/json"

    if uri.startswith("km://learning-ontologies/") and uri.endswith("/canonical"):
        require_implemented("resource:lo/canonical")
        return "", "text/turtle"

    if uri.startswith("km://learning-ontologies/") and uri.endswith("/governance"):
        require_implemented("resource:lo/governance")
        return "", "text/turtle"

    if uri.startswith("km://mr/"):
        require_implemented("resource:mr")
        return "", "text/markdown"

    raise ValueError(f"Unknown resource URI: {uri}")
