"""Source LO quad-store bootstrap (spec §2.5)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from km.exceptions import KmError
from km.infrastructure.config.models import LOBinding, LOPackageConfig
from km.infrastructure.rdf.store import (
    QuadStoreWrapper,
    compute_export_checksums,
    import_lo_exports_to_store,
    needs_cache_rebuild,
    remove_store,
    write_sync_manifest,
)
from km.logging_config import get_logger

logger = get_logger("lo_source_store")

SOURCE_SYNC_MANIFEST = ".km-source-sync-manifest.json"


def resolve_lo_storage_path(source_path: Path, storage_path: str) -> Path:
    expanded = Path(storage_path).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (source_path / expanded).resolve()


@dataclass
class LOSourceStoreEntry:
    binding: LOBinding
    source_path: Path
    lo_config: LOPackageConfig
    store_path: Path
    manifest_path: Path
    wrapper: QuadStoreWrapper
    rebuilt: bool


class LOSourceStoreService:
    """Runtime store at `{source}/lo_quads.db` for curator writes and governance reads."""

    def __init__(self) -> None:
        self.entries: list[LOSourceStoreEntry] = []

    def bootstrap_all(
        self,
        bindings: list[tuple[LOBinding, LOPackageConfig, Path]],
    ) -> list[LOSourceStoreEntry]:
        self.close()
        self.entries.clear()
        for binding, lo_config, source_path in bindings:
            self.entries.append(self._bootstrap_binding(binding, lo_config, source_path))
        return self.entries

    def _bootstrap_binding(
        self,
        binding: LOBinding,
        lo_config: LOPackageConfig,
        source_path: Path,
    ) -> LOSourceStoreEntry:
        store_path = resolve_lo_storage_path(source_path, lo_config.quad_store.storage_path)
        manifest_path = source_path / SOURCE_SYNC_MANIFEST
        current_checksums = compute_export_checksums(source_path)
        rebuild = needs_cache_rebuild(store_path, manifest_path, current_checksums)

        if rebuild:
            start = time.perf_counter()
            logger.info("Bootstrapping source LO store for %s", binding.ontology_id)
            remove_store(store_path)
            wrapper = QuadStoreWrapper(store_path)
            try:
                import_lo_exports_to_store(source_path, lo_config, wrapper)
            finally:
                wrapper.close()
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "Source store bootstrap for %s completed in %.1fms",
                binding.ontology_id,
                elapsed_ms,
            )
        else:
            logger.info("Source LO store up to date for %s", binding.ontology_id)

        write_sync_manifest(
            manifest_path,
            ontology_id=binding.ontology_id,
            source=str(source_path),
            mode=binding.mode.value,
            export_checksums=current_checksums,
        )

        wrapper = QuadStoreWrapper(store_path)
        return LOSourceStoreEntry(
            binding=binding,
            source_path=source_path,
            lo_config=lo_config,
            store_path=store_path,
            manifest_path=manifest_path,
            wrapper=wrapper,
            rebuilt=rebuild,
        )

    def get_entry(self, ontology_id: str) -> LOSourceStoreEntry:
        for entry in self.entries:
            if entry.binding.ontology_id == ontology_id:
                return entry
        raise KmError(f"Unknown learning ontology: {ontology_id}")

    def close(self) -> None:
        for entry in self.entries:
            entry.wrapper.close()
        self.entries.clear()
