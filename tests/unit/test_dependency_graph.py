"""Unit tests for dependency graph algorithms and resolver."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from km.application.services.dependency_resolver_service import DependencyResolverService
from km.exceptions import ConfigError
from km.infrastructure.config.dependency_graph import (
    effective_cache_set,
    validate_dependency_graph,
)
from km.infrastructure.config.models import AccessMode, LOBinding, WorkspaceConfig
from km.application.services.workspace_service import raise_on_binding_errors


REPO_ROOT = Path(__file__).resolve().parents[2]
LO_REPO = REPO_ROOT / "tests" / "fixtures" / "lo-repo"


@pytest.fixture
def lo_repo(tmp_path: Path) -> Path:
    dest = tmp_path / "lo-repo"
    shutil.copytree(LO_REPO, dest)
    return dest


def test_effective_cache_set_transitive() -> None:
    deps = {
        "extension": ["middleware"],
        "middleware": ["foundation"],
        "foundation": [],
    }
    result = effective_cache_set({"extension"}, deps)
    assert result == {"extension", "middleware", "foundation"}


def test_detect_cycle() -> None:
    deps = {"a": ["b"], "b": ["c"], "c": ["a"]}
    errors = validate_dependency_graph({"a", "b", "c"}, deps)
    assert any(err.code == "dependency_cycle" for err in errors)
    cycle_err = next(err for err in errors if err.code == "dependency_cycle")
    assert cycle_err.cycle_path is not None
    assert cycle_err.cycle_path[0] == cycle_err.cycle_path[-1]


def test_unknown_dependency() -> None:
    deps = {"extension": ["missing"]}
    errors = validate_dependency_graph({"extension"}, deps)
    assert any(err.code == "unknown_dependency" for err in errors)


def test_self_dependency() -> None:
    deps = {"extension": ["extension"]}
    errors = validate_dependency_graph({"extension"}, deps)
    assert any(err.code == "self_dependency" for err in errors)


def test_resolver_transitive_closure(lo_repo: Path, tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    km_dir = ws / ".km"
    km_dir.mkdir()
    config = {
        "workspace_id": "dep-test",
        "rootPath": str(lo_repo),
        "learning_ontologies": [
            {
                "ontology_id": "extension",
                "source": "extension",
                "mode": "read_only",
            }
        ],
    }
    (km_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    resolver = DependencyResolverService()
    workspace_config = WorkspaceConfig.model_validate(config)
    resolution = resolver.resolve(workspace_config, ws)

    assert resolution.valid
    assert resolution.effective_cache_set == [
        "extension",
        "foundation",
        "middleware",
    ]
    assert resolution.implicit_dependencies == ["foundation", "middleware"]
    assert len(resolution.bindings) == 3
    kinds = {entry.ontology_id: entry.binding_kind.value for entry in resolution.bindings}
    assert kinds["extension"] == "explicit"
    assert kinds["foundation"] == "implicit"
    assert kinds["middleware"] == "implicit"


def test_resolver_without_rootpath_preserves_base_behavior(
    tmp_workspace: Path,
) -> None:
    resolver = DependencyResolverService()
    from km.infrastructure.config.loader import load_workspace_config

    config = load_workspace_config(tmp_workspace)
    resolution = resolver.resolve(config, tmp_workspace)
    assert resolution.valid
    assert resolution.effective_cache_set == ["hexagonal-architecture"]
    assert resolution.implicit_dependencies == []


def test_resolver_rootpath_not_found(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    km_dir = ws / ".km"
    km_dir.mkdir()
    config = {
        "workspace_id": "bad-root",
        "rootPath": "./missing-ontologies",
        "learning_ontologies": [],
    }
    (km_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    resolver = DependencyResolverService()
    workspace_config = WorkspaceConfig.model_validate(config)
    resolution = resolver.resolve(workspace_config, ws)
    assert not resolution.valid
    assert any(err.code == "rootPath_not_found" for err in resolution.errors)


def test_raise_on_binding_errors() -> None:
    from km.application.services.dependency_resolver_service import BindingResolution
    from km.infrastructure.config.models import DependencyError

    resolution = BindingResolution(
        lo_root=None,
        catalog_loaded=False,
        explicit_bindings=[],
        effective_cache_set=[],
        implicit_dependencies=[],
        errors=[
            DependencyError(
                code="dependency_cycle",
                severity="error",
                message="cycle detected",
            )
        ],
    )
    with pytest.raises(ConfigError):
        raise_on_binding_errors(resolution)
