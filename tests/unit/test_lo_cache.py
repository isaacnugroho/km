"""Unit tests for LO cache synchronization."""

from __future__ import annotations

import time
from pathlib import Path


from km.application.services.lo_cache_service import LOCacheService
from km.infrastructure.config.loader import validate_lo_binding
from km.infrastructure.config.models import AccessMode, LOBinding
from km.infrastructure.rdf.store import (
    compute_export_checksums,
    load_sync_manifest,
    store_exists,
)


def test_first_sync_creates_cache_and_manifest(
    tmp_workspace: Path, lo_package: Path
) -> None:
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    _, lo_config = validate_lo_binding(binding, tmp_workspace)
    cache_base = tmp_workspace / ".km" / "lo-cache"
    service = LOCacheService(tmp_workspace, cache_base)

    entry = service.sync_binding(binding, lo_config, lo_package)

    assert store_exists(entry.cache_db)
    assert entry.manifest_path.is_file()
    assert entry.rebuilt is True
    manifest = load_sync_manifest(entry.manifest_path)
    assert manifest is not None
    assert manifest.ontology_id == "hexagonal-architecture"
    assert "main.ttl" in manifest.export_checksums


def test_unchanged_exports_skip_rebuild(tmp_workspace: Path, lo_package: Path) -> None:
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    _, lo_config = validate_lo_binding(binding, tmp_workspace)
    cache_base = tmp_workspace / ".km" / "lo-cache"
    service = LOCacheService(tmp_workspace, cache_base)

    first = service.sync_binding(binding, lo_config, lo_package)
    mtime_before = first.cache_db.stat().st_mtime
    time.sleep(0.05)

    service2 = LOCacheService(tmp_workspace, cache_base)
    second = service2.sync_binding(binding, lo_config, lo_package)

    assert second.rebuilt is False
    assert second.cache_db.stat().st_mtime == mtime_before


def test_touch_main_ttl_triggers_rebuild(tmp_workspace: Path, lo_package: Path) -> None:
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    _, lo_config = validate_lo_binding(binding, tmp_workspace)
    cache_base = tmp_workspace / ".km" / "lo-cache"
    service = LOCacheService(tmp_workspace, cache_base)
    service.sync_binding(binding, lo_config, lo_package)

    main_ttl = lo_package / "exports" / "main.ttl"
    main_ttl.write_text(main_ttl.read_text() + "\n", encoding="utf-8")

    service2 = LOCacheService(tmp_workspace, cache_base)
    entry = service2.sync_binding(binding, lo_config, lo_package)
    assert entry.rebuilt is True


def test_empty_governance_dir(tmp_workspace: Path, lo_package: Path) -> None:
    checksums = compute_export_checksums(lo_package)
    assert checksums["governance"] == {}
