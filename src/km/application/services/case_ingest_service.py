"""Ingest case facts into the active branch graph."""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from km.application.services.case_export_service import CaseExportService
from km.application.services.case_patch_service import apply_patch, parse_deletion_plan
from km.exceptions import KmError
from km.infrastructure.config.models import ExportPolicy, WorkspaceConfig
from km.infrastructure.git.context import GitContext
from km.infrastructure.rdf.parse import parse_facts, parse_facts_optional
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

if TYPE_CHECKING:
    from km.application.services.validation_service import ValidationService

logger = get_logger("case_ingest")


class CaseIngestService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        export_service: CaseExportService,
        config: WorkspaceConfig,
        validation_service: ValidationService | None = None,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.export_service = export_service
        self.config = config
        self.validation_service = validation_service

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
        if self.validation_service:
            self.validation_service.invalidate(git_context.graph_uri)

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

    def patch(
        self,
        diff_deletions: str,
        diff_insertions: str,
        fmt: str,
        git_context: GitContext,
    ) -> dict[str, Any]:
        if not git_context.branch_path:
            raise KmError("No active git branch context for case patch")

        normalized = fmt.lower()
        if normalized == "ttl":
            normalized = "turtle"
        if normalized != "turtle":
            return self._patch_error(
                "parse",
                f"Unsupported format: {fmt}. patch_case_facts supports turtle only.",
            )

        deletions = (diff_deletions or "").strip()
        insertions = (diff_insertions or "").strip()
        if not deletions and not insertions:
            return self._patch_error(
                "parse",
                "At least one of diff_deletions or diff_insertions must be non-empty.",
            )

        start = time.perf_counter()

        try:
            deletion_plan = parse_deletion_plan(
                diff_deletions or "", normalized, git_context.graph_uri
            )
        except ValueError as exc:
            logger.error("Failed to parse patch deletions: %s", exc)
            return self._patch_error("parse", str(exc))
        except Exception as exc:
            logger.error("Malformed RDF in patch deletions: %s", exc)
            return self._patch_error("parse", str(exc))

        try:
            insertion_quads = parse_facts_optional(
                diff_insertions or "", normalized, git_context.graph_uri
            )
        except ValueError as exc:
            logger.error("Failed to parse patch insertions: %s", exc)
            return self._patch_error("parse", str(exc))
        except Exception as exc:
            logger.error("Malformed RDF in patch insertions: %s", exc)
            return self._patch_error("parse", str(exc))

        try:
            removed, added = apply_patch(
                self.case_wrapper,
                git_context.graph_uri,
                deletion_plan,
                insertion_quads,
            )
        except ValueError as exc:
            logger.error("Patch delete failed: %s", exc)
            return self._patch_error("delete", str(exc))
        except Exception as exc:
            logger.error("Patch apply failed: %s", exc)
            return self._patch_error("insert", str(exc))

        if self.validation_service:
            self.validation_service.invalidate(git_context.graph_uri)

        policy = self.config.case_exports.export_policy
        if policy == ExportPolicy.ON_WRITE:
            logger.debug("Export policy on_write: exporting branch graph after patch")
            self.export_service.export_branch(git_context)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Patched %s: removed %d, added %d (%.1fms)",
            git_context.graph_uri,
            removed,
            added,
            elapsed_ms,
        )
        result: dict[str, Any] = {
            "status": "success",
            "triples_removed": removed,
            "triples_added": added,
        }
        return result

    @staticmethod
    def _patch_error(phase: str, message: str) -> dict[str, Any]:
        return {
            "status": "error",
            "triples_removed": 0,
            "triples_added": 0,
            "errors": [{"phase": phase, "message": message}],
        }

    def serialize_active_graph(self, git_context: GitContext) -> str:
        return self.case_wrapper.serialize_graph(git_context.graph_uri)
