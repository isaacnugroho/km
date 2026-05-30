"""Git branch context (read-only, spec §5.1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from km.logging_config import get_logger

logger = get_logger("git.context")

GRAPH_BASE = "http://km.local/graphs"


@dataclass(frozen=True)
class GitContext:
    active_ref: str
    branch_path: str
    graph_uri: str


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

    # Detached HEAD — use short sha as branch path segment
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
        graph_uri=f"{GRAPH_BASE}/{branch_path}",
    )
