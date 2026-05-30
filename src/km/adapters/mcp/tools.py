"""MCP tool handlers."""

from __future__ import annotations

import json
from typing import Any

from km.application.bootstrap import KMApplication
from km.application.services.feature_gate import require_implemented
from km.exceptions import FeatureNotImplementedError, KmError
from km.logging_config import get_logger

logger = get_logger("mcp.tools")


def handle_get_system_status(app: KMApplication) -> dict[str, Any]:
    require_implemented("get_system_status")
    status = app.get_system_status()
    return status.to_dict()


def handle_ingest_case_facts(app: KMApplication, facts: str, format: str = "json-ld") -> dict[str, Any]:
    require_implemented("ingest_case_facts")
    logger.debug("ingest_case_facts format=%s", format)
    return app.case_ingest.ingest(facts, format, app.git_context)


def handle_validate_constraints(app: KMApplication) -> dict[str, Any]:
    require_implemented("validate_constraints")
    return {"conforms": True, "violations": []}


def handle_propose_local_exception(
    app: KMApplication,
    bypasses_shape: str,
    target_node: str,
    rationale: str,
) -> dict[str, Any]:
    require_implemented("propose_local_exception")
    return {"exception_id": "", "status": "PENDING_APPROVAL"}


def handle_approve_local_exception(
    app: KMApplication,
    exception_id: str,
    approver: str,
    signature: str,
) -> dict[str, Any]:
    require_implemented("approve_local_exception")
    return {"status": "APPROVED", "timestamp": ""}


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
    return {"mr_id": "", "status": "PENDING_APPROVAL"}


def handle_approve_semantic_mr(app: KMApplication, doc_identifier: str) -> dict[str, Any]:
    require_implemented("approve_semantic_mr")
    return {"status": "APPROVED", "mr_id": "", "target_ontology": "", "timestamp": ""}


def tool_error_payload(exc: Exception) -> str:
    if isinstance(exc, FeatureNotImplementedError):
        logger.info("stub: %s", exc)
    elif isinstance(exc, KmError):
        logger.error("KM error: %s", exc)
    else:
        logger.exception("Unexpected tool error")
    return str(exc)


def json_result(data: dict[str, Any]) -> str:
    return json.dumps(data)
