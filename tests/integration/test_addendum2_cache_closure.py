"""Integration tests for Addendum 2 transitive LO cache closure."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.infrastructure.rdf.store import store_exists


REPO_ROOT = Path(__file__).resolve().parents[2]
LO_REPO = REPO_ROOT / "tests" / "fixtures" / "lo-repo"


@pytest.fixture
def lo_repo_workspace(tmp_path: Path) -> Path:
    from tests.conftest import _init_git_repo

    lo_repo = tmp_path / "lo-repo"
    shutil.copytree(LO_REPO, lo_repo)

    ws = tmp_path / "workspace"
    ws.mkdir()
    _init_git_repo(ws)
    km_dir = ws / ".km"
    km_dir.mkdir()
    config = {
        "workspace_id": "addendum2-test",
        "rootPath": str(lo_repo),
        "learning_ontologies": [
            {
                "ontology_id": "extension",
                "source": "extension",
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


def test_bootstrap_materializes_transitive_lo_cache(lo_repo_workspace: Path) -> None:
    app = KMApplication.bootstrap(lo_repo_workspace)
    try:
        cache_base = lo_repo_workspace / ".km" / "lo-cache"
        assert len(app.lo_cache.entries) == 3
        for ontology_id in ("extension", "middleware", "foundation"):
            cache_db = cache_base / ontology_id / "lo_quads.db"
            assert store_exists(cache_db), f"missing LO cache store: {cache_db}"

        status = mcp_tools.handle_status(app)
        assert status["effective_cache_set"] == [
            "extension",
            "foundation",
            "middleware",
        ]
        assert status["implicit_dependencies"] == ["foundation", "middleware"]
        assert len(status["learning_ontologies"]) == 3

        report = mcp_tools.handle_validate_bindings(app)
        assert report["valid"] is True
        assert report["catalog_loaded"] is True
    finally:
        app.shutdown()


def test_schema_lists_implicit_bindings(lo_repo_workspace: Path) -> None:
    app = KMApplication.bootstrap(lo_repo_workspace)
    try:
        doc = app.schemas.learning_ontologies_document()
        kinds = {
            item["ontology_id"]: item["binding_kind"]
            for item in doc["learning_ontologies"]
        }
        assert kinds["extension"] == "explicit"
        assert kinds["foundation"] == "implicit"
        assert kinds["middleware"] == "implicit"
    finally:
        app.shutdown()
