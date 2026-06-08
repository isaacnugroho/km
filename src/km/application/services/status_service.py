"""System status aggregation (spec §4.1 #7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from km.application.services.lo_cache_service import LOCacheEntry
from km.application.services.merge_resolver_service import pending_branch_merge_summary
from km.infrastructure.config.models import WorkspaceConfig
from km.infrastructure.git.context import GitContext
from km.logging_config import get_logger

if TYPE_CHECKING:
    from km.application.services.exception_service import ExceptionService
    from km.application.services.merge_prompt_store import MergePromptStore
    from km.application.services.merge_request_service import MergeRequestService

logger = get_logger("status")


@dataclass
class SystemStatus:
    active_branch: str
    learning_ontologies: list[dict[str, Any]]
    pending_exceptions_count: int
    pending_mrs_count: int
    branch_merge_policy: str
    pending_branch_merges_count: int
    pending_branch_merges: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_branch": self.active_branch,
            "learning_ontologies": self.learning_ontologies,
            "pending_exceptions_count": self.pending_exceptions_count,
            "pending_mrs_count": self.pending_mrs_count,
            "branch_merge_policy": self.branch_merge_policy,
            "pending_branch_merges_count": self.pending_branch_merges_count,
            "pending_branch_merges": self.pending_branch_merges,
        }


class StatusService:
    def get_system_status(
        self,
        config: WorkspaceConfig,
        git_context: GitContext,
        cache_entries: list[LOCacheEntry],
        exception_service: ExceptionService | None = None,
        merge_request_service: MergeRequestService | None = None,
        merge_prompt_store: MergePromptStore | None = None,
    ) -> SystemStatus:
        lo_status: list[dict[str, Any]] = []
        for entry in cache_entries:
            lo_status.append(
                {
                    "ontology_id": entry.binding.ontology_id,
                    "source": str(entry.source_path),
                    "mode": entry.binding.mode.value,
                    "cache_path": str(entry.cache_dir),
                    "cache_synced_at": entry.manifest.synced_at
                    if entry.manifest
                    else None,
                }
            )

        pending_exceptions = 0
        if exception_service is not None:
            pending_exceptions = exception_service.count_pending(git_context)

        pending_mrs = 0
        if merge_request_service is not None:
            pending_mrs = merge_request_service.count_pending()

        pending_merges: list[dict[str, Any]] = []
        if merge_prompt_store is not None:
            pending_merges = [
                pending_branch_merge_summary(prompt)
                for prompt in merge_prompt_store.list_pending()
            ]

        status = SystemStatus(
            active_branch=git_context.branch_path,
            learning_ontologies=lo_status,
            pending_exceptions_count=pending_exceptions,
            pending_mrs_count=pending_mrs,
            branch_merge_policy=config.branch_merge.policy.value,
            pending_branch_merges_count=len(pending_merges),
            pending_branch_merges=pending_merges,
        )
        logger.info(
            "System status: branch=%s, ontologies=%d, pending_exceptions=%d, "
            "pending_mrs=%d, pending_branch_merges=%d",
            status.active_branch,
            len(lo_status),
            pending_exceptions,
            pending_mrs,
            status.pending_branch_merges_count,
        )
        return status
