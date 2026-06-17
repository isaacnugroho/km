"""Unit tests for LO catalog loading and validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from km.infrastructure.config.catalog import (
    catalog_ontology_ids,
    catalog_path_for_id,
    load_catalog,
    load_package_dependencies,
    validate_lo_catalog,
)
from km.exceptions import ConfigError
from km.infrastructure.config.models import LOCatalog, CatalogEntry


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


def test_load_catalog_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Missing LO catalog"):
        load_catalog(tmp_path)


def test_load_catalog_invalid_json(lo_repo: Path) -> None:
    (lo_repo / "catalog.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_catalog(lo_repo)


def test_load_catalog_invalid_schema(lo_repo: Path) -> None:
    (lo_repo / "catalog.json").write_text(
        '{"catalog_version":"1","ontologies":"not-an-array"}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Invalid catalog"):
        load_catalog(lo_repo)


def test_load_catalog_unsupported_version(lo_repo: Path) -> None:
    data = json.loads((lo_repo / "catalog.json").read_text(encoding="utf-8"))
    data["catalog_version"] = "2"
    (lo_repo / "catalog.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="Unsupported catalog_version"):
        load_catalog(lo_repo)


def test_validate_catalog_path_with_parent_reference(lo_repo: Path) -> None:
    catalog = LOCatalog(
        catalog_version="1",
        ontologies=[
            CatalogEntry(ontology_id="bad", path="../escape"),
        ],
    )
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any("must not contain '..'" in err.message for err in errors)


def test_validate_catalog_missing_package_dir(lo_repo: Path) -> None:
    catalog = LOCatalog(
        catalog_version="1",
        ontologies=[CatalogEntry(ontology_id="ghost", path="ghost")],
    )
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any("does not exist" in err.message for err in errors)


def test_validate_catalog_missing_config(lo_repo: Path) -> None:
    ghost = lo_repo / "ghost"
    ghost.mkdir()
    (ghost / "exports").mkdir()
    (ghost / "exports" / "main.ttl").write_text(
        "@prefix ex: <http://example.org#> .\nex:Thing a <http://www.w3.org/2002/07/owl#Class> .\n",
        encoding="utf-8",
    )
    catalog = LOCatalog(
        catalog_version="1",
        ontologies=[CatalogEntry(ontology_id="ghost", path="ghost")],
    )
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any("Missing package config" in err.message for err in errors)


def test_validate_catalog_missing_main_ttl(lo_repo: Path) -> None:
    ghost = lo_repo / "ghost2"
    ghost.mkdir()
    (ghost / "exports").mkdir()
    (ghost / "config.json").write_text(
        json.dumps(
            {
                "ontology_id": "ghost2",
                "base_uri": "http://example.org/ghost2",
                "named_graphs": {
                    "canonical": "http://km.local/ghost2/canonical",
                    "governance": "http://km.local/ghost2/governance",
                },
            }
        ),
        encoding="utf-8",
    )
    catalog = LOCatalog(
        catalog_version="1",
        ontologies=[CatalogEntry(ontology_id="ghost2", path="ghost2")],
    )
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any("Missing canonical export" in err.message for err in errors)


def test_validate_catalog_invalid_package_config(lo_repo: Path) -> None:
    ghost = lo_repo / "ghost3"
    ghost.mkdir()
    (ghost / "exports").mkdir()
    (ghost / "exports" / "main.ttl").write_text("not turtle at all {{{", encoding="utf-8")
    (ghost / "config.json").write_text("{broken", encoding="utf-8")
    catalog = LOCatalog(
        catalog_version="1",
        ontologies=[CatalogEntry(ontology_id="ghost3", path="ghost3")],
    )
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any(err.code == "catalog_invalid" for err in errors)


def test_validate_duplicate_catalog_path(lo_repo: Path) -> None:
    catalog = load_catalog(lo_repo)
    duplicate = CatalogEntry(ontology_id="dup", path="foundation")
    catalog.ontologies.append(duplicate)
    errors = validate_lo_catalog(lo_repo, catalog)
    assert any("Duplicate catalog path" in err.message for err in errors)


def test_load_package_dependencies_handles_missing_and_invalid(lo_repo: Path) -> None:
    catalog = LOCatalog(
        catalog_version="1",
        ontologies=[
            CatalogEntry(ontology_id="missing", path="missing"),
            CatalogEntry(ontology_id="broken", path="broken"),
        ],
    )
    broken = lo_repo / "broken"
    broken.mkdir()
    (broken / "config.json").write_text("{", encoding="utf-8")
    deps = load_package_dependencies(lo_repo, catalog)
    assert deps["missing"] == []
    assert deps["broken"] == []


def test_catalog_helpers(lo_repo: Path) -> None:
    catalog = load_catalog(lo_repo)
    assert catalog_ontology_ids(catalog) == {"foundation", "middleware", "extension"}
    assert catalog_path_for_id(catalog, "middleware") == Path("middleware")
    assert catalog_path_for_id(catalog, "absent") is None
