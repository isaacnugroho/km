"""Local exception propose/approve lifecycle (spec §6.1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pyoxigraph import Literal, NamedNode, Quad

from km.application.services.case_export_service import CaseExportService
from km.domain.governance import (
    EXCEPTION_BASE,
    KM_APPROVED_BY,
    KM_BYPASSES_SHAPE,
    KM_LOCAL_EXCEPTION,
    KM_RATIONALE,
    KM_SIGNATURE,
    KM_STATUS,
    KM_TARGET_NODE,
    KM_TIMESTAMP,
    STATUS_APPROVED,
    STATUS_PENDING,
)
from km.exceptions import KmError
from km.infrastructure.git.context import GitContext
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("exceptions")


class ExceptionService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        export_service: CaseExportService,
        validation_service: object,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.export_service = export_service
        self.validation_service = validation_service

    def propose(
        self,
        bypasses_shape: str,
        target_node: str,
        rationale: str,
        git_context: GitContext,
    ) -> dict[str, Any]:
        exception_id = f"{EXCEPTION_BASE}{uuid.uuid4()}"
        graph = NamedNode(git_context.graph_uri)
        exc_node = NamedNode(exception_id)

        quads = [
            Quad(exc_node, NamedNode(RDF_TYPE), NamedNode(KM_LOCAL_EXCEPTION), graph),
            Quad(
                exc_node, NamedNode(KM_BYPASSES_SHAPE), NamedNode(bypasses_shape), graph
            ),
            Quad(exc_node, NamedNode(KM_TARGET_NODE), NamedNode(target_node), graph),
            Quad(exc_node, NamedNode(KM_RATIONALE), Literal(rationale), graph),
            Quad(exc_node, NamedNode(KM_STATUS), Literal(STATUS_PENDING), graph),
        ]
        for quad in quads:
            self.case_wrapper.store.add(quad)

        self._after_mutation(git_context)
        logger.info("Proposed exception %s for %s", exception_id, target_node)
        return {"exception_id": exception_id, "status": STATUS_PENDING}

    def approve(
        self,
        exception_id: str,
        approver: str,
        signature: str,
        git_context: GitContext,
    ) -> dict[str, Any]:
        exc_uri = (
            exception_id
            if exception_id.startswith("http")
            else f"{EXCEPTION_BASE}{exception_id}"
        )
        graph_uri = git_context.graph_uri
        graph = NamedNode(graph_uri)
        exc_node = NamedNode(exc_uri)

        status = self._get_exception_status(exc_node, graph)
        if status != STATUS_PENDING:
            raise KmError(
                f"Exception {exc_uri} is not PENDING_APPROVAL (status={status})"
            )

        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.case_wrapper.store.remove(
            Quad(exc_node, NamedNode(KM_STATUS), Literal(STATUS_PENDING), graph)
        )
        self.case_wrapper.store.add(
            Quad(exc_node, NamedNode(KM_STATUS), Literal(STATUS_APPROVED), graph)
        )
        self.case_wrapper.store.add(
            Quad(exc_node, NamedNode(KM_APPROVED_BY), Literal(approver), graph)
        )
        self.case_wrapper.store.add(
            Quad(exc_node, NamedNode(KM_SIGNATURE), Literal(signature), graph)
        )
        self.case_wrapper.store.add(
            Quad(
                exc_node,
                NamedNode(KM_TIMESTAMP),
                Literal(
                    timestamp,
                    datatype=NamedNode("http://www.w3.org/2001/XMLSchema#dateTime"),
                ),
                graph,
            )
        )

        self._after_mutation(git_context)
        logger.info("Approved exception %s by %s", exc_uri, approver)
        return {"status": STATUS_APPROVED, "timestamp": timestamp}

    def list_exceptions(self, git_context: GitContext) -> list[dict[str, Any]]:
        graph_uri = git_context.graph_uri
        query = f"""
            SELECT ?exception ?bypasses ?target ?rationale ?status ?approver ?signature ?timestamp
            WHERE {{
                GRAPH <{graph_uri}> {{
                    ?exception a <{KM_LOCAL_EXCEPTION}> ;
                                 <{KM_BYPASSES_SHAPE}> ?bypasses ;
                                 <{KM_TARGET_NODE}> ?target ;
                                 <{KM_RATIONALE}> ?rationale ;
                                 <{KM_STATUS}> ?status .
                    OPTIONAL {{ ?exception <{KM_APPROVED_BY}> ?approver }}
                    OPTIONAL {{ ?exception <{KM_SIGNATURE}> ?signature }}
                    OPTIONAL {{ ?exception <{KM_TIMESTAMP}> ?timestamp }}
                }}
            }}
        """
        results: list[dict[str, Any]] = []
        for row in self.case_wrapper.query(query):
            entry: dict[str, Any] = {
                "exception_id": row["exception"],
                "bypasses_shape": row["bypasses"],
                "target_node": row["target"],
                "rationale": row["rationale"],
                "status": row["status"],
            }
            if row.get("approver"):
                entry["approved_by"] = row["approver"]
            if row.get("signature"):
                entry["signature"] = row["signature"]
            if row.get("timestamp"):
                entry["timestamp"] = row["timestamp"]
            results.append(entry)
        return results

    def get_exception(
        self, exception_id: str, git_context: GitContext
    ) -> dict[str, Any]:
        exc_uri = (
            exception_id
            if exception_id.startswith("http")
            else f"{EXCEPTION_BASE}{exception_id}"
        )
        for entry in self.list_exceptions(git_context):
            if entry["exception_id"] == exc_uri:
                return entry
        raise KmError(f"Exception not found: {exc_uri}")

    def count_pending(self, git_context: GitContext) -> int:
        return sum(
            1
            for exc in self.list_exceptions(git_context)
            if exc.get("status") == STATUS_PENDING
        )

    def _get_exception_status(
        self, exc_node: NamedNode, graph: NamedNode
    ) -> str | None:
        for quad in self.case_wrapper.store.quads_for_pattern(
            exc_node, NamedNode(KM_STATUS), None, graph
        ):
            if isinstance(quad.object, Literal):
                return quad.object.value
        return None

    def _after_mutation(self, git_context: GitContext) -> None:
        self.export_service.export_branch(git_context)
        if hasattr(self.validation_service, "invalidate"):
            self.validation_service.invalidate(git_context.graph_uri)


RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
