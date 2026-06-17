"""Unit tests for LO catalog loading and validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from km.infrastructure.config.catalog import (
    load_catalog,
    load_package_dependencies,
    validate_lo_catalog,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
LO_REPO = REPO_ROOT / "tests" / "fixtures" / "lo-repo"


@pytest.fixture
def lo_repo(tmp_path: Path) -> Path:
    dest = tmp_path / "lo-repo"
    shutil.copytree(LO_REPO, dest)
    return dest


def test_load_catalog(lo_repo: Path) -> None:
    catalog = load_catalog(lo_repo)
    assert catalog.catalog_version == "1"
    assert {entry.ontology_id for entry in catalog.ontologies} == {
        "foundation",
        "middleware",
        "extension",
    }


def test_validate_lo_catalog_success(lo_repo: Path) -> None:
    catalog = load_catalog(lo_repo)
    errors = validate_lo_catalog(lo_repo, catalog)
    assert errors == []


def test_validate_duplicate_ontology_id(lo_repo: Path) -> None:
    catalog = load_catalog(lo_repo)
    catalog.ontologies.append(catalog.ontologies[0])
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any(err.code == "catalog_invalid" for err in errors)


def test_validate_id_mismatch(lo_repo: Path) -> None:
    catalog = load_catalog(lo_repo)
    config_path = lo_repo / "foundation" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["ontology_id"] = "wrong-id"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any(err.code == "catalog_id_mismatch" for err in errors)


def test_load_package_dependencies(lo_repo: Path) -> None:
    catalog = load_catalog(lo_repo)
    deps = load_package_dependencies(lo_repo, catalog)
    assert deps["foundation"] == []
    assert deps["middleware"] == ["foundation"]
    assert deps["extension"] == ["middleware"]
