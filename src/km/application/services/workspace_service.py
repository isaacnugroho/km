"""Workspace discovery and initialization."""

from __future__ import annotations

import json
import os
from pathlib import Path

from km.exceptions import WorkspaceNotFoundError
from km.infrastructure.config.loader import load_workspace_config, validate_lo_binding
from km.infrastructure.config.models import WorkspaceConfig
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


class WorkspaceService:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.config = load_workspace_config(workspace_root)
        self._validated_bindings: list[tuple[Path, object]] = []

    def validate_bindings(self) -> None:
        from km.infrastructure.config.models import LOPackageConfig

        self._validated_bindings.clear()
        for binding in self.config.learning_ontologies:
            source_path, lo_config = validate_lo_binding(binding, self.workspace_root)
            self._validated_bindings.append((source_path, lo_config))
        logger.info(
            "Validated %d LO binding(s) for workspace %s",
            len(self._validated_bindings),
            self.config.workspace_id,
        )

    @property
    def validated_bindings(self) -> list[tuple[Path, object]]:
        if not self._validated_bindings and self.config.learning_ontologies:
            self.validate_bindings()
        return self._validated_bindings

    def resolve_config_path(self, relative: str) -> Path:
        return resolve_path(relative, self.workspace_root)


def init_workspace(target: Path, *, lo_source: str | None = None) -> Path:
    """Create .km/config.json and case-exports scaffolding."""
    target = target.resolve()
    km_dir = target / ".km"
    km_dir.mkdir(parents=True, exist_ok=True)

    source = lo_source or "usages/ontologies/hexagonal-architecture"
    config = {
        "workspace_id": target.name or "km-default-workspace",
        "learning_ontologies": [
            {
                "ontology_id": "hexagonal-architecture",
                "source": source,
                "mode": "read_only",
            }
        ],
        "lo_cache": {"base_path": "./.km/lo-cache"},
        "case_exports": {"base_path": "./case-exports", "export_policy": "on_commit"},
        "branch_merge": {"policy": "auto_merge_exception"},
    }
    config_path = km_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    (target / "case-exports" / "graphs").mkdir(parents=True, exist_ok=True)
    (target / "case-exports" / "governance").mkdir(parents=True, exist_ok=True)

    logger.info("Initialized workspace at %s", target)
    return config_path
