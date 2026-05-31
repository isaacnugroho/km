"""KM MCP server entry point."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from km.adapters.mcp import resources as resource_handlers
from km.adapters.mcp import tools as tool_handlers
from km.application.bootstrap import KMApplication
from km.exceptions import as_km_error
from km.logging_config import configure_logging, get_logger

logger = get_logger("mcp.server")

mcp = FastMCP("km")


def _get_app() -> KMApplication:
    if not hasattr(_get_app, "_app"):
        try:
            _get_app._app = KMApplication.bootstrap(enable_git_watcher=True)  # type: ignore[attr-defined]
        except Exception as exc:
            normalized = as_km_error(exc)
            raise normalized if normalized is not None else exc
    return _get_app._app  # type: ignore[attr-defined]


def _handle_tool_error(exc: Exception) -> str:
    return tool_handlers.tool_error_payload(exc)


def _run_tool(handler):
    try:
        return handler()
    except Exception as exc:
        km_exc = as_km_error(exc)
        if km_exc is None:
            raise
        raise RuntimeError(_handle_tool_error(km_exc)) from km_exc


@mcp.tool()
def ingest_case_facts(facts: str, format: str = "json-ld") -> str:
    """Ingest new contextual facts into the active case branch graph."""
    result = _run_tool(lambda: tool_handlers.handle_ingest_case_facts(_get_app(), facts, format))
    return tool_handlers.json_result(result)


@mcp.tool()
def validate_constraints() -> str:
    """Run SHACL validation on the active case graph against LO canonical shapes."""
    result = _run_tool(lambda: tool_handlers.handle_validate_constraints(_get_app()))
    return tool_handlers.json_result(result)


@mcp.tool()
def propose_local_exception(bypasses_shape: str, target_node: str, rationale: str) -> str:
    """Declare a local exception to bypass a SHACL shape for a focus node."""
    result = _run_tool(
        lambda: tool_handlers.handle_propose_local_exception(
            _get_app(), bypasses_shape, target_node, rationale
        )
    )
    return tool_handlers.json_result(result)


@mcp.tool()
def approve_local_exception(exception_id: str, approver: str, signature: str) -> str:
    """Record human approval for a proposed local exception."""
    result = _run_tool(
        lambda: tool_handlers.handle_approve_local_exception(
            _get_app(), exception_id, approver, signature
        )
    )
    return tool_handlers.json_result(result)


@mcp.tool()
def query_semantic_graph(query: str) -> str:
    """Execute a read-only SPARQL query over case + LO canonical graphs."""
    result = _run_tool(lambda: tool_handlers.handle_query_semantic_graph(_get_app(), query))
    return tool_handlers.json_result(result)


@mcp.tool()
def propose_semantic_mr(
    target_ontology: str,
    rationale: str,
    diff_insertions: str,
    diff_deletions: str = "",
) -> str:
    """Create a semantic merge request in a curator-bound learning ontology."""
    result = _run_tool(
        lambda: tool_handlers.handle_propose_semantic_mr(
            _get_app(), target_ontology, rationale, diff_insertions, diff_deletions
        )
    )
    return tool_handlers.json_result(result)


@mcp.tool()
def get_system_status() -> str:
    """Return workspace environment and ontology binding status."""
    result = _run_tool(lambda: tool_handlers.handle_get_system_status(_get_app()))
    return tool_handlers.json_result(result)


@mcp.tool()
def approve_semantic_mr(doc_identifier: str) -> str:
    """Approve a pending semantic merge request by review doc path or km:// URI."""
    result = _run_tool(lambda: tool_handlers.handle_approve_semantic_mr(_get_app(), doc_identifier))
    return tool_handlers.json_result(result)


@mcp.resource("km://schemas/learning-ontologies")
def schemas_learning_ontologies() -> str:
    content, _ = resource_handlers.read_resource(_get_app(), "km://schemas/learning-ontologies")
    return content


@mcp.resource("km://case/active-graph")
def case_active_graph() -> str:
    content, _ = resource_handlers.read_resource(_get_app(), "km://case/active-graph")
    return content


@mcp.resource("km://case/active-exceptions")
def case_active_exceptions() -> str:
    content, _ = resource_handlers.read_resource(_get_app(), "km://case/active-exceptions")
    return content


@mcp.resource("km://case/active-exceptions/{exception_id}")
def case_active_exception_item(exception_id: str) -> str:
    uri = f"km://case/active-exceptions/{exception_id}"
    content, _ = resource_handlers.read_resource(_get_app(), uri)
    return content


@mcp.resource("km://learning-ontologies/{ontology_id}/canonical")
def lo_canonical(ontology_id: str) -> str:
    uri = f"km://learning-ontologies/{ontology_id}/canonical"
    content, _ = resource_handlers.read_resource(_get_app(), uri)
    return content


@mcp.resource("km://learning-ontologies/{ontology_id}/governance")
def lo_governance(ontology_id: str) -> str:
    uri = f"km://learning-ontologies/{ontology_id}/governance"
    content, _ = resource_handlers.read_resource(_get_app(), uri)
    return content


@mcp.resource("km://mr/{ontology_id}/{mr_id}")
def mr_review_doc(ontology_id: str, mr_id: str) -> str:
    uri = f"km://mr/{ontology_id}/{mr_id}"
    content, _ = resource_handlers.read_resource(_get_app(), uri)
    return content


def run_mcp_server() -> None:
    configure_logging(mcp_mode=True)
    logger.info("Starting KM MCP server (stdio)")
    mcp.run(transport="stdio")
