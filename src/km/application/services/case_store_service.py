"""Case ontology store bootstrap (spec §2.6)."""

from __future__ import annotations

from pathlib import Path

from km.application.services.case_export_service import (
    CaseExportService,
    case_exports_need_rebuild,
    compute_case_export_checksums,
)
from km.infrastructure.rdf.graph_uri_migration import (
    migrate_legacy_branch_graphs,
    rewrite_case_export_graph_uris,
)
from km.infrastructure.rdf.store import QuadStoreWrapper, store_exists
from km.logging_config import get_logger

logger = get_logger("case_store")


class CaseStoreService:
    def __init__(
        self,
        workspace_root: Path,
        case_db_path: Path,
        exports_root: Path,
        km_dir: Path,
    ) -> None:
        self.workspace_root = workspace_root
        self.case_db_path = case_db_path
        self.exports_root = exports_root
        self.km_dir = km_dir
        self.wrapper: QuadStoreWrapper | None = None

    def bootstrap(self) -> QuadStoreWrapper:
        if self.wrapper:
            self.wrapper.close()

        current_checksums = compute_case_export_checksums(self.exports_root)
        has_exports = bool(current_checksums.get("graphs")) or bool(
            current_checksums.get("governance")
        )
        rebuild = case_exports_need_rebuild(
            self.case_db_path, self.exports_root, self.km_dir
        )

        if has_exports:
            rewritten = rewrite_case_export_graph_uris(self.exports_root)
            if rewritten:
                logger.info(
                    "Rewrote legacy graph URIs in %d case export file(s)",
                    len(rewritten),
                )

        if rebuild and has_exports:
            logger.info("Bootstrapping case store from case-exports")
            CaseExportService.rebuild_store_from_exports(self.exports_root, self.case_db_path)
        elif not store_exists(self.case_db_path):
            logger.info("Creating empty case store at %s", self.case_db_path)

        self.wrapper = QuadStoreWrapper(self.case_db_path)
        migrated = migrate_legacy_branch_graphs(self.wrapper)
        if migrated:
            logger.info("Migrated %d legacy branch graph(s) to slug URIs", migrated)
        return self.wrapper

    def close(self) -> None:
        if self.wrapper:
            self.wrapper.close()
            self.wrapper = None
