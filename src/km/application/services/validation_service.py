"""SHACL validation with incremental cache and exception filtering (spec §6.2)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from pyoxigraph import NamedNode
from pyshacl import validate
from rdflib import BNode, Graph, URIRef
from rdflib.namespace import RDF, SH

from km.infrastructure.git.context import GitContext
from km.infrastructure.rdf.graph_hash import hash_graph_quads
from km.infrastructure.rdf.shacl_cache import ShaclCache
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("validation")


@dataclass
class ValidationCacheEntry:
    graph_hash: str
    conforms: bool
    violations: list[dict[str, str]]


class ValidationService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        shacl_cache: ShaclCache,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.shacl_cache = shacl_cache
        self._cache: dict[str, ValidationCacheEntry] = {}

    def invalidate(self, graph_uri: str) -> None:
        self._cache.pop(graph_uri, None)
        logger.debug("Validation cache invalidated for %s", graph_uri)

    def reload_shapes(self, shacl_cache: ShaclCache) -> None:
        self.shacl_cache = shacl_cache
        self._cache.clear()
        logger.info("Reloaded SHACL shapes; validation cache cleared")

    def validate_constraints(self, git_context: GitContext) -> dict[str, Any]:
        graph_uri = git_context.graph_uri
        store = self.case_wrapper.store
        current_hash = hash_graph_quads(store, graph_uri)

        cached = self._cache.get(graph_uri)
        if cached and cached.graph_hash == current_hash:
            logger.debug("Validation cache hit for %s", graph_uri)
            return {"conforms": cached.conforms, "violations": list(cached.violations)}

        start = time.perf_counter()
        data_graph = _case_graph_to_rdflib(
            self.case_wrapper,
            graph_uri,
            self.shacl_cache.prefix_bindings,
        )
        conforms, report_graph, _ = validate(
            data_graph,
            shacl_graph=self.shacl_cache.shapes_graph,
            advanced=True,
        )
        raw_violations = _parse_violations(report_graph, self.shacl_cache.shapes_graph)
        filtered = _filter_with_exceptions(self.case_wrapper, graph_uri, raw_violations)
        conforms_now = len(filtered) == 0
        elapsed_ms = (time.perf_counter() - start) * 1000

        if elapsed_ms > 120:
            logger.warning("SHACL validation slow: %.1fms", elapsed_ms)
        else:
            logger.debug("SHACL validation completed in %.1fms", elapsed_ms)

        logger.info(
            "Validation %s: %d violation(s) after exception filter",
            "PASS" if conforms_now else "FAIL",
            len(filtered),
        )

        self._cache[graph_uri] = ValidationCacheEntry(
            graph_hash=current_hash,
            conforms=conforms_now,
            violations=filtered,
        )
        return {"conforms": conforms_now, "violations": filtered}


def _case_graph_to_rdflib(
    wrapper: QuadStoreWrapper,
    graph_uri: str,
    prefix_bindings: dict[str, str] | None = None,
) -> Graph:
    from km.application.services.query_service import _oxi_to_rdflib
    from rdflib import URIRef

    graph = Graph()
    if prefix_bindings:
        for prefix, namespace_uri in prefix_bindings.items():
            graph.bind(prefix, namespace_uri)
    for quad in wrapper.quads_in_graph(graph_uri):
        graph.add(
            (
                _oxi_to_rdflib(quad.subject),
                URIRef(quad.predicate.value),
                _oxi_to_rdflib(quad.object),
            )
        )
    return graph


def _parse_violations(report: Graph, shapes: Graph) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for result in report.subjects(RDF.type, SH.ValidationResult):
        focus = report.value(result, SH.focusNode)
        shape = report.value(result, SH.sourceShape)
        severity = report.value(result, SH.resultSeverity)
        message = report.value(result, SH.resultMessage)

        if focus is None:
            continue

        shape_uri = _resolve_shape_uri(shapes, shape)
        violations.append(
            {
                "focus_node": str(focus),
                "source_shape": shape_uri,
                "severity": _severity_label(severity),
                "message": str(message) if message else "",
            }
        )
    return violations


def _resolve_shape_uri(shapes: Graph, source_shape: object) -> str:
    if source_shape is None:
        return ""
    if isinstance(source_shape, URIRef):
        return str(source_shape)
    if isinstance(source_shape, BNode):
        for shape in shapes.subjects(RDF.type, SH.NodeShape):
            for prop in shapes.objects(shape, SH.property):
                if prop == source_shape:
                    return str(shape)
        return str(source_shape)
    return str(source_shape)


def _severity_label(severity: object) -> str:
    if severity is None:
        return "Violation"
    value = str(severity)
    if "#" in value:
        return value.rsplit("#", 1)[-1]
    return value


def _filter_with_exceptions(
    wrapper: QuadStoreWrapper,
    graph_uri: str,
    violations: list[dict[str, str]],
) -> list[dict[str, str]]:
    from km.domain.governance import (
        KM_BYPASSES_SHAPE,
        KM_LOCAL_EXCEPTION,
        KM_STATUS,
        KM_TARGET_NODE,
        STATUS_APPROVED,
    )

    filtered: list[dict[str, str]] = []
    for violation in violations:
        focus = violation["focus_node"]
        shape = violation["source_shape"]
        ask = f"""
            ASK WHERE {{
                GRAPH <{graph_uri}> {{
                    ?exception a <{KM_LOCAL_EXCEPTION}> ;
                               <{KM_BYPASSES_SHAPE}> <{shape}> ;
                               <{KM_TARGET_NODE}> <{focus}> ;
                               <{KM_STATUS}> "{STATUS_APPROVED}" .
                }}
            }}
        """
        has_exception = wrapper.store.query(ask)
        if isinstance(has_exception, bool):
            approved = has_exception
        else:
            approved = bool(has_exception)
        logger.debug(
            "Exception check focus=%s shape=%s approved=%s",
            focus,
            shape,
            approved,
        )
        if not approved:
            filtered.append(violation)
    return filtered
