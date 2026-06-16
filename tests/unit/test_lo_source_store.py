"""Unit tests for LO source store bootstrap (Phase 4a)."""

from __future__ import annotations

from pathlib import Path

from km.application.services.lo_source_store_service import (
    LOSourceStoreService,
    resolve_lo_storage_path,
)
from km.infrastructure.config.loader import validate_lo_binding
from km.infrastructure.config.models import AccessMode, LOBinding
from km.infrastructure.rdf.store import load_sync_manifest, store_exists


def test_source_store_bootstrap_creates_lo_quads_db(
    tmp_workspace: Path, lo_package: Path
) -> None:
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    _, lo_config = validate_lo_binding(binding, tmp_workspace)
    service = LOSourceStoreService()

    entry = service.bootstrap_all(
        [(binding, lo_config, lo_package)], km_dir=tmp_workspace / ".km"
    )[0]

    store_path = resolve_lo_storage_path(lo_package, lo_config.quad_store.storage_path)
    assert store_path == entry.store_path
    assert store_exists(store_path)
    assert entry.rebuilt is True
    assert entry.manifest_path.is_file()
    manifest = load_sync_manifest(entry.manifest_path)
    assert manifest is not None
    assert manifest.ontology_id == "hexagonal-architecture"
    service.close()


def test_source_store_skips_rebuild_when_exports_unchanged(
    tmp_workspace: Path, lo_package: Path
) -> None:
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    _, lo_config = validate_lo_binding(binding, tmp_workspace)
    service = LOSourceStoreService()
    first = service.bootstrap_all(
        [(binding, lo_config, lo_package)], km_dir=tmp_workspace / ".km"
    )[0]
    assert first.rebuilt is True
    service.close()

    service2 = LOSourceStoreService()
    second = service2.bootstrap_all(
        [(binding, lo_config, lo_package)], km_dir=tmp_workspace / ".km"
    )[0]
    assert second.rebuilt is False
    service2.close()


def test_source_store_open_entry_releases_lock_for_other_processes(
    tmp_workspace: Path, lo_package: Path
) -> None:
    """Short-lived opens allow another bootstrap after the first service closes."""
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    _, lo_config = validate_lo_binding(binding, tmp_workspace)
    service_a = LOSourceStoreService()
    service_a.bootstrap_all(
        [(binding, lo_config, lo_package)], km_dir=tmp_workspace / ".km"
    )
    entry = service_a.get_entry("hexagonal-architecture")
    with service_a.open_entry(entry) as wrapper:
        assert wrapper.ask("ASK { }") is True
    service_a.close()

    service_b = LOSourceStoreService()
    entry_b = service_b.bootstrap_all(
        [(binding, lo_config, lo_package)], km_dir=tmp_workspace / ".km"
    )[0]
    with service_b.open_entry(entry_b) as wrapper:
        assert wrapper.ask("ASK { }") is True
    service_b.close()


def test_governance_graph_serializes_from_source_store(
    tmp_workspace: Path, lo_package: Path
) -> None:
    gov_graph = "http://km.local/learning-ontologies/hexagonal-architecture/governance"
    shard = lo_package / "exports" / "governance" / "MR-HEX-001.ttl"
    shard.write_text(
        f"""@prefix km: <http://km.local/governance#> .

GRAPH <{gov_graph}> {{
    km:MR-HEX-001 a km:SemanticMergeRequest ;
        km:status "APPROVED" .
}}
""",
        encoding="utf-8",
    )
    binding = LOBinding(
        ontology_id="hexagonal-architecture",
        source=str(lo_package),
        mode=AccessMode.READ_ONLY,
    )
    _, lo_config = validate_lo_binding(binding, tmp_workspace)
    service = LOSourceStoreService()
    entry = service.bootstrap_all(
        [(binding, lo_config, lo_package)], km_dir=tmp_workspace / ".km"
    )[0]
    with service.open_entry(entry) as wrapper:
        content = wrapper.serialize_graph(gov_graph)
    assert "MR-HEX-001" in content
    assert "APPROVED" in content
    service.close()
