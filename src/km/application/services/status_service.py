"""System status aggregation (spec §4.1 #7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from km.application.services.lo_cache_service import LOCacheEntry
from km.infrastructure.config.models import WorkspaceConfig
from km.infrastructure.git.context import GitContext
from km.logging_config import get_logger

logger = get_logger("status")


@dataclass
class SystemStatus:
    active_branch: str
    learning_ontologies: list[dict[str, Any]]
    pending_exceptions_count: int
    pending_mrs_count: int
    branch_merge_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_branch": self.active_branch,
            "learning_ontologies": self.learning_ontologies,
            "pending_exceptions_count": self.pending_exceptions_count,
            "pending_mrs_count": self.pending_mrs_count,
            "branch_merge_policy": self.branch_merge_policy,
        }


class StatusService:
    def get_system_status(
        self,
        config: WorkspaceConfig,
        git_context: GitContext,
        cache_entries: list[LOCacheEntry],
    ) -> SystemStatus:
        lo_status: list[dict[str, Any]] = []
        for entry in cache_entries:
            lo_status.append(
                {
                    "ontology_id": entry.binding.ontology_id,
                    "source": str(entry.source_path),
                    "mode": entry.binding.mode.value,
                    "cache_path": str(entry.cache_dir),
                    "cache_synced_at": entry.manifest.synced_at if entry.manifest else None,
                }
            )

        status = SystemStatus(
            active_branch=git_context.branch_path,
            learning_ontologies=lo_status,
            pending_exceptions_count=0,
            pending_mrs_count=0,
            branch_merge_policy=config.branch_merge.policy.value,
        )
        logger.info(
            "System status: branch=%s, ontologies=%d",
            status.active_branch,
            len(lo_status),
        )
        return status
