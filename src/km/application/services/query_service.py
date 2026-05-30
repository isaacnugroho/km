"""SPARQL query over merged case + LO canonical graphs."""

from __future__ import annotations

import re
import time
from typing import Any

from km.application.services.lo_cache_service import LOCacheEntry
from km.exceptions import KmError
from km.infrastructure.git.context import GitContext
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger
from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
from rdflib.query import Result

logger = get_logger("query")

READONLY_FORBIDDEN = re.compile(
    r"\b(INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY|CONSTRUCT\s+.*\bINSERT)\b",
    re.IGNORECASE,
)
MR_GRAPH_PATTERN = re.compile(r"GRAPH\s*<[^>]+/mr/[^>]+>", re.IGNORECASE)


class QueryService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        lo_cache_entries: list[LOCacheEntry],
        git_context: GitContext,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.lo_cache_entries = lo_cache_entries
        self.git_context = git_context

    def query(self, sparql: str) -> dict[str, Any]:
        if not sparql or not sparql.strip():
            raise KmError("Empty SPARQL query")

        normalized = sparql.strip()
        upper = normalized.upper()
        if not (upper.startswith("SELECT") or upper.startswith("ASK") or upper.startswith("PREFIX")):
            if "SELECT" not in upper and "ASK" not in upper:
                raise KmError("Only read-only SELECT or ASK queries are supported")

        if READONLY_FORBIDDEN.search(normalized):
            raise KmError("Only read-only SELECT or ASK queries are supported")

        if MR_GRAPH_PATTERN.search(normalized):
            logger.info("MR proposal graph queries deferred to Phase 4")
            raise KmError("Querying MR proposal graphs is not yet implemented")

        start = time.perf_counter()
        dataset = self._build_dataset()
        result = dataset.query(normalized)
        elapsed_ms = (time.perf_counter() - start) * 1000

        payload = _result_to_sparql_json(result, normalized)
        bindings = payload.get("results", {}).get("bindings", [])
        if len(bindings) > 10_000:
            logger.warning("Large query result: %d bindings", len(bindings))
        if elapsed_ms > 20:
            logger.warning("Slow SPARQL query: %.1fms", elapsed_ms)
        else:
            logger.debug("SPARQL query completed in %.1fms", elapsed_ms)

        return payload

    def _build_dataset(self) -> Graph:
        merged = Graph()
        case_quads = self.case_wrapper.quads_in_graph(self.git_context.graph_uri)
        _add_quads_to_graph(merged, case_quads)

        for entry in self.lo_cache_entries:
            lo_wrapper = QuadStoreWrapper(entry.cache_db)
            try:
                canonical_uri = entry.lo_config.named_graphs.canonical
                lo_quads = lo_wrapper.quads_in_graph(canonical_uri)
                _add_quads_to_graph(merged, lo_quads)
            finally:
                lo_wrapper.close()

        graph_uris = [self.git_context.graph_uri] + [
            e.lo_config.named_graphs.canonical for e in self.lo_cache_entries
        ]
        logger.debug("Query dataset graphs: %s", graph_uris)
        return merged


def _add_quads_to_graph(target: Graph, quads: list) -> None:
    from rdflib import BNode, Literal as RDFLiteral, URIRef
    from pyoxigraph import BlankNode, Literal, NamedNode

    for quad in quads:
        s = _oxi_to_rdflib(quad.subject)
        p = URIRef(quad.predicate.value)
        o = _oxi_to_rdflib(quad.object)
        target.add((s, p, o))


def _oxi_to_rdflib(term: object) -> URIRef | BNode | RDFLiteral:
    from rdflib import BNode, Literal as RDFLiteral, URIRef
    from pyoxigraph import BlankNode, Literal, NamedNode

    if isinstance(term, NamedNode):
        return URIRef(term.value)
    if isinstance(term, BlankNode):
        return BNode(term.value)
    if isinstance(term, Literal):
        if term.language:
            return RDFLiteral(term.value, lang=term.language)
        if term.datatype:
            return RDFLiteral(term.value, datatype=URIRef(term.datatype.value))
        return RDFLiteral(term.value)
    return RDFLiteral(str(term))


def _result_to_sparql_json(result: Result, query: str) -> dict[str, Any]:
    if result.type == "ASK":
        return {"head": {}, "results": {"boolean": bool(result.askAnswer)}}

    vars_list = [str(v) for v in result.vars]
    bindings = []
    for row in result:
        binding: dict[str, dict[str, str]] = {}
        for var in result.vars:
            term = row[var]
            if term is None:
                continue
            binding[str(var)] = _term_to_binding(term)
        bindings.append(binding)

    return {"head": {"vars": vars_list}, "results": {"bindings": bindings}}


def _term_to_binding(term: object) -> dict[str, str]:
    from rdflib import BNode, Literal as RDFLiteral, URIRef

    if isinstance(term, URIRef):
        return {"type": "uri", "value": str(term)}
    if isinstance(term, BNode):
        return {"type": "bnode", "value": str(term)}
    if isinstance(term, RDFLiteral):
        value: dict[str, str] = {"type": "literal", "value": str(term)}
        if term.language:
            value["xml:lang"] = term.language
        elif term.datatype:
            value["datatype"] = str(term.datatype)
        return value
    return {"type": "literal", "value": str(term)}
