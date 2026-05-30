"""Shared pytest fixtures."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HEXAGONAL_LO = REPO_ROOT / "usages" / "ontologies" / "hexagonal-architecture"


@pytest.fixture
def lo_package(tmp_path: Path) -> Path:
    dest = tmp_path / "lo" / "hexagonal-architecture"
    shutil.copytree(HEXAGONAL_LO, dest)
    return dest


@pytest.fixture
def tmp_workspace(tmp_path: Path, lo_package: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=ws, check=True, capture_output=True)
    km_dir = ws / ".km"
    km_dir.mkdir()
    rel_lo = Path("..") / "lo" / "hexagonal-architecture"
    # Use absolute path for reliability
    config = {
        "workspace_id": "test-workspace",
        "learning_ontologies": [
            {
                "ontology_id": "hexagonal-architecture",
                "source": str(lo_package),
                "mode": "read_only",
            }
        ],
        "lo_cache": {"base_path": "./.km/lo-cache"},
        "case_exports": {"base_path": "./case-exports", "export_policy": "on_commit"},
        "branch_merge": {"policy": "auto_merge_exception"},
    }
    (km_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (ws / "case-exports" / "graphs").mkdir(parents=True)
    (ws / "case-exports" / "governance").mkdir(parents=True)
    return ws
