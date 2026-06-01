"""Git branch context and mutable holder for branch watcher (spec §5.1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from km.infrastructure.rdf.ref_mapping import GRAPH_BASE, branch_path_to_graph_uri
from km.logging_config import get_logger

logger = get_logger("git.context")


@dataclass(frozen=True)
class GitContext:
    active_ref: str
    branch_path: str
    graph_uri: str


@dataclass
class GitContextHolder:
    workspace_root: Path
    context: GitContext

    @classmethod
    def create(cls, workspace_root: Path) -> GitContextHolder:
        return cls(workspace_root=workspace_root, context=read_git_context(workspace_root))

    def refresh(self) -> tuple[GitContext, GitContext]:
        previous = self.context
        self.context = read_git_context(self.workspace_root)
        return previous, self.context


def read_git_context(workspace_root: Path) -> GitContext:
    git_dir = workspace_root / ".git"
    head_path = git_dir / "HEAD"
    if not head_path.is_file():
        logger.warning("No .git/HEAD found; using default branch 'main'")
        return _context_from_branch("main")

    head_content = head_path.read_text(encoding="utf-8").strip()
    if head_content.startswith("ref:"):
        ref = head_content.split(":", 1)[1].strip()
        branch_path = _branch_path_from_ref(ref)
        return _context_from_branch(branch_path, active_ref=ref)

    short_sha = head_content[:7]
    logger.debug("Detached HEAD at %s", short_sha)
    return GitContext(
        active_ref=head_content,
        branch_path=short_sha,
        graph_uri=f"{GRAPH_BASE}/{short_sha}",
    )


def _branch_path_from_ref(ref: str) -> str:
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        return ref[len(prefix) :]
    if ref.startswith("refs/"):
        return ref[len("refs/") :].replace("/", "-")
    return ref


def _context_from_branch(branch_path: str, active_ref: str | None = None) -> GitContext:
    ref = active_ref or f"refs/heads/{branch_path}"
    return GitContext(
        active_ref=ref,
        branch_path=branch_path,
        graph_uri=branch_path_to_graph_uri(branch_path),
    )
