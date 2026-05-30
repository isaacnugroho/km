"""Clone-on-write branch inheritance (spec §5.2)."""

from __future__ import annotations

from pathlib import Path

from pyoxigraph import NamedNode, Quad

from km.application.services.case_export_service import CaseExportService
from km.infrastructure.git.context import GitContextHolder
from km.infrastructure.git.merge_base import detect_parent_branch
from km.infrastructure.rdf.ref_mapping import branch_path_to_graph_uri
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("branch_inheritance")


class BranchInheritanceService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        case_export: CaseExportService,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.case_export = case_export

    def ensure_inherited(self, git: GitContextHolder, workspace_root: Path) -> int:
        graph_uri = git.context.graph_uri
        if self._graph_has_triples(graph_uri):
            return 0

        parent_branch = detect_parent_branch(workspace_root, git.context.branch_path)
        if not parent_branch:
            logger.warning(
                "No parent branch detected for %s; leaving empty graph",
                git.context.branch_path,
            )
            return 0

        parent_uri = branch_path_to_graph_uri(parent_branch)
        if not self._graph_has_triples(parent_uri):
            logger.warning(
                "Parent graph %s is empty; cannot inherit for %s",
                parent_uri,
                graph_uri,
            )
            return 0

        copied = self._clone_graph(parent_uri, graph_uri)
        if copied:
            self.case_export.export_branch(git.context)
            logger.info(
                "Inherited %d triple(s) from %s into %s",
                copied,
                parent_branch,
                git.context.branch_path,
            )
        return copied

    def _graph_has_triples(self, graph_uri: str) -> bool:
        return bool(self.case_wrapper.quads_in_graph(graph_uri))

    def _clone_graph(self, source_uri: str, target_uri: str) -> int:
        target = NamedNode(target_uri)
        copied = 0
        for quad in self.case_wrapper.quads_in_graph(source_uri):
            new_quad = Quad(quad.subject, quad.predicate, quad.object, target)
            if self.case_wrapper.add_quad(new_quad):
                copied += 1
        return copied
