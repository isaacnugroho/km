"""LO dependency resolution and effective cache set (Addendum 2 §B.4–B.5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from km.exceptions import ConfigError
from km.infrastructure.config.catalog import (
    catalog_ontology_ids,
    catalog_path_for_id,
    load_catalog,
    load_package_dependencies,
    validate_lo_catalog,
)
from km.infrastructure.config.dependency_graph import (
    effective_cache_set,
    validate_dependency_graph,
)
from km.infrastructure.config.loader import load_lo_package_config, validate_lo_binding
from km.infrastructure.config.lo_root import (
    infer_lo_root_from_package_path,
    infer_lo_root_from_bindings,
    resolve_binding_source,
    resolve_lo_root,
    source_outside_lo_root_warning,
)
from km.infrastructure.config.models import (
    AccessMode,
    BindingKind,
    DependencyError,
    LOBinding,
    LOCatalog,
    LOPackageConfig,
    WorkspaceConfig,
)
from km.logging_config import get_logger

logger = get_logger("dependency_resolver")


@dataclass
class ResolvedLOBinding:
    ontology_id: str
    source_path: Path
    lo_config: LOPackageConfig
    mode: AccessMode
    binding_kind: BindingKind
    dependencies: list[str]
    cache_synced: bool = False

    def to_binding_tuple(self) -> tuple[LOBinding, LOPackageConfig, Path]:
        binding = LOBinding(
            ontology_id=self.ontology_id,
            source=str(self.source_path),
            mode=self.mode,
        )
        return binding, self.lo_config, self.source_path


@dataclass
class BindingResolution:
    lo_root: Path | None
    catalog_loaded: bool
    explicit_bindings: list[str]
    effective_cache_set: list[str]
    implicit_dependencies: list[str]
    bindings: list[ResolvedLOBinding] = field(default_factory=list)
    errors: list[DependencyError] = field(default_factory=list)
    warnings: list[DependencyError] = field(default_factory=list)
    catalog: LOCatalog | None = None
    package_dependencies: dict[str, list[str]] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def cache_sync_complete(self) -> bool:
        if not self.bindings:
            return True
        return all(entry.cache_synced for entry in self.bindings)

    def hard_error_messages(self) -> list[str]:
        return [err.message for err in self.errors if err.severity == "error"]

    def to_report_dict(self) -> dict:
        return {
            "valid": self.valid and self.cache_sync_complete,
            "rootPath": str(self.lo_root) if self.lo_root else None,
            "catalog_loaded": self.catalog_loaded,
            "explicit_bindings": self.explicit_bindings,
            "effective_cache_set": self.effective_cache_set,
            "implicit_dependencies": self.implicit_dependencies,
            "bindings": [
                {
                    "ontology_id": entry.ontology_id,
                    "source": str(entry.source_path),
                    "mode": entry.mode.value,
                    "binding_kind": entry.binding_kind.value,
                    "dependencies": list(entry.dependencies),
                    "cache_synced": entry.cache_synced,
                    "base_uri": entry.lo_config.base_uri,
                }
                for entry in self.bindings
            ],
            "errors": [err.to_dict() for err in self.errors + self.warnings],
        }


class DependencyResolverService:
    def resolve(
        self,
        config: WorkspaceConfig,
        workspace_root: Path,
        *,
        check_cache_sync: bool = False,
    ) -> BindingResolution:
        explicit_ids = {b.ontology_id for b in config.learning_ontologies}
        explicit_by_id = {b.ontology_id: b for b in config.learning_ontologies}

        lo_root, root_errors = resolve_lo_root(config, workspace_root)
        resolution = BindingResolution(
            lo_root=lo_root,
            catalog_loaded=False,
            explicit_bindings=sorted(explicit_ids),
            effective_cache_set=sorted(explicit_ids),
            implicit_dependencies=[],
        )
        resolution.errors.extend(root_errors)

        if lo_root is None:
            inferred_root, infer_errors = infer_lo_root_from_bindings(
                config.learning_ontologies, workspace_root
            )
            resolution.errors.extend(infer_errors)
            if resolution.errors:
                return resolution
            lo_root = inferred_root
            resolution.lo_root = lo_root

        if lo_root is None:
            return self._resolve_without_catalog(
                config,
                workspace_root,
                explicit_ids,
                explicit_by_id,
                resolution,
                check_cache_sync=check_cache_sync,
            )

        catalog_path = lo_root / "catalog.json"
        if not catalog_path.is_file():
            resolution.warnings.append(
                DependencyError(
                    code="catalog_not_found",
                    severity="warning",
                    message=(
                        f"LO repository root '{lo_root}' has no catalog.json; "
                        "dependency cache expansion skipped"
                    ),
                )
            )
            return self._resolve_without_catalog(
                config,
                workspace_root,
                explicit_ids,
                explicit_by_id,
                resolution,
                lo_root=lo_root,
                check_cache_sync=check_cache_sync,
            )

        try:
            catalog = load_catalog(lo_root)
        except ConfigError as exc:
            resolution.errors.append(
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=str(exc),
                )
            )
            return resolution

        resolution.catalog = catalog
        resolution.catalog_loaded = True

        catalog_errors = validate_lo_catalog(lo_root, catalog)
        resolution.errors.extend(catalog_errors)

        package_deps = load_package_dependencies(lo_root, catalog)
        resolution.package_dependencies = package_deps

        ontology_ids = catalog_ontology_ids(catalog)
        graph_errors = validate_dependency_graph(ontology_ids, package_deps)
        resolution.errors.extend(graph_errors)

        if resolution.errors:
            return resolution

        cache_ids = effective_cache_set(explicit_ids, package_deps)
        implicit = sorted(cache_ids - explicit_ids)
        resolution.effective_cache_set = sorted(cache_ids)
        resolution.implicit_dependencies = implicit

        explicit_paths: dict[str, Path] = {}
        for binding in config.learning_ontologies:
            try:
                source_path = resolve_binding_source(binding, workspace_root, lo_root)
                if binding.source and Path(binding.source).expanduser().is_absolute():
                    warning = source_outside_lo_root_warning(
                        source_path, lo_root, binding.ontology_id
                    )
                    if warning is not None:
                        resolution.warnings.append(warning)
                explicit_paths[binding.ontology_id] = source_path
            except ConfigError as exc:
                resolution.errors.append(
                    DependencyError(
                        code="dependency_unresolvable",
                        severity="error",
                        message=str(exc),
                        ontology_id=binding.ontology_id,
                    )
                )

        if resolution.errors:
            return resolution

        for ontology_id in sorted(cache_ids):
            binding_kind = (
                BindingKind.EXPLICIT
                if ontology_id in explicit_ids
                else BindingKind.IMPLICIT
            )
            if ontology_id in explicit_by_id:
                binding = explicit_by_id[ontology_id]
                mode = binding.mode
                source_path = explicit_paths[ontology_id]
            else:
                mode = AccessMode.READ_ONLY
                rel_path = catalog_path_for_id(catalog, ontology_id)
                if rel_path is None:
                    resolution.errors.append(
                        DependencyError(
                            code="dependency_unresolvable",
                            severity="error",
                            message=(
                                f"No catalog entry for dependency '{ontology_id}'"
                            ),
                            ontology_id=ontology_id,
                        )
                    )
                    continue
                source_path = (lo_root / rel_path).resolve()

            if not source_path.is_dir():
                resolution.errors.append(
                    DependencyError(
                        code="dependency_unresolvable",
                        severity="error",
                        message=f"LO package path does not exist: {source_path}",
                        ontology_id=ontology_id,
                    )
                )
                continue

            main_ttl = source_path / "exports" / "main.ttl"
            if not main_ttl.is_file():
                resolution.errors.append(
                    DependencyError(
                        code="dependency_unresolvable",
                        severity="error",
                        message=f"Missing canonical export: {main_ttl}",
                        ontology_id=ontology_id,
                    )
                )
                continue

            try:
                lo_config = load_lo_package_config(source_path)
            except ConfigError as exc:
                resolution.errors.append(
                    DependencyError(
                        code="dependency_unresolvable",
                        severity="error",
                        message=str(exc),
                        ontology_id=ontology_id,
                    )
                )
                continue

            if lo_config.ontology_id != ontology_id:
                resolution.errors.append(
                    DependencyError(
                        code="dependency_unresolvable",
                        severity="error",
                        message=(
                            f"Expected ontology_id '{ontology_id}', package has "
                            f"'{lo_config.ontology_id}'"
                        ),
                        ontology_id=ontology_id,
                    )
                )
                continue

            if binding_kind == BindingKind.EXPLICIT:
                binding = explicit_by_id[ontology_id]
                try:
                    _, lo_config = validate_lo_binding(
                        binding, workspace_root, lo_root=lo_root
                    )
                except ConfigError as exc:
                    resolution.errors.append(
                        DependencyError(
                            code="dependency_unresolvable",
                            severity="error",
                            message=str(exc),
                            ontology_id=ontology_id,
                        )
                    )
                    continue

            deps = list(package_deps.get(ontology_id, lo_config.dependencies))
            resolution.bindings.append(
                ResolvedLOBinding(
                    ontology_id=ontology_id,
                    source_path=source_path,
                    lo_config=lo_config,
                    mode=mode,
                    binding_kind=binding_kind,
                    dependencies=deps,
                )
            )

        if check_cache_sync:
            self._mark_cache_sync_state(resolution, config, workspace_root)

        return resolution

    def validate_catalog_at_source(
        self, source_path: Path
    ) -> list[DependencyError]:
        """Re-validate catalog dependency graph for an LO package path."""
        lo_root = infer_lo_root_from_package_path(source_path)
        if lo_root is None:
            return []
        try:
            catalog = load_catalog(lo_root)
        except ConfigError as exc:
            return [
                DependencyError(
                    code="catalog_invalid",
                    severity="error",
                    message=str(exc),
                )
            ]
        errors = validate_lo_catalog(lo_root, catalog)
        package_deps = load_package_dependencies(lo_root, catalog)
        errors.extend(
            validate_dependency_graph(catalog_ontology_ids(catalog), package_deps)
        )
        return errors

    def _resolve_without_catalog(
        self,
        config: WorkspaceConfig,
        workspace_root: Path,
        explicit_ids: set[str],
        explicit_by_id: dict[str, LOBinding],
        resolution: BindingResolution,
        *,
        lo_root: Path | None = None,
        check_cache_sync: bool = False,
    ) -> BindingResolution:
        if resolution.errors:
            return resolution

        for binding in config.learning_ontologies:
            try:
                source_path, lo_config = validate_lo_binding(
                    binding, workspace_root, lo_root=lo_root
                )
            except ConfigError as exc:
                resolution.errors.append(
                    DependencyError(
                        code="dependency_unresolvable",
                        severity="error",
                        message=str(exc),
                        ontology_id=binding.ontology_id,
                    )
                )
                continue

            if lo_config.dependencies:
                resolution.errors.append(
                    DependencyError(
                        code="rootPath_required_for_dependencies",
                        severity="error",
                        message=(
                            f"LO '{binding.ontology_id}' declares dependencies "
                            f"{lo_config.dependencies} but LO catalog cannot be resolved"
                        ),
                        ontology_id=binding.ontology_id,
                    )
                )
                continue

            resolution.bindings.append(
                ResolvedLOBinding(
                    ontology_id=binding.ontology_id,
                    source_path=source_path,
                    lo_config=lo_config,
                    mode=binding.mode,
                    binding_kind=BindingKind.EXPLICIT,
                    dependencies=[],
                )
            )

        resolution.effective_cache_set = sorted(explicit_ids)
        resolution.implicit_dependencies = []
        if check_cache_sync:
            self._mark_cache_sync_state(resolution, config, workspace_root)
        return resolution

    def _mark_cache_sync_state(
        self,
        resolution: BindingResolution,
        config: WorkspaceConfig,
        workspace_root: Path,
    ) -> None:
        from km.infrastructure.sync_manifest import lo_sync_manifest_path, workspace_km_dir
        from km.infrastructure.rdf.store import (
            compute_export_checksums,
            needs_cache_rebuild,
        )

        lo_cache_base = workspace_root / ".km" / "lo-cache"
        if config.lo_cache.base_path != "./.km/lo-cache":
            from km.infrastructure.paths import resolve_path

            lo_cache_base = resolve_path(config.lo_cache.base_path, workspace_root)

        km_dir = workspace_km_dir(workspace_root)
        for entry in resolution.bindings:
            cache_db = lo_cache_base / entry.ontology_id / "lo_quads.db"
            manifest_path = lo_sync_manifest_path(km_dir, entry.ontology_id)
            checksums = compute_export_checksums(entry.source_path)
            entry.cache_synced = not needs_cache_rebuild(
                cache_db, manifest_path, checksums
            )
