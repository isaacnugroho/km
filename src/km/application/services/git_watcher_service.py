"""Git branch watcher orchestration (spec §5)."""

from __future__ import annotations

from pathlib import Path

from km.application.services.branch_inheritance_service import BranchInheritanceService
from km.application.services.merge_resolver_service import MergeResolverService
from km.infrastructure.config.models import WorkspaceConfig
from km.infrastructure.git.context import GitContextHolder
from km.infrastructure.git.merge_base import detect_recent_merge
from km.infrastructure.git.ref_watcher import RefWatcher
from km.logging_config import get_logger

logger = get_logger("git_watcher")


class GitWatcherService:
    def __init__(
        self,
        workspace_root: Path,
        config: WorkspaceConfig,
        git: GitContextHolder,
        inheritance: BranchInheritanceService,
        merge_resolver: MergeResolverService,
        *,
        enable_observer: bool = True,
    ) -> None:
        self.workspace_root = workspace_root
        self.config = config
        self.git = git
        self.inheritance = inheritance
        self.merge_resolver = merge_resolver
        self._watcher: RefWatcher | None = None
        self._enable_observer = enable_observer

    def start(self) -> None:
        if not self._enable_observer:
            return
        self._watcher = RefWatcher(self.workspace_root, self.handle_git_change)
        self._watcher.start()

    def stop(self) -> None:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def handle_git_change(self) -> None:
        previous, current = self.git.refresh()
        if previous.graph_uri != current.graph_uri:
            logger.info(
                "Branch switch %s → %s (%s → %s)",
                previous.branch_path,
                current.branch_path,
                previous.graph_uri,
                current.graph_uri,
            )
            self.inheritance.ensure_inherited(self.git, self.workspace_root)

        policy = self.config.branch_merge.policy
        for head_file in sorted(
            (self.workspace_root / ".git" / "refs" / "heads").glob("*")
        ):
            if not head_file.is_file():
                continue
            target_branch = head_file.name
            detected = detect_recent_merge(self.workspace_root, target_branch)
            if not detected:
                continue
            source_branch, fingerprint = detected
            self.merge_resolver.handle_merge(
                source_branch,
                target_branch,
                policy,
                event_fingerprint=fingerprint,
            )
