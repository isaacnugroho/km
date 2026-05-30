"""Branch merge resolution policies (spec §5.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pyoxigraph import Literal, NamedNode, Quad

from km.application.services.case_export_service import CaseExportService
from km.application.services.merge_prompt_store import MergePromptStore
from km.domain.governance import (
    CASE_GOVERNANCE_GRAPH,
    KM,
    KM_BRANCH_MERGE_RESOLUTION,
    KM_EXCEPTIONS_COPIED,
    KM_LOCAL_EXCEPTION,
    KM_POLICY,
    KM_RECORDED_AT,
    KM_RESOLUTION,
    KM_SOURCE_GRAPH,
    KM_STATUS,
    KM_TARGET_GRAPH,
    KM_TRIPLES_IMPORTED,
    STATUS_APPROVED,
)
from km.exceptions import KmError
from km.infrastructure.config.models import BranchMergePolicy
from km.infrastructure.rdf.ref_mapping import branch_path_to_graph_uri
from km.infrastructure.rdf.serialization import serialize_graph_block
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("merge_resolver")

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD_DATE_TIME = "http://www.w3.org/2001/XMLSchema#dateTime"


@dataclass
class MergeHandleResult:
    event_id: str
    policy: str
    exceptions_copied: int
    triples_imported: int
    prompt_written: bool


class MergeResolverService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        case_export: CaseExportService,
        prompt_store: MergePromptStore,
        processed_events: set[str] | None = None,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.case_export = case_export
        self.prompt_store = prompt_store
        self.processed_events = processed_events if processed_events is not None else set()

    def handle_merge(
        self,
        source_branch: str,
        target_branch: str,
        policy: BranchMergePolicy,
        *,
        event_fingerprint: str,
    ) -> MergeHandleResult | None:
        event_id = f"merge-{source_branch.replace('/', '-')}-into-{target_branch.replace('/', '-')}-{event_fingerprint}"
        if event_id in self.processed_events:
            return None

        source_uri = branch_path_to_graph_uri(source_branch)
        target_uri = branch_path_to_graph_uri(target_branch)

        if policy == BranchMergePolicy.AUTO_MERGE:
            imported = self._copy_all_quads(source_uri, target_uri)
            self._write_governance(
                event_id,
                source_uri,
                target_uri,
                policy.value,
                resolution="MERGE",
                exceptions_copied=0,
                triples_imported=imported,
            )
            self._export_graphs(source_branch, target_branch)
            self.processed_events.add(event_id)
            return MergeHandleResult(event_id, policy.value, 0, imported, False)

        if policy == BranchMergePolicy.AUTO_MERGE_EXCEPTION:
            exceptions_copied = self._copy_approved_exceptions(source_uri, target_uri)
            remaining = self._count_non_exception_triples(source_uri)
            self._write_governance(
                event_id,
                source_uri,
                target_uri,
                policy.value,
                resolution="AUTO_EXCEPTIONS",
                exceptions_copied=exceptions_copied,
                triples_imported=exceptions_copied,
            )
            self._export_graphs(source_branch, target_branch)
            prompt_written = False
            if remaining > 0:
                self.prompt_store.write_prompt(
                    {
                        "event_id": event_id,
                        "source_branch": source_branch,
                        "target_branch": target_branch,
                        "policy": policy.value,
                        "exceptions_copied": exceptions_copied,
                        "remaining_triples": remaining,
                        "options": ["MERGE", "KEEP_ISOLATED", "DELETE"],
                        "warning": (
                            "DELETE removes non-exception triples from the source branch graph only. "
                            "Approved exceptions were already copied to the target."
                        ),
                    }
                )
                prompt_written = True
            self.processed_events.add(event_id)
            return MergeHandleResult(
                event_id,
                policy.value,
                exceptions_copied,
                exceptions_copied,
                prompt_written,
            )

        self.prompt_store.write_prompt(
            {
                "event_id": event_id,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "policy": policy.value,
                "exceptions_copied": 0,
                "remaining_triples": len(self.case_wrapper.quads_in_graph(source_uri)),
                "options": ["MERGE", "KEEP_ISOLATED", "DELETE"],
                "warning": (
                    "DELETE discards the entire source branch graph including approved exceptions."
                ),
            }
        )
        self.processed_events.add(event_id)
        return MergeHandleResult(event_id, policy.value, 0, 0, True)

    def resolve_prompt(self, event_id: str, resolution: str) -> dict[str, Any]:
        prompt = self.prompt_store.read_prompt(event_id)
        resolution = resolution.upper()
        if resolution not in prompt["options"]:
            raise KmError(f"Invalid resolution '{resolution}' for event {event_id}")

        source_branch = prompt["source_branch"]
        target_branch = prompt["target_branch"]
        source_uri = branch_path_to_graph_uri(source_branch)
        target_uri = branch_path_to_graph_uri(target_branch)
        triples_imported = 0

        if resolution == "MERGE":
            if prompt["policy"] == BranchMergePolicy.NO_AUTO_MERGE.value:
                triples_imported = self._copy_all_quads(source_uri, target_uri)
            else:
                triples_imported = self._copy_non_exception_quads(source_uri, target_uri)
        elif resolution == "DELETE":
            if prompt["policy"] == BranchMergePolicy.NO_AUTO_MERGE.value:
                self._clear_graph(source_uri)
            else:
                self._delete_non_exception_triples(source_uri)

        self._write_governance(
            event_id,
            source_uri,
            target_uri,
            prompt["policy"],
            resolution=resolution,
            exceptions_copied=int(prompt.get("exceptions_copied", 0)),
            triples_imported=triples_imported,
        )
        self._export_graphs(source_branch, target_branch)
        self.prompt_store.delete_prompt(event_id)
        logger.info(
            "Resolved merge %s with %s (imported %d triples)",
            event_id,
            resolution,
            triples_imported,
        )
        return {
            "event_id": event_id,
            "resolution": resolution,
            "triples_imported": triples_imported,
        }

    def _approved_exception_subjects(self, graph_uri: str) -> set[NamedNode]:
        query = f"""
            SELECT ?exception WHERE {{
                GRAPH <{graph_uri}> {{
                    ?exception a <{KM_LOCAL_EXCEPTION}> ;
                               <{KM_STATUS}> "{STATUS_APPROVED}" .
                }}
            }}
        """
        subjects: set[NamedNode] = set()
        for row in self.case_wrapper.query(query):
            exc = row.get("exception")
            if exc:
                subjects.add(NamedNode(exc))
        return subjects

    def _copy_all_quads(self, source_uri: str, target_uri: str) -> int:
        target = NamedNode(target_uri)
        copied = 0
        for quad in self.case_wrapper.quads_in_graph(source_uri):
            if self.case_wrapper.add_quad(
                Quad(quad.subject, quad.predicate, quad.object, target)
            ):
                copied += 1
        return copied

    def _copy_approved_exceptions(self, source_uri: str, target_uri: str) -> int:
        target = NamedNode(target_uri)
        subjects = self._approved_exception_subjects(source_uri)
        copied = 0
        for quad in self.case_wrapper.quads_in_graph(source_uri):
            if quad.subject in subjects:
                if self.case_wrapper.add_quad(
                    Quad(quad.subject, quad.predicate, quad.object, target)
                ):
                    copied += 1
        return copied

    def _copy_non_exception_quads(self, source_uri: str, target_uri: str) -> int:
        target = NamedNode(target_uri)
        exception_subjects = self._approved_exception_subjects(source_uri)
        copied = 0
        for quad in self.case_wrapper.quads_in_graph(source_uri):
            if quad.subject in exception_subjects:
                continue
            if self.case_wrapper.add_quad(
                Quad(quad.subject, quad.predicate, quad.object, target)
            ):
                copied += 1
        return copied

    def _count_non_exception_triples(self, graph_uri: str) -> int:
        exception_subjects = self._approved_exception_subjects(graph_uri)
        return sum(
            1
            for quad in self.case_wrapper.quads_in_graph(graph_uri)
            if quad.subject not in exception_subjects
        )

    def _delete_non_exception_triples(self, graph_uri: str) -> None:
        graph = NamedNode(graph_uri)
        exception_subjects = self._approved_exception_subjects(graph_uri)
        for quad in list(self.case_wrapper.quads_in_graph(graph_uri)):
            if quad.subject not in exception_subjects:
                self.case_wrapper.remove_quad(quad)

    def _clear_graph(self, graph_uri: str) -> None:
        for quad in list(self.case_wrapper.quads_in_graph(graph_uri)):
            self.case_wrapper.remove_quad(quad)

    def _write_governance(
        self,
        event_id: str,
        source_uri: str,
        target_uri: str,
        policy: str,
        *,
        resolution: str,
        exceptions_copied: int,
        triples_imported: int,
    ) -> None:
        recorded_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        node = NamedNode(f"{KM}{event_id}")
        graph = NamedNode(CASE_GOVERNANCE_GRAPH)
        quads = [
            Quad(node, NamedNode(RDF_TYPE), NamedNode(KM_BRANCH_MERGE_RESOLUTION), graph),
            Quad(node, NamedNode(KM_SOURCE_GRAPH), NamedNode(source_uri), graph),
            Quad(node, NamedNode(KM_TARGET_GRAPH), NamedNode(target_uri), graph),
            Quad(node, NamedNode(KM_RESOLUTION), Literal(resolution), graph),
            Quad(node, NamedNode(KM_POLICY), Literal(policy), graph),
            Quad(
                node,
                NamedNode(KM_EXCEPTIONS_COPIED),
                Literal(str(exceptions_copied)),
                graph,
            ),
            Quad(
                node,
                NamedNode(KM_TRIPLES_IMPORTED),
                Literal(str(triples_imported)),
                graph,
            ),
            Quad(
                node,
                NamedNode(KM_RECORDED_AT),
                Literal(recorded_at, datatype=NamedNode(XSD_DATE_TIME)),
                graph,
            ),
        ]
        for quad in quads:
            self.case_wrapper.store.add(quad)

        export_path = self.case_export.governance_dir / f"{event_id}.ttl"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            "@prefix km: <http://km.local/governance#> .\n\n"
            + serialize_graph_block(CASE_GOVERNANCE_GRAPH, quads),
            encoding="utf-8",
        )

    def _export_graphs(self, source_branch: str, target_branch: str) -> None:
        from km.infrastructure.git.context import _context_from_branch

        self.case_export.export_branch(_context_from_branch(source_branch))
        self.case_export.export_branch(_context_from_branch(target_branch))
