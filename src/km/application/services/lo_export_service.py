"""Learning Ontology Git export writes (spec §2.5, §7.1)."""

from __future__ import annotations

from pathlib import Path

from pyoxigraph import NamedNode

from km.application.services.lo_source_store_service import LOSourceStoreEntry
from km.infrastructure.rdf.serialization import serialize_graph_block
from km.infrastructure.rdf.store import compute_export_checksums, write_sync_manifest
from km.logging_config import get_logger

logger = get_logger("lo_export")


class LOExportService:
    def upsert_governance_mr_shard(
        self,
        entry: LOSourceStoreEntry,
        mr_id: str,
        mr_subject: NamedNode,
    ) -> Path:
        gov_graph = entry.lo_config.named_graphs.governance
        quads = [
            quad
            for quad in entry.wrapper.quads_in_graph(gov_graph)
            if quad.subject == mr_subject
        ]
        export_path = entry.source_path / "exports" / "governance" / f"{mr_id}.ttl"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        body = serialize_graph_block(gov_graph, quads)
        export_path.write_text(
            "@prefix km: <http://km.local/governance#> .\n\n" + body,
            encoding="utf-8",
        )
        self.refresh_source_manifest(entry)
        logger.info("Upserted governance export %s", export_path)
        return export_path

    def refresh_source_manifest(self, entry: LOSourceStoreEntry) -> None:
        checksums = compute_export_checksums(entry.source_path)
        write_sync_manifest(
            entry.manifest_path,
            ontology_id=entry.binding.ontology_id,
            source=str(entry.source_path),
            mode=entry.binding.mode.value,
            export_checksums=checksums,
        )
