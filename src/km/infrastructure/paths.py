"""Filesystem path resolution (spec §2.2)."""

from __future__ import annotations

from pathlib import Path


def resolve_path(raw: str, workspace_root: Path) -> Path:
    """Resolve absolute, workspace-relative, or home-relative paths."""
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (workspace_root / expanded).resolve()
