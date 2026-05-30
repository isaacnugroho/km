"""Pre-compiled SHACL shapes from LO canonical graphs (spec §3.2)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from rdflib import Graph, Namespace

from km.application.services.lo_cache_service import LOCacheEntry
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("shacl_cache")


def _quads_to_rdflib(quads: list) -> Graph:
    from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
    from pyoxigraph import BlankNode, Literal, NamedNode

    graph = Graph()
    for quad in quads:
        s = _term(quad.subject)
        p = URIRef(quad.predicate.value)
        o = _term(quad.object)
        graph.add((s, p, o))
    return graph


def _term(term: object):
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


@dataclass
class ShaclCache:
    shapes_graph: Graph
    shape_count: int
    ontology_ids: list[str]

    @classmethod
    def compile_from_lo_entries(cls, entries: list[LOCacheEntry]) -> ShaclCache:
        start = time.perf_counter()
        merged = Graph()
        shape_count = 0
        ontology_ids: list[str] = []

        from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

        merged.bind("sh", SH)
        merged.bind("rdf", RDF)
        merged.bind("rdfs", RDFS)
        merged.bind("xsd", XSD)
        merged.bind("owl", OWL)

        for entry in entries:
            ontology_ids.append(entry.binding.ontology_id)
            wrapper = QuadStoreWrapper(entry.cache_db)
            try:
                canonical_uri = entry.lo_config.named_graphs.canonical
                quads = wrapper.quads_in_graph(canonical_uri)
                lo_graph = _quads_to_rdflib(quads)
                prefix_base = entry.lo_config.base_uri.rstrip("#/")
                ns = Namespace(f"{prefix_base}#")
                if entry.binding.ontology_id == "hexagonal-architecture":
                    merged.bind("hex", ns)
                else:
                    merged.bind(entry.binding.ontology_id.replace("-", "_"), ns)
                for prefix, ns_uri in lo_graph.namespace_manager.namespaces():
                    merged.bind(prefix, ns_uri)
                for triple in lo_graph:
                    merged.add(triple)
                from rdflib import URIRef

                for _ in lo_graph.subjects(RDF.type, URIRef("http://www.w3.org/ns/shacl#NodeShape")):
                    shape_count += 1
            finally:
                wrapper.close()

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Compiled SHACL cache: %d NodeShape(s) from %d ontology(ies) in %.1fms",
            shape_count,
            len(entries),
            elapsed_ms,
        )
        logger.debug("SHACL cache ontology_ids=%s", ontology_ids)
        return cls(shapes_graph=merged, shape_count=shape_count, ontology_ids=ontology_ids)
