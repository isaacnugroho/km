"""Ingest case facts into the active branch graph."""

from __future__ import annotations

import time
from typing import Any

from km.application.services.case_export_service import CaseExportService
from km.exceptions import KmError
from km.infrastructure.config.models import ExportPolicy, WorkspaceConfig
from km.infrastructure.git.context import GitContext
from km.infrastructure.rdf.graph_hash import hash_graph_quads
from km.infrastructure.rdf.parse import parse_facts
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("case_ingest")


class CaseIngestService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        export_service: CaseExportService,
        config: WorkspaceConfig,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.export_service = export_service
        self.config = config
        self._validation_hashes: dict[str, str] = {}

    def ingest(
        self,
        facts: str,
        fmt: str,
        git_context: GitContext,
    ) -> dict[str, Any]:
        if not git_context.branch_path:
            raise KmError("No active git branch context for case ingestion")

        start = time.perf_counter()
        try:
            quads = parse_facts(facts, fmt, git_context.graph_uri)
        except ValueError as exc:
            logger.error("Failed to parse case facts: %s", exc)
            return {"status": "error", "triples_added": 0}
        except Exception as exc:
            logger.error("Malformed RDF in case facts: %s", exc)
            return {"status": "error", "triples_added": 0}

        added = self.case_wrapper.add_quads(quads)
        self._invalidate_validation_cache(git_context.graph_uri)

        policy = self.config.case_exports.export_policy
        if policy == ExportPolicy.ON_WRITE:
            logger.debug("Export policy on_write: exporting branch graph")
            self.export_service.export_branch(git_context)
        else:
            logger.debug("Export deferred (policy=%s)", policy.value)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Ingested %d triple(s) into %s (%.1fms)",
            added,
            git_context.graph_uri,
            elapsed_ms,
        )
        return {"status": "success", "triples_added": added}

    def _invalidate_validation_cache(self, graph_uri: str) -> None:
        store = self.case_wrapper.store
        self._validation_hashes[graph_uri] = hash_graph_quads(store, graph_uri)

    def serialize_active_graph(self, git_context: GitContext) -> str:
        return self.case_wrapper.serialize_graph(git_context.graph_uri)
