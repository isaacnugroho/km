"""Unit tests for LO root path resolution (Addendum 2 §B.2)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from km.exceptions import ConfigError
from km.infrastructure.config.lo_root import (
    infer_lo_root_from_bindings,
    infer_lo_root_from_package_path,
    resolve_binding_source,
    resolve_lo_root,
    source_outside_lo_root_warning,
)
from km.infrastructure.config.models import AccessMode, LOBinding, WorkspaceConfig


REPO_ROOT = Path(__file__).resolve().parents[2]
LO_REPO = REPO_ROOT / "tests" / "fixtures" / "lo-repo"


def test_resolve_lo_root_none_when_unconfigured(tmp_path: Path) -> None:
    config = WorkspaceConfig.model_validate({"workspace_id": "ws"})
    lo_root, errors = resolve_lo_root(config, tmp_path)
    assert lo_root is None
    assert errors == []


def test_resolve_lo_root_not_found(tmp_path: Path) -> None:
    config = WorkspaceConfig.model_validate(
        {"workspace_id": "ws", "rootPath": "./missing-lo-root"}
    )
    lo_root, errors = resolve_lo_root(config, tmp_path)
    assert lo_root is None
    assert len(errors) == 1
    assert errors[0].code == "rootPath_not_found"


def test_infer_lo_root_from_package_file_path(tmp_path: Path) -> None:
    lo_repo = tmp_path / "lo-repo"
    shutil.copytree(LO_REPO, lo_repo)
    main_ttl = lo_repo / "foundation" / "exports" / "main.ttl"
    found = infer_lo_root_from_package_path(main_ttl)
    assert found == lo_repo.resolve()


def test_infer_lo_root_from_bindings_returns_existing_lo_root(
    tmp_path: Path,
) -> None:
    lo_root = tmp_path / "lo-repo"
    lo_root.mkdir()
    (lo_root / "catalog.json").write_text('{"catalog_version":"1","ontologies":[]}')
    binding = LOBinding(
        ontology_id="x", source="somewhere", mode=AccessMode.READ_ONLY
    )
    found, errors = infer_lo_root_from_bindings(
        [binding], tmp_path, lo_root=lo_root
    )
    assert found == lo_root
    assert errors == []


def test_infer_lo_root_from_bindings_skips_omitted_source(tmp_path: Path) -> None:
    binding = LOBinding(ontology_id="x", source=None, mode=AccessMode.READ_ONLY)
    found, errors = infer_lo_root_from_bindings([binding], tmp_path)
    assert found is None
    assert errors == []


def test_infer_lo_root_from_bindings_multiple_roots(tmp_path: Path) -> None:
    root_a = tmp_path / "repo-a"
    root_b = tmp_path / "repo-b"
    for root in (root_a, root_b):
        pkg = root / "pkg-a"
        pkg.mkdir(parents=True)
        (root / "catalog.json").write_text(
            json.dumps({"catalog_version": "1", "ontologies": []})
        )

    bindings = [
        LOBinding(
            ontology_id="a",
            source=str(root_a / "pkg-a"),
            mode=AccessMode.READ_ONLY,
        ),
        LOBinding(
            ontology_id="b",
            source=str(root_b / "pkg-a"),
            mode=AccessMode.READ_ONLY,
        ),
    ]
    found, errors = infer_lo_root_from_bindings(bindings, tmp_path)
    assert found is None
    assert any(err.code == "multiple_lo_roots" for err in errors)


def test_infer_lo_root_from_bindings_single_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (root / "catalog.json").write_text(
        '{"catalog_version":"1","ontologies":[]}', encoding="utf-8"
    )
    binding = LOBinding(
        ontology_id="pkg", source=str(pkg), mode=AccessMode.READ_ONLY
    )
    found, errors = infer_lo_root_from_bindings([binding], tmp_path)
    assert found == root.resolve()
    assert errors == []


def test_resolve_binding_source_omitted_with_lo_root(tmp_path: Path) -> None:
    lo_root = tmp_path / "ontologies"
    lo_root.mkdir()
    binding = LOBinding(
        ontology_id="foundation", source=None, mode=AccessMode.READ_ONLY
    )
    resolved = resolve_binding_source(binding, tmp_path, lo_root)
    assert resolved == (lo_root / "foundation").resolve()


def test_resolve_binding_source_omitted_without_lo_root() -> None:
    binding = LOBinding(
        ontology_id="foundation", source=None, mode=AccessMode.READ_ONLY
    )
    with pytest.raises(ConfigError, match="omits source"):
        resolve_binding_source(binding, Path("/ws"), None)


def test_resolve_binding_source_relative_without_lo_root(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    pkg = ws / "packages" / "lo"
    pkg.mkdir(parents=True)
    binding = LOBinding(
        ontology_id="lo", source="packages/lo", mode=AccessMode.READ_ONLY
    )
    resolved = resolve_binding_source(binding, ws, None)
    assert resolved == pkg.resolve()


def test_source_outside_lo_root_warning() -> None:
    lo_root = Path("/data/ontologies")
    outside = Path("/other/hexagonal-architecture")
    warning = source_outside_lo_root_warning(outside, lo_root, "hexagonal-architecture")
    assert warning is not None
    assert warning.code == "source_outside_lo_root"

    inside = lo_root / "hexagonal-architecture"
    assert source_outside_lo_root_warning(inside, lo_root, "hexagonal-architecture") is None
