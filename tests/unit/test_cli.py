"""Unit tests for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from km.adapters.cli.main import cmd_export_case, cmd_init, main, run_cli
from km.exceptions import FeatureNotImplementedError
from km.application.services.workspace_service import init_workspace


def test_cmd_init_creates_config_without_lo(tmp_path: Path) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    config_path = init_workspace(ws)
    assert config_path.is_file()
    data = json.loads(config_path.read_text())
    assert data["learning_ontologies"] == []
    assert (ws / "case-exports" / "graphs").is_dir()
    assert (ws / "case-exports" / "governance").is_dir()


def test_cmd_init_creates_config_with_lo_source(
    tmp_path: Path, lo_package: Path
) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    config_path = init_workspace(ws, lo_source=str(lo_package))
    assert config_path.is_file()
    data = json.loads(config_path.read_text())
    assert data["learning_ontologies"][0]["ontology_id"] == "hexagonal-architecture"
    assert data["learning_ontologies"][0]["source"] == str(lo_package)
    assert (ws / "case-exports" / "graphs").is_dir()
    assert (ws / "case-exports" / "governance").is_dir()


def test_init_workspace_does_not_overwrite_existing_config(
    tmp_path: Path, lo_package: Path
) -> None:
    ws = tmp_path / "proj"
    km_dir = ws / ".km"
    km_dir.mkdir(parents=True)
    config_path = km_dir / "config.json"
    original = {"workspace_id": "keep-me", "learning_ontologies": []}
    config_path.write_text(json.dumps(original), encoding="utf-8")
    init_workspace(ws, lo_source=str(lo_package))
    assert json.loads(config_path.read_text()) == original
    assert (ws / "case-exports" / "governance").is_dir()


def test_init_workspace_ensures_governance_when_config_exists(tmp_path: Path) -> None:
    ws = tmp_path / "proj"
    km_dir = ws / ".km"
    km_dir.mkdir(parents=True)
    (km_dir / "config.json").write_text(
        json.dumps({"workspace_id": "legacy", "learning_ontologies": []}),
        encoding="utf-8",
    )
    init_workspace(ws)
    assert (ws / "case-exports" / "graphs").is_dir()
    assert (ws / "case-exports" / "governance").is_dir()


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
    manifest = tmp_workspace / ".km" / "main_sync-manifest.json"
    assert manifest.is_file()


def test_run_cli_status(
    tmp_workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("KM_WORKSPACE_ROOT", str(tmp_workspace))
    assert run_cli(["status"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["active_branch"] == "main"
    assert "pending_branch_merges" in data


def test_run_cli_version(capsys) -> None:
    from km import __version__

    with pytest.raises(SystemExit) as exc:
        run_cli(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_run_cli_init(tmp_path: Path, capsys) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    assert run_cli(["init", "--path", str(ws)]) == 0
    assert "Initialized workspace config" in capsys.readouterr().out
    assert (ws / ".km" / "config.json").is_file()


def test_run_cli_init_with_lo_source(
    tmp_path: Path, lo_package: Path, capsys
) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    assert (
        run_cli(["init", "--path", str(ws), "--lo-source", str(lo_package)]) == 0
    )
    data = json.loads((ws / ".km" / "config.json").read_text(encoding="utf-8"))
    assert data["learning_ontologies"][0]["source"] == str(lo_package)


def test_cmd_init_prints_path(tmp_path: Path, capsys) -> None:
    ws = tmp_path / "proj"
    ws.mkdir()
    cmd_init(ws, lo_source=None)
    assert "Initialized workspace config" in capsys.readouterr().out


def test_run_cli_mcp_delegates_to_server(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def fake_mcp() -> None:
        called.append("mcp")

    monkeypatch.setattr("km.adapters.mcp.server.run_mcp_server", fake_mcp)
    assert run_cli(["mcp"]) == 0
    assert called == ["mcp"]


def test_run_cli_feature_not_implemented(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    def fail_export() -> None:
        raise FeatureNotImplementedError("export_case")

    monkeypatch.setattr("km.adapters.cli.main.cmd_export_case", fail_export)
    assert run_cli(["export-case"]) == 2
    assert "feature not yet implemented" in capsys.readouterr().err


def test_run_cli_km_error_returns_one(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    def fail_status() -> None:
        raise FileNotFoundError("workspace missing")

    monkeypatch.setattr("km.adapters.cli.main.cmd_status", fail_status)
    assert run_cli(["status"]) == 1
    assert "workspace missing" in capsys.readouterr().err


def test_run_cli_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupt() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("km.adapters.cli.main.cmd_status", interrupt)
    assert run_cli(["status"]) == 130


def test_main_exits_with_run_cli_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("km.adapters.cli.main.run_cli", lambda _argv: 7)
    monkeypatch.setattr("km.adapters.cli.main.sys.argv", ["km", "status"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 7
