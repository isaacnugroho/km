"""Unit tests for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from km.adapters.cli.main import cmd_export_case, run_cli
from km.application.services.workspace_service import init_workspace
from km.exceptions import FeatureNotImplementedError


def test_cmd_init_creates_config(tmp_path: Path, lo_package: Path) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    config_path = init_workspace(ws, lo_source=str(lo_package))
    assert config_path.is_file()
    data = json.loads(config_path.read_text())
    assert data["learning_ontologies"][0]["ontology_id"] == "hexagonal-architecture"
    assert (ws / "case-exports" / "graphs").is_dir()


def test_cmd_export_case_stub(tmp_path: Path, lo_package: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    init_workspace(ws, lo_source=str(lo_package))
    monkeypatch.setenv("KM_WORKSPACE_ROOT", str(ws))
    with pytest.raises(FeatureNotImplementedError, match="cli:export-case"):
        cmd_export_case()


def test_run_cli_export_case_returns_2(tmp_path: Path, lo_package: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "ws2"
    ws.mkdir()
    init_workspace(ws, lo_source=str(lo_package))
    monkeypatch.setenv("KM_WORKSPACE_ROOT", str(ws))
    assert run_cli(["export-case"]) == 2
