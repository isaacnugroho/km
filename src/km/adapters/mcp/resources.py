"""MCP resource handlers."""

from __future__ import annotations

from km.application.bootstrap import KMApplication
from km.application.services.feature_gate import require_implemented
from km.logging_config import get_logger

logger = get_logger("mcp.resources")

RESOURCE_URIS = [
    "km://schemas/learning-ontologies",
    "km://case/active-graph",
    "km://case/active-exceptions",
]


def read_resource(app: KMApplication, uri: str) -> tuple[str, str]:
    """Return (content, mime_type) for a km:// resource URI."""
    logger.debug("Resource read: %s", uri)

    if uri == "km://schemas/learning-ontologies":
        require_implemented("resource:schemas/learning-ontologies")
        return "{}", "application/ld+json"

    if uri == "km://case/active-graph":
        require_implemented("resource:case/active-graph")
        return "", "text/turtle"

    if uri == "km://case/active-exceptions":
        require_implemented("resource:case/active-exceptions")
        return "[]", "application/json"

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
