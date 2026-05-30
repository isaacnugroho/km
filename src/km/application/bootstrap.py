"""Application bootstrap — wires startup pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from km.application.services.case_export_service import CaseExportService
from km.application.services.case_ingest_service import CaseIngestService
from km.application.services.case_store_service import CaseStoreService
from km.application.services.lo_cache_service import LOCacheService
from km.application.services.query_service import QueryService
from km.application.services.status_service import StatusService, SystemStatus
from km.application.services.workspace_service import WorkspaceService, discover_workspace_root
from km.infrastructure.git.context import GitContext, read_git_context
from km.logging_config import get_logger

logger = get_logger("bootstrap")


@dataclass
class KMApplication:
    workspace_root: Path
    workspace: WorkspaceService
    lo_cache: LOCacheService
    case_store: CaseStoreService
    git_context: GitContext
    status_service: StatusService
    case_export: CaseExportService
    case_ingest: CaseIngestService
    query: QueryService

    @classmethod
    def bootstrap(cls, workspace_root: Path | None = None) -> KMApplication:
        root = workspace_root or discover_workspace_root()
        logger.info("Starting KM bootstrap for workspace %s", root)

        workspace = WorkspaceService(root)
        workspace.validate_bindings()

        lo_cache_base = workspace.resolve_config_path(workspace.config.lo_cache.base_path)
        lo_cache = LOCacheService(root, lo_cache_base)

        binding_data = []
        for binding in workspace.config.learning_ontologies:
            from km.infrastructure.config.loader import validate_lo_binding

            source_path, lo_config = validate_lo_binding(binding, root)
            binding_data.append((binding, lo_config, source_path))

        lo_cache.sync_all(binding_data)

        case_db = workspace.resolve_config_path(workspace.config.quad_store.storage_path)
        exports_root = workspace.resolve_config_path(workspace.config.case_exports.base_path)
        case_store = CaseStoreService(root, case_db, exports_root)
        case_wrapper = case_store.bootstrap()

        git_context = read_git_context(root)

        case_export = CaseExportService(exports_root, case_wrapper)
        case_ingest = CaseIngestService(case_wrapper, case_export, workspace.config)
        query = QueryService(case_wrapper, lo_cache.entries, git_context)

        app = cls(
            workspace_root=root,
            workspace=workspace,
            lo_cache=lo_cache,
            case_store=case_store,
            git_context=git_context,
            status_service=StatusService(),
            case_export=case_export,
            case_ingest=case_ingest,
            query=query,
        )
        logger.info("KM bootstrap complete")
        return app

    def get_system_status(self) -> SystemStatus:
        return self.status_service.get_system_status(
            self.workspace.config,
            self.git_context,
            self.lo_cache.entries,
        )

    def shutdown(self) -> None:
        self.case_store.close()
