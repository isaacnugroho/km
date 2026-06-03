"""Pre-compiled SHACL shapes from LO canonical graphs (spec §3.2)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

from km.application.services.lo_cache_service import LOCacheEntry
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("shacl_cache")

KM_LEARNING_ONTOLOGY = "http://km.local/learning-ontologies/"


def lo_prefix_name(ontology_id: str) -> str:
    """Return the canonical SPARQL prefix label for an LO binding (from ontology_id)."""
    return ontology_id.replace("-", "_")


def lo_ontology_uri(ontology_id: str) -> str:
    """Named resource anchoring sh:declare / sh:prefixes for an LO binding."""
    return f"{KM_LEARNING_ONTOLOGY}{ontology_id}"


def collect_export_prefixes(source_path: Path) -> dict[str, str]:
    """Read @prefix declarations from LO exports/main.ttl (authoritative for SPARQL in shapes)."""
    main_ttl = source_path / "exports" / "main.ttl"
    if not main_ttl.is_file():
        return {}
    parsed = Graph()
    parsed.parse(main_ttl, format="turtle")
    bindings: dict[str, str] = {}
    for prefix, namespace in parsed.namespace_manager.namespaces():
        bindings[str(prefix)] = str(namespace)
    return bindings


def inject_lo_sparql_prefixes(
    graph: Graph,
    ontology_uri: str,
    prefix_bindings: dict[str, str],
) -> None:
    """Inject sh:declare and sh:prefixes so pyshacl resolves LO prefixes in SPARQL constraints."""
    ont = URIRef(ontology_uri.rstrip("#/"))

    for prefix, namespace_uri in sorted(prefix_bindings.items()):
        ns = URIRef(
            namespace_uri
            if namespace_uri.endswith("#")
            else f"{namespace_uri.rstrip('/')}#"
        )
        declare_node: BNode | URIRef | None = None
        for dec in graph.objects(ont, SH.declare):
            existing_prefix = graph.value(dec, SH.prefix)
            if existing_prefix == Literal(prefix):
                declare_node = dec
                break

        if declare_node is None:
            declare_node = BNode()
            graph.add((ont, SH.declare, declare_node))
            graph.add((declare_node, SH.prefix, Literal(prefix)))
            graph.add((declare_node, SH.namespace, Literal(str(ns), datatype=XSD.anyURI)))

    if (ont, RDF.type, OWL.Ontology) not in graph:
        graph.add((ont, RDF.type, OWL.Ontology))

    for constraint in graph.subjects(SH.select, None):
        if not list(graph.objects(constraint, SH.prefixes)):
            graph.add((constraint, SH.prefixes, ont))


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
    prefix_bindings: dict[str, str] = field(default_factory=dict)

    @classmethod
    def compile_from_lo_entries(cls, entries: list[LOCacheEntry]) -> ShaclCache:
        start = time.perf_counter()
        merged = Graph()
        shape_count = 0
        ontology_ids: list[str] = []
        prefix_bindings: dict[str, str] = {}

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
                primary_ns = f"{prefix_base}#"
                primary_prefix = lo_prefix_name(entry.binding.ontology_id)
                lo_prefixes = collect_export_prefixes(entry.source_path)
                lo_prefixes[primary_prefix] = primary_ns

                for prefix_name, ns_uri in lo_prefixes.items():
                    merged.bind(prefix_name, Namespace(ns_uri))
                    prefix_bindings[prefix_name] = ns_uri

                for triple in lo_graph:
                    merged.add(triple)
                inject_lo_sparql_prefixes(
                    merged,
                    entry.lo_config.base_uri,
                    lo_prefixes,
                )

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
        return cls(
            shapes_graph=merged,
            shape_count=shape_count,
            ontology_ids=ontology_ids,
            prefix_bindings=prefix_bindings,
        )
