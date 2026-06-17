"""LO repository catalog loading and validation (Addendum 2 §B.1, §B.5.2)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from km.exceptions import ConfigError
from km.infrastructure.config.loader import load_lo_package_config
from km.infrastructure.config.models import (
    CatalogEntry,
    DependencyError,
    LOCatalog,
)


def load_catalog(lo_root: Path) -> LOCatalog:
    """Load and parse {lo-root}/catalog.json."""
    catalog_path = lo_root / "catalog.json"
    if not catalog_path.is_file():
        raise ConfigError(f"Missing LO catalog: {catalog_path}")
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Invalid JSON in {catalog_path}: {exc.msg} at line {exc.lineno}, "
            f"column {exc.colno}"
        ) from exc
    try:
        catalog = LOCatalog.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid catalog in {catalog_path}: {exc}") from exc
    if catalog.catalog_version != "1":
        raise ConfigError(
            f"Unsupported catalog_version '{catalog.catalog_version}' in {catalog_path}; "
            "expected '1'"
        )
    return catalog


def validate_lo_catalog(lo_root: Path, catalog: LOCatalog) -> list[DependencyError]:
    """Enforce catalog invariants (§B.1.4) and return structured errors."""
    errors: list[DependencyError] = []

    seen_ids: dict[str, CatalogEntry] = {}
    seen_paths: dict[str, CatalogEntry] = {}

    for entry in catalog.ontologies:
        if entry.ontology_id in seen_ids:
            errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=(
                        f"Duplicate ontology_id '{entry.ontology_id}' in catalog.json"
                    ),
                    ontology_id=entry.ontology_id,
                )
            )
        else:
            seen_ids[entry.ontology_id] = entry

        if ".." in Path(entry.path).parts:
            errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=f"Catalog path must not contain '..': {entry.path}",
                    ontology_id=entry.ontology_id,
                )
            )
            continue

        if entry.path in seen_paths:
            errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=f"Duplicate catalog path '{entry.path}'",
                    ontology_id=entry.ontology_id,
                )
            )
        else:
            seen_paths[entry.path] = entry

        package_path = lo_root / entry.path
        if not package_path.is_dir():
            errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=f"Catalog package path does not exist: {package_path}",
                    ontology_id=entry.ontology_id,
                )
            )
            continue

        config_path = package_path / "config.json"
        if not config_path.is_file():
            errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=f"Missing package config: {config_path}",
                    ontology_id=entry.ontology_id,
                )
            )
            continue

        main_ttl = package_path / "exports" / "main.ttl"
        if not main_ttl.is_file():
            errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=f"Missing canonical export: {main_ttl}",
                    ontology_id=entry.ontology_id,
                )
            )

        try:
            lo_config = load_lo_package_config(package_path)
        except ConfigError as exc:
            errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=str(exc),
                    ontology_id=entry.ontology_id,
                )
            )
            continue

        if lo_config.ontology_id != entry.ontology_id:
            errors.append(
                DependencyError(
                    code="catalog_id_mismatch",
                    severity="error",
                    message=(
                        f"Catalog ontology_id '{entry.ontology_id}' does not match "
                        f"package config '{lo_config.ontology_id}' at {package_path}"
                    ),
                    ontology_id=entry.ontology_id,
                )
            )

    return errors


def load_package_dependencies(
    lo_root: Path, catalog: LOCatalog
) -> dict[str, list[str]]:
    """Load direct dependencies for every catalog entry."""
    graph: dict[str, list[str]] = {}
    for entry in catalog.ontologies:
        package_path = lo_root / entry.path
        if not package_path.is_dir():
            graph[entry.ontology_id] = []
            continue
        try:
            lo_config = load_lo_package_config(package_path)
        except ConfigError:
            graph[entry.ontology_id] = []
            continue
        graph[entry.ontology_id] = list(lo_config.dependencies)
    return graph


def catalog_ontology_ids(catalog: LOCatalog) -> set[str]:
    return {entry.ontology_id for entry in catalog.ontologies}


def catalog_path_for_id(catalog: LOCatalog, ontology_id: str) -> Path | None:
    for entry in catalog.ontologies:
        if entry.ontology_id == ontology_id:
            return Path(entry.path)
    return None
