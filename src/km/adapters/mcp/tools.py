"""MCP tool handlers."""

from __future__ import annotations

import json
from typing import Any

from km.application.bootstrap import KMApplication
from km.application.services.feature_gate import require_implemented
from km.application.services.merge_resolver_service import default_target_branch
from km.exceptions import FeatureNotImplementedError, KmError, as_km_error
from km.logging_config import get_logger

logger = get_logger("mcp.tools")


def handle_status(app: KMApplication) -> dict[str, Any]:
    require_implemented("status")
    status = app.get_system_status()
    return status.to_dict()


def handle_validate_bindings(app: KMApplication) -> dict[str, Any]:
    require_implemented("validate_bindings")
    return app.workspace.binding_report()


def handle_export_case(app: KMApplication) -> dict[str, Any]:
    require_implemented("export_case")
    export_path = app.case_export.export_active(app.git_context)
    return {"status": "success", "export_path": str(export_path)}


def handle_ingest_case_facts(
    app: KMApplication, facts: str, format: str = "json-ld"
) -> dict[str, Any]:
    require_implemented("ingest_case_facts")
    logger.debug("ingest_case_facts format=%s", format)
    return app.case_ingest.ingest(facts, format, app.git_context)


def handle_validate_constraints(app: KMApplication) -> dict[str, Any]:
    require_implemented("validate_constraints")
    return app.validation.validate_constraints(app.git_context)


def handle_propose_local_exception(
    app: KMApplication,
    bypasses_shape: str,
    target_node: str,
    rationale: str,
) -> dict[str, Any]:
    require_implemented("propose_local_exception")
    return app.exceptions.propose(
        bypasses_shape, target_node, rationale, app.git_context
    )


def handle_approve_local_exception(
    app: KMApplication,
    exception_id: str,
    approver: str,
    signature: str,
) -> dict[str, Any]:
    require_implemented("approve_local_exception")
    return app.exceptions.approve(exception_id, approver, signature, app.git_context)


def handle_query_semantic_graph(app: KMApplication, query: str) -> dict[str, Any]:
    require_implemented("query_semantic_graph")
    return app.query.query(query)


def handle_propose_semantic_mr(
    app: KMApplication,
    target_ontology: str,
    rationale: str,
    diff_insertions: str,
    diff_deletions: str = "",
) -> dict[str, Any]:
    require_implemented("propose_semantic_mr")
    return app.merge_requests.propose(
        target_ontology, rationale, diff_insertions, diff_deletions
    )


def handle_approve_semantic_mr(
    app: KMApplication, doc_identifier: str
) -> dict[str, Any]:
    require_implemented("approve_semantic_mr")
    result = app.merge_requests.approve(doc_identifier)
    app.shacl_cache = app.validation.shacl_cache
    return result


def handle_reject_semantic_mr(
    app: KMApplication, doc_identifier: str
) -> dict[str, Any]:
    require_implemented("reject_semantic_mr")
    return app.merge_requests.reject(doc_identifier)


def handle_sync_pending_branch_merges(
    app: KMApplication,
    source_branch: str,
    target_branch: str | None = None,
    event_fingerprint: str | None = None,
) -> dict[str, Any]:
    require_implemented("sync_pending_branch_merges")
    target = target_branch or default_target_branch(app.workspace_root)
    return app.merge_resolver.sync_pending(
        source_branch,
        target,
        app.workspace.config.branch_merge.policy,
        app.workspace_root,
        event_fingerprint=event_fingerprint,
    )


def handle_resolve_branch_merge(
    app: KMApplication, event_id: str, resolution: str
) -> dict[str, Any]:
    require_implemented("resolve_branch_merge")
    return app.merge_resolver.resolve(event_id, resolution)


def tool_error_payload(exc: Exception) -> str:
    km_exc = as_km_error(exc) or exc
    if isinstance(km_exc, FeatureNotImplementedError):
        logger.info("stub: %s", km_exc)
    elif isinstance(km_exc, KmError):
        logger.error("KM error: %s", km_exc)
    else:
        logger.exception("Unexpected tool error")
    return str(km_exc)


def json_result(data: dict[str, Any]) -> str:
    return json.dumps(data)
