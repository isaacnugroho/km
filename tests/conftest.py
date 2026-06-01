"""Shared pytest fixtures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HEXAGONAL_LO = REPO_ROOT / "usages" / "ontologies" / "hexagonal-architecture"
LO_RUNTIME_IGNORE = shutil.ignore_patterns("lo_quads.db")
_GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "km-test",
    "GIT_AUTHOR_EMAIL": "km-test@example.com",
    "GIT_COMMITTER_NAME": "km-test",
    "GIT_COMMITTER_EMAIL": "km-test@example.com",
}


def _init_git_repo(path: Path, *, branch: str = "main") -> None:
    subprocess.run(["git", "init", "-b", branch], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "km test init"],
        cwd=path,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
    )


@pytest.fixture
def lo_package(tmp_path: Path) -> Path:
    dest = tmp_path / "lo" / "hexagonal-architecture"
    shutil.copytree(HEXAGONAL_LO, dest, ignore=LO_RUNTIME_IGNORE)
    return dest


@pytest.fixture
def tmp_workspace(tmp_path: Path, lo_package: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    _init_git_repo(ws)
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


@pytest.fixture
def tmp_workspace_on_write(tmp_path: Path, lo_package: Path) -> Path:
    ws = tmp_path / "workspace_on_write"
    ws.mkdir()
    _init_git_repo(ws)
    km_dir = ws / ".km"
    km_dir.mkdir()
    config = {
        "workspace_id": "test-workspace-on-write",
        "learning_ontologies": [
            {
                "ontology_id": "hexagonal-architecture",
                "source": str(lo_package),
                "mode": "read_only",
            }
        ],
        "lo_cache": {"base_path": "./.km/lo-cache"},
        "case_exports": {"base_path": "./case-exports", "export_policy": "on_write"},
        "branch_merge": {"policy": "auto_merge_exception"},
    }
    (km_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (ws / "case-exports" / "graphs").mkdir(parents=True)
    (ws / "case-exports" / "governance").mkdir(parents=True)
    return ws


@pytest.fixture
def curator_lo_package(tmp_path: Path) -> Path:
    dest = tmp_path / "lo-curator" / "hexagonal-architecture"
    shutil.copytree(HEXAGONAL_LO, dest, ignore=LO_RUNTIME_IGNORE)
    return dest


@pytest.fixture
def tmp_curator_workspace(tmp_path: Path, curator_lo_package: Path) -> Path:
    ws = tmp_path / "curator_workspace"
    ws.mkdir()
    _init_git_repo(ws)
    km_dir = ws / ".km"
    km_dir.mkdir()
    config = {
        "workspace_id": "test-curator-workspace",
        "learning_ontologies": [
            {
                "ontology_id": "hexagonal-architecture",
                "source": str(curator_lo_package),
                "mode": "curator",
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
