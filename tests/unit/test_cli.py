"""Unit tests for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from km.adapters.cli.main import cmd_export_case, install_pre_commit_hook, run_cli
from km.application.services.workspace_service import init_workspace


def test_cmd_init_creates_config(tmp_path: Path, lo_package: Path) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    config_path = init_workspace(ws, lo_source=str(lo_package))
    assert config_path.is_file()
    data = json.loads(config_path.read_text())
    assert data["learning_ontologies"][0]["ontology_id"] == "hexagonal-architecture"
    assert (ws / "case-exports" / "graphs").is_dir()


def test_cmd_export_case_writes_graph_file(
    tmp_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KM_WORKSPACE_ROOT", str(tmp_workspace))
    from km.application.bootstrap import KMApplication
    from km.adapters.mcp import tools as mcp_tools
    from tests.fixtures_data import SAMPLE_CASE_TURTLE

    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
    finally:
        app.shutdown()

    cmd_export_case()
    export_path = tmp_workspace / "case-exports" / "graphs" / "refs-heads-main.ttl"
    assert export_path.is_file()
    assert "my_core" in export_path.read_text(encoding="utf-8")
    manifest = tmp_workspace / "case-exports" / "sync-manifest.json"
    assert manifest.is_file()


def test_install_pre_commit_hook(tmp_workspace: Path) -> None:
    hook_path = install_pre_commit_hook(tmp_workspace)
    assert hook_path.is_file()
    assert "km export-case" in hook_path.read_text(encoding="utf-8")


def test_run_cli_merge_resolve_unknown_event(tmp_path: Path, lo_package: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    init_workspace(ws, lo_source=str(lo_package))
    assert run_cli(["merge-resolve", "missing-event", "MERGE"]) == 1
