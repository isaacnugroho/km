"""Semantic merge request lifecycle (spec §7)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyoxigraph import Literal, NamedNode, Quad

from km.application.services.lo_cache_service import LOCacheEntry, LOCacheService
from km.application.services.lo_export_service import LOExportService
from km.application.services.lo_source_store_service import (
    LOSourceStoreEntry,
    LOSourceStoreService,
)
from km.application.services.mr_review_doc_service import MRReviewDocService
from km.application.services.validation_service import ValidationService
from km.domain.governance import (
    KM,
    KM_APPROVED_AT,
    KM_APPROVER,
    KM_AUTHOR,
    KM_CREATED_AT,
    KM_DIFF_DELETIONS,
    KM_PROPOSAL_GRAPH,
    KM_RATIONALE,
    KM_REVIEW_DOC,
    KM_SEMANTIC_MERGE_REQUEST,
    KM_STATUS,
    KM_TARGET_ONTOLOGY,
    KM_REJECTED_AT,
    KM_REJECTOR,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
)
from km.application.services.dependency_resolver_service import DependencyResolverService
from km.exceptions import ConfigError, KmError, PermissionError
from km.infrastructure.config.models import LOBinding, LOPackageConfig, AccessMode
from km.infrastructure.rdf.parse import parse_facts
from km.infrastructure.rdf.shacl_cache import ShaclCache
from km.infrastructure.rdf.store import QuadStoreWrapper
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


def resolve_doc_identifier(
    doc_identifier: str,
    workspace_root: Path,
    binding_data: list[tuple[LOBinding, LOPackageConfig, Path]],
) -> tuple[str, str]:
    raw = doc_identifier.strip()
    if raw.startswith("km://mr/"):
        remainder = raw.removeprefix("km://mr/")
        parts = remainder.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise KmError(f"Invalid MR URI: {doc_identifier}")
        return parts[0], parts[1]

    if raw.upper().startswith("MR-"):
        for binding, _, _ in binding_data:
            slug = binding.ontology_id.upper().replace("-", "_")
            prefix = f"MR-{slug}-"
            if raw.startswith(prefix):
                return binding.ontology_id, raw
        raise KmError(f"Cannot resolve MR id: {doc_identifier}")

    path = Path(raw)
    if not path.is_absolute():
        path = (workspace_root / path).resolve()
    stem = path.stem
    if not stem.startswith("mr-"):
        raise KmError(f"Cannot parse MR review document: {doc_identifier}")

    remainder = stem.removeprefix("mr-")
    for binding, _, _ in binding_data:
        prefix = f"{binding.ontology_id}-"
        if remainder.startswith(prefix):
            return binding.ontology_id, f"MR-{remainder[len(prefix) :]}"
    raise KmError(f"Cannot parse MR review document: {doc_identifier}")


class MergeRequestService:
    def __init__(
        self,
        workspace_root: Path,
        binding_data: list[tuple[LOBinding, LOPackageConfig, Path]],
        lo_source_store: LOSourceStoreService,
        lo_cache: LOCacheService,
        lo_cache_entries: list[LOCacheEntry],
        lo_export: LOExportService,
        review_docs: MRReviewDocService,
        validation: ValidationService,
    ) -> None:
        self.workspace_root = workspace_root
        self.binding_data = binding_data
        self.lo_source_store = lo_source_store
        self.lo_cache = lo_cache
        self.lo_cache_entries = lo_cache_entries
        self.lo_export = lo_export
        self.review_docs = review_docs
        self.validation = validation

    def propose(
        self,
        target_ontology: str,
        rationale: str,
        diff_insertions: str,
        diff_deletions: str = "",
    ) -> dict[str, Any]:
        binding, lo_config, _source_path = resolve_lo_binding(
            target_ontology, self.binding_data
        )
        if binding.mode != AccessMode.CURATOR:
            raise PermissionError(
                f"propose_semantic_mr requires curator mode on binding '{binding.ontology_id}'"
            )

        with self.lo_source_store.open_store(binding.ontology_id) as (entry, wrapper):
            mr_id = self._mint_mr_id(entry, wrapper)
            proposal_uri = proposal_graph_uri(binding.ontology_id, mr_id)
            created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            author = os.environ.get("KM_MR_AUTHOR", "km-agent")

            insertion_quads = self._parse_diff(
                diff_insertions, proposal_uri, "insertions"
            )
            for quad in insertion_quads:
                wrapper.store.add(quad)

            gov_graph = NamedNode(lo_config.named_graphs.governance)
            mr_subject = NamedNode(f"{KM}{mr_id}")
            rel_review_doc = self.review_docs.review_doc_relative_path(
                binding.ontology_id, mr_id
            )

            governance_quads = [
                Quad(
                    mr_subject,
                    NamedNode(RDF_TYPE),
                    NamedNode(KM_SEMANTIC_MERGE_REQUEST),
                    gov_graph,
                ),
                Quad(
                    mr_subject, NamedNode(KM_STATUS), Literal(STATUS_PENDING), gov_graph
                ),
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
                Quad(
                    mr_subject,
                    NamedNode(KM_REVIEW_DOC),
                    Literal(rel_review_doc),
                    gov_graph,
                ),
            ]
            if diff_deletions.strip():
                governance_quads.append(
                    Quad(
                        mr_subject,
                        NamedNode(KM_DIFF_DELETIONS),
                        Literal(diff_deletions),
                        gov_graph,
                    )
                )
            for quad in governance_quads:
                wrapper.store.add(quad)

            self.lo_export.upsert_governance_mr_shard(entry, mr_id, mr_subject, wrapper)

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

    def approve(self, doc_identifier: str) -> dict[str, Any]:
        ontology_id, mr_id = resolve_doc_identifier(
            doc_identifier, self.workspace_root, self.binding_data
        )
        binding, lo_config, source_path = self._binding_for_ontology(ontology_id)
        if binding.mode != AccessMode.CURATOR:
            raise PermissionError(
                f"approve_semantic_mr requires curator mode on binding '{binding.ontology_id}'"
            )

        with self.lo_source_store.open_store(ontology_id) as (entry, wrapper):
            mr_subject = NamedNode(f"{KM}{mr_id}")
            gov_graph = NamedNode(lo_config.named_graphs.governance)
            record = self._load_mr_record(wrapper, mr_subject, gov_graph)
            if record["status"] != STATUS_PENDING:
                raise KmError(
                    f"MR {mr_id} is not PENDING_APPROVAL (status={record['status']})"
                )

            proposal_uri = record["proposal_graph"]
            canonical = NamedNode(lo_config.named_graphs.canonical)
            self._merge_proposal_into_canonical(wrapper, proposal_uri, canonical)
            self._apply_deletions(
                wrapper, mr_subject, gov_graph, proposal_uri, canonical
            )

            timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            approver = os.environ.get("KM_MR_APPROVER", "developer")
            wrapper.store.remove(
                Quad(
                    mr_subject, NamedNode(KM_STATUS), Literal(STATUS_PENDING), gov_graph
                )
            )
            wrapper.store.add(
                Quad(
                    mr_subject, NamedNode(KM_STATUS), Literal(STATUS_APPROVED), gov_graph
                )
            )
            wrapper.store.add(
                Quad(mr_subject, NamedNode(KM_APPROVER), Literal(approver), gov_graph)
            )
            wrapper.store.add(
                Quad(
                    mr_subject,
                    NamedNode(KM_APPROVED_AT),
                    Literal(timestamp, datatype=NamedNode(XSD_DATE_TIME)),
                    gov_graph,
                )
            )

            self.lo_export.regenerate_main_ttl(entry, wrapper)
            self.lo_export.upsert_governance_mr_shard(entry, mr_id, mr_subject, wrapper)

        catalog_errors = DependencyResolverService().validate_catalog_at_source(
            source_path
        )
        hard_errors = [err for err in catalog_errors if err.severity == "error"]
        if hard_errors:
            raise ConfigError(
                "; ".join(err.message for err in hard_errors)
            )

        cache_entry = self.lo_cache.resync_binding(binding, lo_config, source_path)
        self._replace_cache_entry(cache_entry)
        shacl_cache = ShaclCache.compile_from_lo_entries(self.lo_cache.entries)
        self.validation.reload_shapes(shacl_cache)

        self.review_docs.update_review_doc_status(
            ontology_id, mr_id, STATUS_APPROVED, timestamp=timestamp
        )

        logger.info("Approved semantic MR %s for %s", mr_id, ontology_id)
        return {
            "status": STATUS_APPROVED,
            "mr_id": mr_id,
            "target_ontology": lo_config.base_uri,
            "timestamp": timestamp,
        }

    def reject(self, doc_identifier: str) -> dict[str, Any]:
        ontology_id, mr_id = resolve_doc_identifier(
            doc_identifier, self.workspace_root, self.binding_data
        )
        binding, lo_config, _source_path = self._binding_for_ontology(ontology_id)
        if binding.mode != AccessMode.CURATOR:
            raise PermissionError(
                f"reject_semantic_mr requires curator mode on binding '{binding.ontology_id}'"
            )

        with self.lo_source_store.open_store(ontology_id) as (entry, wrapper):
            mr_subject = NamedNode(f"{KM}{mr_id}")
            gov_graph = NamedNode(lo_config.named_graphs.governance)
            record = self._load_mr_record(wrapper, mr_subject, gov_graph)
            if record["status"] != STATUS_PENDING:
                raise KmError(
                    f"MR {mr_id} is not PENDING_APPROVAL (status={record['status']})"
                )

            timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            rejector = os.environ.get("KM_MR_REJECTOR", "developer")
            wrapper.store.remove(
                Quad(
                    mr_subject, NamedNode(KM_STATUS), Literal(STATUS_PENDING), gov_graph
                )
            )
            wrapper.store.add(
                Quad(
                    mr_subject, NamedNode(KM_STATUS), Literal(STATUS_REJECTED), gov_graph
                )
            )
            wrapper.store.add(
                Quad(mr_subject, NamedNode(KM_REJECTOR), Literal(rejector), gov_graph)
            )
            wrapper.store.add(
                Quad(
                    mr_subject,
                    NamedNode(KM_REJECTED_AT),
                    Literal(timestamp, datatype=NamedNode(XSD_DATE_TIME)),
                    gov_graph,
                )
            )

            self.lo_export.upsert_governance_mr_shard(entry, mr_id, mr_subject, wrapper)

        self.review_docs.update_review_doc_status(
            ontology_id, mr_id, STATUS_REJECTED, timestamp=timestamp
        )

        logger.info("Rejected semantic MR %s for %s", mr_id, ontology_id)
        return {
            "status": STATUS_REJECTED,
            "mr_id": mr_id,
            "target_ontology": lo_config.base_uri,
            "timestamp": timestamp,
        }

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
            with self.lo_source_store.open_entry(entry) as wrapper:
                total += len(wrapper.query(query))
        return total

    def _binding_for_ontology(
        self, ontology_id: str
    ) -> tuple[LOBinding, LOPackageConfig, Path]:
        for binding, lo_config, source_path in self.binding_data:
            if binding.ontology_id == ontology_id:
                return binding, lo_config, source_path
        raise KmError(f"Unknown learning ontology: {ontology_id}")

    def _replace_cache_entry(self, cache_entry: LOCacheEntry) -> None:
        for index, entry in enumerate(self.lo_cache_entries):
            if entry.binding.ontology_id == cache_entry.binding.ontology_id:
                self.lo_cache_entries[index] = cache_entry
                return
        self.lo_cache_entries.append(cache_entry)

    def _load_mr_record(
        self,
        wrapper: QuadStoreWrapper,
        mr_subject: NamedNode,
        gov_graph: NamedNode,
    ) -> dict[str, str]:
        query = f"""
            SELECT ?status ?proposal WHERE {{
                GRAPH <{gov_graph.value}> {{
                    <{mr_subject.value}> a <{KM_SEMANTIC_MERGE_REQUEST}> ;
                        <{KM_STATUS}> ?status ;
                        <{KM_PROPOSAL_GRAPH}> ?proposal .
                }}
            }}
        """
        rows = wrapper.query(query)
        if not rows:
            raise KmError(f"Semantic merge request not found: {mr_subject.value}")
        row = rows[0]
        status = row.get("status")
        proposal = row.get("proposal")
        if not status or not proposal:
            raise KmError(f"Incomplete MR record for {mr_subject.value}")
        return {"status": status, "proposal_graph": proposal}

    def _merge_proposal_into_canonical(
        self,
        wrapper: QuadStoreWrapper,
        proposal_uri: str,
        canonical: NamedNode,
    ) -> None:
        for quad in wrapper.quads_in_graph(proposal_uri):
            wrapper.store.add(Quad(quad.subject, quad.predicate, quad.object, canonical))

    def _apply_deletions(
        self,
        wrapper: QuadStoreWrapper,
        mr_subject: NamedNode,
        gov_graph: NamedNode,
        proposal_uri: str,
        canonical: NamedNode,
    ) -> None:
        deletions = self._literal_object(wrapper, mr_subject, gov_graph, KM_DIFF_DELETIONS)
        if not deletions:
            return
        for quad in self._parse_diff(deletions, proposal_uri, "deletions"):
            canonical_quad = Quad(quad.subject, quad.predicate, quad.object, canonical)
            wrapper.remove_quad(canonical_quad)

    def _literal_object(
        self,
        wrapper: QuadStoreWrapper,
        subject: NamedNode,
        graph: NamedNode,
        predicate_uri: str,
    ) -> str | None:
        for quad in wrapper.store.quads_for_pattern(
            subject, NamedNode(predicate_uri), None, graph
        ):
            if isinstance(quad.object, Literal):
                return quad.object.value
        return None

    def _mint_mr_id(self, entry: LOSourceStoreEntry, wrapper: QuadStoreWrapper) -> str:
        gov_graph = entry.lo_config.named_graphs.governance
        existing = wrapper.query(
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
