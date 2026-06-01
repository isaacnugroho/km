"""Resolve paths to bundled non-Python resources (source tree and PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def _package_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path.cwd())) / "km"
    return Path(__file__).resolve().parent.parent


def bundle_resource_path(*relative_parts: str) -> Path:
    """Return path to a resource shipped alongside the km package."""
    return _package_root().joinpath(*relative_parts)
