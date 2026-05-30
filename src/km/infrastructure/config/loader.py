"""Load workspace and LO package configuration."""

from __future__ import annotations

import json
from pathlib import Path

from km.exceptions import ConfigError
from km.infrastructure.config.models import LOBinding, LOPackageConfig, WorkspaceConfig
from km.infrastructure.paths import resolve_path


def load_workspace_config(workspace_root: Path) -> WorkspaceConfig:
    config_path = workspace_root / ".km" / "config.json"
    if not config_path.is_file():
        raise ConfigError(f"Missing workspace config: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return WorkspaceConfig.model_validate(data)


def load_lo_package_config(source_path: Path) -> LOPackageConfig:
    config_path = source_path / "config.json"
    if not config_path.is_file():
        raise ConfigError(f"Missing LO package config: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return LOPackageConfig.model_validate(data)


def validate_lo_binding(binding: LOBinding, workspace_root: Path) -> tuple[Path, LOPackageConfig]:
    source_path = resolve_path(binding.source, workspace_root)
    if not source_path.is_dir():
        raise ConfigError(f"LO source path does not exist: {source_path}")

    lo_config = load_lo_package_config(source_path)
    if lo_config.ontology_id != binding.ontology_id:
        raise ConfigError(
            f"ontology_id mismatch for binding '{binding.ontology_id}': "
            f"package has '{lo_config.ontology_id}'"
        )

    main_ttl = source_path / "exports" / "main.ttl"
    if not main_ttl.is_file():
        raise ConfigError(f"Missing canonical export: {main_ttl}")

    return source_path, lo_config
