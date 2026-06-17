"""Workspace discovery and initialization."""

from __future__ import annotations

import json
import os
from pathlib import Path

from typing import Any

from km.application.services.dependency_resolver_service import (
    BindingResolution,
    DependencyResolverService,
)
from km.exceptions import ConfigError, KmError, WorkspaceNotFoundError
from km.infrastructure.config.loader import load_workspace_config
from km.infrastructure.config.models import LOBinding, LOPackageConfig
from km.application.services.case_export_service import ensure_case_exports_dirs
from km.infrastructure.paths import resolve_path
from km.logging_config import get_logger

logger = get_logger("workspace")


def discover_workspace_root(start: Path | None = None) -> Path:
    """Walk up from start (or CWD) to find directory containing .km/."""
    if os.environ.get("KM_WORKSPACE_ROOT"):
        root = Path(os.environ["KM_WORKSPACE_ROOT"]).resolve()
        if (root / ".km").is_dir():
            return root
        raise WorkspaceNotFoundError(f"KM_WORKSPACE_ROOT has no .km/: {root}")

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".km").is_dir():
            logger.debug("Discovered workspace root: %s", candidate)
            return candidate
    raise WorkspaceNotFoundError(
        f"No .km/ directory found searching upward from {current}"
    )


def raise_on_binding_errors(resolution: BindingResolution) -> None:
    """Map hard dependency resolution failures to ConfigError."""
    if resolution.errors:
        messages = resolution.hard_error_messages()
        if messages:
            raise ConfigError("; ".join(messages))


class WorkspaceService:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.config = load_workspace_config(workspace_root)
        self._resolver = DependencyResolverService()
        self._resolution: BindingResolution | None = None
        self._validated_bindings: list[tuple[LOBinding, LOPackageConfig, Path]] = []

    def resolve_bindings(self, *, check_cache_sync: bool = False) -> BindingResolution:
        self._resolution = self._resolver.resolve(
            self.config,
            self.workspace_root,
            check_cache_sync=check_cache_sync,
        )
        self._validated_bindings = [
            entry.to_binding_tuple() for entry in self._resolution.bindings
        ]
        return self._resolution

    def validate_bindings(self) -> None:
        resolution = self.resolve_bindings()
        raise_on_binding_errors(resolution)
        logger.info(
            "Validated %d LO binding(s) (%d explicit, %d implicit) for workspace %s",
            len(resolution.bindings),
            len(resolution.explicit_bindings),
            len(resolution.implicit_dependencies),
            self.config.workspace_id,
        )

    @property
    def binding_resolution(self) -> BindingResolution | None:
        return self._resolution

    @property
    def validated_bindings(self) -> list[tuple[LOBinding, LOPackageConfig, Path]]:
        if not self._validated_bindings and self.config.learning_ontologies:
            self.validate_bindings()
        return self._validated_bindings

    def binding_report(self) -> dict[str, Any]:
        """Validate all LO bindings and return Addendum 2 structured report."""
        resolution = self.resolve_bindings(check_cache_sync=True)
        report = resolution.to_report_dict()
        if not resolution.errors:
            self._validated_bindings = [
                entry.to_binding_tuple() for entry in resolution.bindings
            ]
        return report

    def resolve_config_path(self, relative: str) -> Path:
        return resolve_path(relative, self.workspace_root)


def init_workspace(target: Path, *, lo_source: str | None = None) -> Path:
    """Create .km/config.json and case-exports scaffolding."""
    target = target.resolve()
    km_dir = target / ".km"
    km_dir.mkdir(parents=True, exist_ok=True)

    learning_ontologies: list[dict[str, str]] = []
    if lo_source is not None:
        source_path = Path(lo_source)
        if not source_path.is_absolute():
            source_path = (target / source_path).resolve()
        lo_config_path = source_path / "config.json"
        if lo_config_path.is_file():
            lo_config = json.loads(lo_config_path.read_text(encoding="utf-8"))
            ontology_id = lo_config.get("ontology_id", source_path.name)
        else:
            ontology_id = source_path.name
        learning_ontologies.append(
            {
                "ontology_id": ontology_id,
                "source": lo_source,
                "mode": "read_only",
            }
        )

    config = {
        "workspace_id": target.name or "km-default-workspace",
        "learning_ontologies": learning_ontologies,
        "lo_cache": {"base_path": "./.km/lo-cache"},
        "case_exports": {"base_path": "./case-exports", "export_policy": "on_commit"},
        "branch_merge": {"policy": "auto_merge_exception"},
    }
    ensure_case_exports_dirs(target / "case-exports")

    config_path = km_dir / "config.json"
    if config_path.exists():
        logger.warning(
            "Skipping config write: %s already exists (refusing to overwrite)",
            config_path,
        )
        return config_path
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    logger.info("Initialized workspace at %s", target)
    return config_path


def setup_mcp_workspace(
    target: Path,
    *,
    lo_source: str | None = None,
    existing_app: object | None = None,
) -> tuple[object, Path]:
    """Initialize workspace scaffolding and bootstrap the MCP application."""
    from km.application.bootstrap import KMApplication

    target = target.resolve()
    config_path = init_workspace(target, lo_source=lo_source)

    if existing_app is not None:
        if existing_app.workspace_root == target:
            return existing_app, config_path
        existing_app.shutdown()

    app = KMApplication.bootstrap(target, enable_git_watcher=True)
    return app, config_path
