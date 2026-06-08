"""SPARQL query over merged case + LO canonical graphs."""

from __future__ import annotations

import re
import time
from typing import Any

from km.application.services.lo_cache_service import LOCacheEntry
from km.exceptions import KmError
from km.infrastructure.git.context import GitContextHolder
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger
from pyoxigraph import DefaultGraph, Quad

logger = get_logger("query")

READONLY_FORBIDDEN = re.compile(
    r"\b(INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY|CONSTRUCT\s+.*\bINSERT)\b",
    re.IGNORECASE,
)
MR_GRAPH_PATTERN = re.compile(r"GRAPH\s*<[^>]+/mr/[^>]+>", re.IGNORECASE)
_ASK_QUERY = re.compile(r"^\s*ASK\b", re.IGNORECASE | re.DOTALL)


class QueryService:
    def __init__(
        self,
        case_wrapper: QuadStoreWrapper,
        lo_cache_entries: list[LOCacheEntry],
        git: GitContextHolder,
    ) -> None:
        self.case_wrapper = case_wrapper
        self.lo_cache_entries = lo_cache_entries
        self.git = git

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
        try:
            if _is_ask_query(normalized):
                payload = {
                    "head": {},
                    "results": {"boolean": dataset.ask(normalized)},
                }
            else:
                rows = dataset.query(normalized)
                payload = _rows_to_sparql_json(rows)
        finally:
            dataset.close()

        elapsed_ms = (time.perf_counter() - start) * 1000
        bindings = payload.get("results", {}).get("bindings", [])
        if len(bindings) > 10_000:
            logger.warning("Large query result: %d bindings", len(bindings))
        if elapsed_ms > 20:
            logger.warning("Slow SPARQL query: %.1fms", elapsed_ms)
        else:
            logger.debug("SPARQL query completed in %.1fms", elapsed_ms)

        return payload

    def _build_dataset(self) -> QuadStoreWrapper:
        wrapper = QuadStoreWrapper.in_memory()
        default = DefaultGraph()

        case_quads = self.case_wrapper.quads_in_graph(self.git.context.graph_uri)
        for quad in case_quads:
            wrapper.store.add(
                Quad(quad.subject, quad.predicate, quad.object, default)
            )

        for entry in self.lo_cache_entries:
            lo_wrapper = QuadStoreWrapper(entry.cache_db)
            try:
                canonical_uri = entry.lo_config.named_graphs.canonical
                lo_quads = lo_wrapper.quads_in_graph(canonical_uri)
                for quad in lo_quads:
                    wrapper.store.add(
                        Quad(quad.subject, quad.predicate, quad.object, default)
                    )
            finally:
                lo_wrapper.close()

        graph_uris = [self.git.context.graph_uri] + [
            e.lo_config.named_graphs.canonical for e in self.lo_cache_entries
        ]
        logger.debug("Query dataset graphs: %s", graph_uris)
        return wrapper


def _is_ask_query(sparql: str) -> bool:
    stripped = re.sub(
        r"PREFIX\s+[\w-]+:\s*<[^>]+>\s*",
        "",
        sparql,
        flags=re.IGNORECASE,
    ).strip()
    return bool(_ASK_QUERY.match(stripped))


def _rows_to_sparql_json(rows: list[dict[str, str | None]]) -> dict[str, Any]:
    if not rows:
        return {"head": {"vars": []}, "results": {"bindings": []}}
    vars_list = list(rows[0].keys())
    bindings = []
    for row in rows:
        binding: dict[str, dict[str, str]] = {}
        for var in vars_list:
            value = row.get(var)
            if value is None:
                continue
            binding[var] = _string_to_binding(value)
        bindings.append(binding)
    return {"head": {"vars": vars_list}, "results": {"bindings": bindings}}


def _oxi_to_rdflib(term: object):
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


def _string_to_binding(value: str) -> dict[str, str]:
    if value.startswith("http://") or value.startswith("https://"):
        return {"type": "uri", "value": value}
    if value.startswith("_:"):
        return {"type": "bnode", "value": value}
    return {"type": "literal", "value": value}
