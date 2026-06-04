"""Unit tests for path resolution and config loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from km.exceptions import ConfigError, WorkspaceNotFoundError
from km.infrastructure.config.loader import load_workspace_config, validate_lo_binding
from km.infrastructure.config.loader import load_lo_package_config
from km.infrastructure.config.models import AccessMode, LOBinding, WorkspaceConfig
from km.infrastructure.paths import resolve_path
from km.application.services.workspace_service import discover_workspace_root


def test_resolve_absolute_path(tmp_path: Path) -> None:
    abs_path = tmp_path / "abs"
    abs_path.mkdir()
    assert resolve_path(str(abs_path), tmp_path / "ws") == abs_path.resolve()


def test_resolve_relative_to_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    sub = ws / "data"
    sub.mkdir()
    assert resolve_path("data", ws) == sub.resolve()


def test_resolve_tilde_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    home_sub = tmp_path / "ontologies"
    home_sub.mkdir()
    assert resolve_path("~/ontologies", tmp_path / "ws") == home_sub.resolve()


def test_workspace_config_defaults() -> None:
    cfg = WorkspaceConfig.model_validate({"workspace_id": "x"})
    assert cfg.branch_merge.policy.value == "auto_merge_exception"
    assert cfg.case_exports.export_policy.value == "on_commit"


def test_discover_workspace_root(tmp_workspace: Path) -> None:
    assert discover_workspace_root(tmp_workspace) == tmp_workspace.resolve()


def test_discover_workspace_root_missing(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        discover_workspace_root(tmp_path)


def test_load_workspace_config(tmp_workspace: Path) -> None:
    cfg = load_workspace_config(tmp_workspace)
    assert cfg.workspace_id == "test-workspace"
    assert len(cfg.learning_ontologies) == 1


def test_lo_package_config_prefix(lo_package: Path) -> None:
    lo_cfg = load_lo_package_config(lo_package)
    assert lo_cfg.prefix == "hex"
    assert lo_cfg.primary_prefix == "hex"
    assert lo_cfg.namespace_uri == "http://architecture.org/hexagonal#"


def test_lo_package_config_default_prefix(tmp_path: Path) -> None:
    lo_root = tmp_path / "sample-lo"
    lo_root.mkdir()
    (lo_root / "exports").mkdir()
    (lo_root / "exports" / "main.ttl").write_text(
        "@prefix ex: <http://example.org/lo#> .\nex:Thing a <http://www.w3.org/2002/07/owl#Class> .\n",
        encoding="utf-8",
    )
    (lo_root / "config.json").write_text(
        json.dumps(
            {
                "ontology_id": "sample-lo",
                "base_uri": "http://example.org/lo",
                "named_graphs": {
                    "canonical": "http://km.local/learning-ontologies/sample-lo/canonical",
                    "governance": "http://km.local/learning-ontologies/sample-lo/governance",
                },
            }
        ),
        encoding="utf-8",
    )
    lo_cfg = load_lo_package_config(lo_root)
    assert lo_cfg.prefix is None
    assert lo_cfg.primary_prefix == "sample_lo"


def test_validate_lo_binding_ok(tmp_workspace: Path, lo_package: Path) -> None:
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    source, lo_cfg = validate_lo_binding(binding, tmp_workspace)
    assert source == lo_package.resolve()
    assert lo_cfg.ontology_id == "hexagonal-architecture"


def test_validate_lo_binding_ontology_id_mismatch(tmp_workspace: Path, lo_package: Path) -> None:
    binding = LOBinding(
        ontology_id="wrong-id",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    with pytest.raises(ConfigError, match="ontology_id mismatch"):
        validate_lo_binding(binding, tmp_workspace)


def test_validate_lo_binding_missing_main_ttl(tmp_workspace: Path, lo_package: Path) -> None:
    (lo_package / "exports" / "main.ttl").unlink()
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    with pytest.raises(ConfigError, match="Missing canonical export"):
        validate_lo_binding(binding, tmp_workspace)
