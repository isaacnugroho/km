"""LO repository root resolution and binding source paths (Addendum 2 §B.2)."""

from __future__ import annotations

from pathlib import Path

from km.exceptions import ConfigError
from km.infrastructure.config.models import DependencyError, LOBinding, WorkspaceConfig
from km.infrastructure.paths import resolve_path


def resolve_lo_root(
    config: WorkspaceConfig, workspace_root: Path
) -> tuple[Path | None, list[DependencyError]]:
    """Resolve configured rootPath to an absolute LO repository root."""
    if config.rootPath is None:
        return None, []
    lo_root = resolve_path(config.rootPath, workspace_root)
    if not lo_root.is_dir():
        return None, [
            DependencyError(
                code="rootPath_not_found",
                severity="error",
                message=f"Configured rootPath does not exist or is not a directory: {lo_root}",
            )
        ]
    return lo_root, []


def infer_lo_root_from_package_path(package_path: Path) -> Path | None:
    """Walk parents from a package path until catalog.json is found."""
    current = package_path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "catalog.json").is_file():
            return candidate
    return None


def infer_lo_root_from_bindings(
    bindings: list[LOBinding],
    workspace_root: Path,
    *,
    lo_root: Path | None = None,
) -> tuple[Path | None, list[DependencyError]]:
    """Infer {lo-root} from binding source paths when rootPath is omitted."""
    if lo_root is not None:
        return lo_root, []

    inferred: set[Path] = set()
    for binding in bindings:
        if binding.source is None:
            continue
        source_path = resolve_path(binding.source, workspace_root)
        found = infer_lo_root_from_package_path(source_path)
        if found is not None:
            inferred.add(found.resolve())

    if not inferred:
        return None, []
    if len(inferred) > 1:
        roots = sorted(str(p) for p in inferred)
        return None, [
            DependencyError(
                code="multiple_lo_roots",
                severity="error",
                message=(
                    "Bindings imply more than one LO repository root without rootPath: "
                    + ", ".join(roots)
                ),
            )
        ]
    return next(iter(inferred)), []


def resolve_binding_source(
    binding: LOBinding,
    workspace_root: Path,
    lo_root: Path | None,
) -> Path:
    """Resolve a binding's package directory per §B.2.3."""
    if binding.source is None:
        if lo_root is None:
            raise ConfigError(
                f"Binding '{binding.ontology_id}' omits source but workspace "
                "rootPath is not configured"
            )
        return (lo_root / binding.ontology_id).resolve()

    expanded = Path(binding.source).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()

    if lo_root is not None:
        return (lo_root / binding.source).resolve()

    return resolve_path(binding.source, workspace_root)


def source_outside_lo_root_warning(
    source_path: Path, lo_root: Path, ontology_id: str
) -> DependencyError | None:
    """Emit warning when absolute source lies outside configured lo-root."""
    try:
        source_path.resolve().relative_to(lo_root.resolve())
    except ValueError:
        return DependencyError(
            code="source_outside_lo_root",
            severity="warning",
            message=(
                f"Binding '{ontology_id}' source '{source_path}' is outside "
                f"configured lo-root '{lo_root}'"
            ),
            ontology_id=ontology_id,
        )
    return None
