"""Application bootstrap — wires startup pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from km.application.services.branch_inheritance_service import BranchInheritanceService
from km.application.services.case_export_service import CaseExportService
from km.application.services.case_ingest_service import CaseIngestService
from km.application.services.case_store_service import CaseStoreService
from km.application.services.exception_service import ExceptionService
from km.application.services.git_watcher_service import GitWatcherService
from km.application.services.lo_cache_service import LOCacheService
from km.application.services.lo_export_service import LOExportService
from km.application.services.lo_resource_service import LOResourceService
from km.application.services.lo_source_store_service import LOSourceStoreService
from km.application.services.merge_prompt_store import MergePromptStore
from km.application.services.merge_request_service import MergeRequestService
from km.application.services.merge_resolver_service import MergeResolverService
from km.application.services.processed_merge_event_store import ProcessedMergeEventStore
from km.application.services.mr_review_doc_service import MRReviewDocService
from km.application.services.query_service import QueryService
from km.application.services.schema_service import SchemaService
from km.application.services.status_service import StatusService, SystemStatus
from km.application.services.validation_service import ValidationService
from km.application.services.feature_gate import release
from km.application.services.workspace_service import (
    WorkspaceService,
    discover_workspace_root,
    raise_on_binding_errors,
)
from km.infrastructure.git.context import GitContext, GitContextHolder
from km.infrastructure.rdf.shacl_cache import ShaclCache
from km.exceptions import ConfigError, KmError
from km.logging_config import get_logger

logger = get_logger("bootstrap")


@dataclass
class KMApplication:
    workspace_root: Path
    workspace: WorkspaceService
    lo_cache: LOCacheService
    case_store: CaseStoreService
    git: GitContextHolder
    status_service: StatusService
    case_export: CaseExportService
    case_ingest: CaseIngestService
    query: QueryService
    shacl_cache: ShaclCache
    validation: ValidationService
    exceptions: ExceptionService
    schemas: SchemaService
    lo_source_store: LOSourceStoreService
    lo_resources: LOResourceService
    lo_export: LOExportService
    merge_requests: MergeRequestService
    branch_inheritance: BranchInheritanceService
    merge_resolver: MergeResolverService
    merge_prompts: MergePromptStore
    git_watcher: GitWatcherService

    @property
    def git_context(self) -> GitContext:
        return self.git.context

    @classmethod
    def bootstrap(
        cls,
        workspace_root: Path | None = None,
        *,
        enable_git_watcher: bool = False,
    ) -> KMApplication:
        root = workspace_root or discover_workspace_root()
        logger.info("Starting KM bootstrap for workspace %s", root)

        workspace = WorkspaceService(root)
        resolution = workspace.resolve_bindings()
        raise_on_binding_errors(resolution)

        lo_cache_base = workspace.resolve_config_path(
            workspace.config.lo_cache.base_path
        )
        lo_cache = LOCacheService(root, lo_cache_base)

        try:
            if resolution.bindings:
                lo_cache.sync_all(resolution.bindings)
            else:
                lo_cache.sync_all([])
        except KmError as exc:
            raise ConfigError(f"cache_sync_failed: {exc}") from exc

        for entry in lo_cache.entries:
            cached = next(
                (
                    resolved
                    for resolved in resolution.bindings
                    if resolved.ontology_id == entry.binding.ontology_id
                ),
                None,
            )
            if cached is not None:
                cached.cache_synced = True

        binding_data = list(workspace.validated_bindings)
        shacl_cache = ShaclCache.compile_from_lo_entries(lo_cache.entries)

        lo_source_store = LOSourceStoreService()
        km_dir = root / ".km"
        lo_source_store.bootstrap_all(binding_data, km_dir=km_dir)
        lo_resources = LOResourceService(lo_cache, lo_source_store)
        lo_export = LOExportService()
        review_docs = MRReviewDocService(root)

        case_db = workspace.resolve_config_path(
            workspace.config.quad_store.storage_path
        )
        exports_root = workspace.resolve_config_path(
            workspace.config.case_exports.base_path
        )
        case_store = CaseStoreService(root, case_db, exports_root, km_dir)
        case_wrapper = case_store.bootstrap()

        git = GitContextHolder.create(root)

        case_export = CaseExportService(exports_root, case_wrapper, km_dir)
        validation = ValidationService(case_wrapper, shacl_cache)
        merge_requests = MergeRequestService(
            root,
            binding_data,
            lo_source_store,
            lo_cache,
            lo_cache.entries,
            lo_export,
            review_docs,
            validation,
        )
        branch_inheritance = BranchInheritanceService(case_wrapper, case_export)
        merge_prompts = MergePromptStore(root)
        processed_merges = ProcessedMergeEventStore(root)
        merge_resolver = MergeResolverService(
            case_wrapper, case_export, merge_prompts, processed_merges
        )
        git_watcher = GitWatcherService(
            root,
            workspace.config,
            git,
            branch_inheritance,
            merge_resolver,
            enable_observer=enable_git_watcher,
        )
        case_ingest = CaseIngestService(
            case_wrapper, case_export, workspace.config, validation
        )
        query = QueryService(case_wrapper, lo_cache.entries, git)
        exceptions = ExceptionService(case_wrapper, case_export, validation)
        schemas = SchemaService(lo_cache.entries)

        app = cls(
            workspace_root=root,
            workspace=workspace,
            lo_cache=lo_cache,
            case_store=case_store,
            git=git,
            status_service=StatusService(),
            case_export=case_export,
            case_ingest=case_ingest,
            query=query,
            shacl_cache=shacl_cache,
            validation=validation,
            exceptions=exceptions,
            schemas=schemas,
            lo_source_store=lo_source_store,
            lo_resources=lo_resources,
            lo_export=lo_export,
            merge_requests=merge_requests,
            branch_inheritance=branch_inheritance,
            merge_resolver=merge_resolver,
            merge_prompts=merge_prompts,
            git_watcher=git_watcher,
        )
        branch_inheritance.ensure_inherited(git, root)
        git_watcher.start()
        release("validate_bindings")
        release("reject_semantic_mr")
        logger.info("KM bootstrap complete")
        return app

    def get_system_status(self) -> SystemStatus:
        resolution = self.workspace.binding_resolution
        return self.status_service.get_system_status(
            self.workspace.config,
            self.git.context,
            self.lo_cache.entries,
            self.exceptions,
            self.merge_requests,
            self.merge_prompts,
            binding_resolution=resolution,
        )

    def shutdown(self) -> None:
        self.git_watcher.stop()
        self.lo_source_store.close()
        self.case_store.close()
