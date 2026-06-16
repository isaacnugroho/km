"""Learning Ontology Git export writes (spec §2.5, §7.1)."""

from __future__ import annotations

from pathlib import Path

from pyoxigraph import NamedNode

from km.application.services.lo_source_store_service import LOSourceStoreEntry
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.infrastructure.rdf.serialization import (
    serialize_canonical_export,
    serialize_graph_block,
)
from km.logging_config import get_logger

logger = get_logger("lo_export")


class LOExportService:
    def upsert_governance_mr_shard(
        self,
        entry: LOSourceStoreEntry,
        mr_id: str,
        mr_subject: NamedNode,
        wrapper: QuadStoreWrapper,
    ) -> Path:
        gov_graph = entry.lo_config.named_graphs.governance
        quads = [
            quad
            for quad in wrapper.quads_in_graph(gov_graph)
            if quad.subject == mr_subject
        ]
        export_path = entry.source_path / "exports" / "governance" / f"{mr_id}.ttl"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        body = serialize_graph_block(gov_graph, quads)
        export_path.write_text(
            "@prefix km: <http://km.local/governance#> .\n\n" + body,
            encoding="utf-8",
        )
        logger.info("Upserted governance export %s", export_path)
        return export_path

    def regenerate_main_ttl(
        self, entry: LOSourceStoreEntry, wrapper: QuadStoreWrapper
    ) -> Path:
        canonical_uri = entry.lo_config.named_graphs.canonical
        quads = wrapper.quads_in_graph(canonical_uri)
        export_path = entry.source_path / "exports" / "main.ttl"
        export_path.write_text(serialize_canonical_export(quads), encoding="utf-8")
        logger.info("Regenerated canonical export %s", export_path)
        return export_path
