"""Unit tests for bundled resource path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

from km.infrastructure.bundle import bundle_resource_path


def test_bundle_resource_path_source() -> None:
    path = bundle_resource_path("adapters", "hooks", "pre-commit.km.sh")
    assert path.is_file()
    assert "km export-case" in path.read_text(encoding="utf-8")


def test_bundle_resource_path_frozen(tmp_path: Path, monkeypatch) -> None:
    hook_dir = tmp_path / "km" / "adapters" / "hooks"
    hook_dir.mkdir(parents=True)
    template = hook_dir / "pre-commit.km.sh"
    template.write_text("#!/bin/sh\nkm export-case\n", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert bundle_resource_path("adapters", "hooks", "pre-commit.km.sh") == template
