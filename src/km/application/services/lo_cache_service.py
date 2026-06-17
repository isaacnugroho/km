"""LO workspace cache synchronization (spec §2.3)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from km.application.services.dependency_resolver_service import ResolvedLOBinding
from km.infrastructure.config.models import (
    AccessMode,
    BindingKind,
    LOBinding,
    LOPackageConfig,
    SyncManifest,
)
from km.infrastructure.sync_manifest import lo_sync_manifest_path, workspace_km_dir
from km.infrastructure.rdf.store import (
    QuadStoreWrapper,
    compute_export_checksums,
    import_lo_exports_to_store,
    needs_cache_rebuild,
    remove_store,
    write_sync_manifest,
)
from km.logging_config import get_logger

logger = get_logger("lo_cache")


@dataclass
class LOCacheEntry:
    binding: LOBinding
    source_path: Path
    lo_config: LOPackageConfig
    cache_dir: Path
    cache_db: Path
    manifest_path: Path
    manifest: SyncManifest | None
    rebuilt: bool
    binding_kind: BindingKind = BindingKind.EXPLICIT
    dependencies: list[str] | None = None


class LOCacheService:
    def __init__(self, workspace_root: Path, lo_cache_base: Path) -> None:
        self.workspace_root = workspace_root
        self.lo_cache_base = lo_cache_base
        self.entries: list[LOCacheEntry] = []

    def sync_binding(
        self,
        binding: LOBinding,
        lo_config: LOPackageConfig,
        source_path: Path,
        *,
        binding_kind: BindingKind = BindingKind.EXPLICIT,
        dependencies: list[str] | None = None,
    ) -> LOCacheEntry:
        cache_dir = self.lo_cache_base / binding.ontology_id
        cache_db = cache_dir / "lo_quads.db"
        manifest_path = lo_sync_manifest_path(
            workspace_km_dir(self.workspace_root), binding.ontology_id
        )

        current_checksums = compute_export_checksums(source_path)
        rebuild = needs_cache_rebuild(cache_db, manifest_path, current_checksums)

        if rebuild:
            start = time.perf_counter()
            logger.info("Rebuilding LO cache for %s", binding.ontology_id)
            self._rebuild_cache(source_path, lo_config, cache_dir, cache_db)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "Cache rebuild for %s completed in %.1fms",
                binding.ontology_id,
                elapsed_ms,
            )
        else:
            logger.info("LO cache up to date for %s", binding.ontology_id)

        manifest = write_sync_manifest(
            manifest_path,
            ontology_id=binding.ontology_id,
            source=str(source_path),
            mode=binding.mode.value,
            export_checksums=current_checksums,
        )

        entry = LOCacheEntry(
            binding=binding,
            source_path=source_path,
            lo_config=lo_config,
            cache_dir=cache_dir,
            cache_db=cache_db,
            manifest_path=manifest_path,
            manifest=manifest,
            rebuilt=rebuild,
            binding_kind=binding_kind,
            dependencies=dependencies,
        )
        self.entries.append(entry)
        return entry

    def _rebuild_cache(
        self,
        source_path: Path,
        lo_config: LOPackageConfig,
        cache_dir: Path,
        cache_db: Path,
    ) -> None:
        remove_store(cache_db)

        wrapper = QuadStoreWrapper(cache_db)
        try:
            import_lo_exports_to_store(source_path, lo_config, wrapper)
        finally:
            wrapper.close()

    def sync_all(
        self,
        bindings: list[ResolvedLOBinding | tuple[LOBinding, LOPackageConfig, Path]],
    ) -> list[LOCacheEntry]:
        self.entries.clear()
        for item in bindings:
            if isinstance(item, ResolvedLOBinding):
                binding, lo_config, source_path = item.to_binding_tuple()
                self.sync_binding(
                    binding,
                    lo_config,
                    source_path,
                    binding_kind=item.binding_kind,
                    dependencies=item.dependencies,
                )
            else:
                binding, lo_config, source_path = item
                self.sync_binding(binding, lo_config, source_path)
        return self.entries

    def resync_binding(
        self,
        binding: LOBinding,
        lo_config: LOPackageConfig,
        source_path: Path,
    ) -> LOCacheEntry:
        """Replace cache entry after source exports change (e.g. MR approve)."""
        self.entries = [
            e for e in self.entries if e.binding.ontology_id != binding.ontology_id
        ]
        return self.sync_binding(binding, lo_config, source_path)
