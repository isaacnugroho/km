"""Git parent-branch and merge detection via reflog (spec §5.2, §5.3)."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from km.logging_config import get_logger

logger = get_logger("git.merge_base")

CHECKOUT_RE = re.compile(r"checkout: moving from (.+) to (.+)")
MERGE_RE = re.compile(r"merge ([^:]+):")


def _branch_log_path(workspace_root: Path, branch_path: str) -> Path:
    path = workspace_root / ".git" / "logs" / "refs" / "heads"
    for part in branch_path.split("/"):
        path = path / part
    return path


def detect_parent_branch(workspace_root: Path, branch_path: str) -> str | None:
    if branch_path in {"main", "master"}:
        return None

    for log_path in (
        _branch_log_path(workspace_root, branch_path),
        workspace_root / ".git" / "logs" / "HEAD",
    ):
        parent = _parent_from_log_file(log_path, branch_path)
        if parent:
            return parent

    result = subprocess.run(
        ["git", "reflog", "--format=%gs", "-n", "30", branch_path],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        for line in reversed(result.stdout.splitlines()):
            match = CHECKOUT_RE.search(line)
            if match and match.group(2).strip() == branch_path:
                parent = match.group(1).strip()
                if parent and parent != branch_path:
                    logger.debug("Detected parent branch %s for %s via git reflog", parent, branch_path)
                    return parent

    heads_dir = workspace_root / ".git" / "refs" / "heads"
    for candidate in ("main", "master"):
        if candidate != branch_path and (heads_dir / candidate).is_file():
            logger.debug("Falling back to parent branch %s for %s", candidate, branch_path)
            return candidate
    return None


def _parent_from_log_file(log_path: Path, branch_path: str) -> str | None:
    if not log_path.is_file():
        return None
    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        message = line.split("\t", 1)[-1] if "\t" in line else line
        match = CHECKOUT_RE.search(message)
        if match and match.group(2).strip() == branch_path:
            parent = match.group(1).strip()
            if parent and parent != branch_path:
                logger.debug("Detected parent branch %s for %s", parent, branch_path)
                return parent
    return None


def detect_recent_merge(workspace_root: Path, target_branch: str) -> tuple[str, str] | None:
    """Return (source_branch, event_fingerprint) from the latest reflog merge entry."""
    log_path = _branch_log_path(workspace_root, target_branch)
    if not log_path.is_file():
        return None

    for line in reversed(log_path.read_text(encoding="utf-8").splitlines()):
        message = line.split("\t", 1)[-1] if "\t" in line else line
        match = MERGE_RE.search(message)
        if not match:
            continue
        source_branch = match.group(1).strip()
        fingerprint = hashlib.sha256(line.encode("utf-8")).hexdigest()[:16]
        logger.debug(
            "Detected merge of %s into %s (event %s)",
            source_branch,
            target_branch,
            fingerprint,
        )
        return source_branch, fingerprint
    return None
