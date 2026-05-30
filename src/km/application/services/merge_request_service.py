"""Semantic merge request lifecycle (spec §7)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyoxigraph import Literal, NamedNode, Quad

from km.application.services.lo_cache_service import LOCacheEntry
from km.application.services.lo_export_service import LOExportService
from km.application.services.lo_source_store_service import LOSourceStoreEntry, LOSourceStoreService
from km.application.services.mr_review_doc_service import MRReviewDocService
from km.domain.governance import (
    KM,
    KM_AUTHOR,
    KM_CREATED_AT,
    KM_PROPOSAL_GRAPH,
    KM_RATIONALE,
    KM_REVIEW_DOC,
    KM_SEMANTIC_MERGE_REQUEST,
    KM_STATUS,
    KM_TARGET_ONTOLOGY,
    STATUS_PENDING,
)
from km.exceptions import KmError, PermissionError
from km.infrastructure.config.models import LOBinding, LOPackageConfig, AccessMode
from km.infrastructure.rdf.parse import parse_facts
from km.logging_config import get_logger

logger = get_logger("merge_request")

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_DATE_TIME = "http://www.w3.org/2001/XMLSchema#dateTime"


def resolve_lo_binding(
    target_ontology: str,
    bindings: list[tuple[LOBinding, LOPackageConfig, Path]],
) -> tuple[LOBinding, LOPackageConfig, Path]:
    base_uri_match: tuple[LOBinding, LOPackageConfig, Path] | None = None
    ontology_id_match: tuple[LOBinding, LOPackageConfig, Path] | None = None

    for binding, lo_config, source_path in bindings:
        if lo_config.base_uri == target_ontology:
            base_uri_match = (binding, lo_config, source_path)
        if binding.ontology_id == target_ontology:
            ontology_id_match = (binding, lo_config, source_path)

    if base_uri_match:
        return base_uri_match
    if ontology_id_match:
        return ontology_id_match
    raise KmError(f"No learning ontology binding matches target: {target_ontology}")


def proposal_graph_uri(ontology_id: str, mr_id: str) -> str:
    return f"http://km.local/learning-ontologies/{ontology_id}/mr/{mr_id}"


class MergeRequestService:
    def __init__(
        self,
        workspace_root: Path,
        binding_data: list[tuple[LOBinding, LOPackageConfig, Path]],
        lo_source_store: LOSourceStoreService,
        lo_cache_entries: list[LOCacheEntry],
        lo_export: LOExportService,
        review_docs: MRReviewDocService,
    ) -> None:
        self.workspace_root = workspace_root
        self.binding_data = binding_data
        self.lo_source_store = lo_source_store
        self.lo_cache_entries = lo_cache_entries
        self.lo_export = lo_export
        self.review_docs = review_docs

    def propose(
        self,
        target_ontology: str,
        rationale: str,
        diff_insertions: str,
        diff_deletions: str = "",
    ) -> dict[str, Any]:
        binding, lo_config, source_path = resolve_lo_binding(target_ontology, self.binding_data)
        if binding.mode != AccessMode.CURATOR:
            raise PermissionError(
                f"propose_semantic_mr requires curator mode on binding '{binding.ontology_id}'"
            )

        entry = self.lo_source_store.get_entry(binding.ontology_id)
        mr_id = self._mint_mr_id(entry)
        proposal_uri = proposal_graph_uri(binding.ontology_id, mr_id)
        created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        author = os.environ.get("KM_MR_AUTHOR", "km-agent")

        insertion_quads = self._parse_diff(diff_insertions, proposal_uri, "insertions")
        deletion_quads = self._parse_diff(diff_deletions, proposal_uri, "deletions") if diff_deletions.strip() else []

        for quad in insertion_quads + deletion_quads:
            entry.wrapper.store.add(quad)

        gov_graph = NamedNode(lo_config.named_graphs.governance)
        mr_subject = NamedNode(f"{KM}{mr_id}")
        rel_review_doc = self.review_docs.review_doc_relative_path(binding.ontology_id, mr_id)

        governance_quads = [
            Quad(mr_subject, NamedNode(RDF_TYPE), NamedNode(KM_SEMANTIC_MERGE_REQUEST), gov_graph),
            Quad(mr_subject, NamedNode(KM_STATUS), Literal(STATUS_PENDING), gov_graph),
            Quad(
                mr_subject,
                NamedNode(KM_TARGET_ONTOLOGY),
                NamedNode(lo_config.base_uri),
                gov_graph,
            ),
            Quad(
                mr_subject,
                NamedNode(KM_PROPOSAL_GRAPH),
                NamedNode(proposal_uri),
                gov_graph,
            ),
            Quad(mr_subject, NamedNode(KM_RATIONALE), Literal(rationale), gov_graph),
            Quad(mr_subject, NamedNode(KM_AUTHOR), Literal(author), gov_graph),
            Quad(
                mr_subject,
                NamedNode(KM_CREATED_AT),
                Literal(created_at, datatype=NamedNode(XSD_DATE_TIME)),
                gov_graph,
            ),
            Quad(mr_subject, NamedNode(KM_REVIEW_DOC), Literal(rel_review_doc), gov_graph),
        ]
        for quad in governance_quads:
            entry.wrapper.store.add(quad)

        self.lo_export.upsert_governance_mr_shard(entry, mr_id, mr_subject)
        self.review_docs.write_review_doc(
            ontology_id=binding.ontology_id,
            mr_id=mr_id,
            target_ontology_uri=lo_config.base_uri,
            proposal_graph_uri=proposal_uri,
            rationale=rationale,
            author=author,
            diff_insertions=diff_insertions,
            diff_deletions=diff_deletions,
            created_at=created_at,
        )

        logger.info(
            "Proposed semantic MR %s for %s (proposal graph %s)",
            mr_id,
            binding.ontology_id,
            proposal_uri,
        )
        return {"mr_id": mr_id, "status": STATUS_PENDING}

    def read_review_doc(self, ontology_id: str, mr_id: str) -> str:
        return self.review_docs.read_review_doc(ontology_id, mr_id)

    def count_pending(self) -> int:
        total = 0
        for entry in self.lo_source_store.entries:
            gov_graph = entry.lo_config.named_graphs.governance
            query = f"""
                SELECT ?mr WHERE {{
                    GRAPH <{gov_graph}> {{
                        ?mr a <{KM_SEMANTIC_MERGE_REQUEST}> ;
                            <{KM_STATUS}> "{STATUS_PENDING}" .
                    }}
                }}
            """
            total += len(entry.wrapper.query(query))
        return total

    def _mint_mr_id(self, entry: LOSourceStoreEntry) -> str:
        gov_graph = entry.lo_config.named_graphs.governance
        existing = entry.wrapper.query(
            f"""
            SELECT ?mr WHERE {{
                GRAPH <{gov_graph}> {{
                    ?mr a <{KM_SEMANTIC_MERGE_REQUEST}> .
                }}
            }}
            """
        )
        seq = len(existing) + 1
        slug = entry.binding.ontology_id.upper().replace("-", "_")
        return f"MR-{slug}-{seq:03d}"

    def _parse_diff(self, turtle: str, graph_uri: str, label: str) -> list[Quad]:
        if not turtle or not turtle.strip():
            return []
        try:
            return parse_facts(turtle, "turtle", graph_uri)
        except ValueError as exc:
            raise KmError(f"Invalid {label} Turtle: {exc}") from exc
