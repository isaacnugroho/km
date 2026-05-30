"""Convert between rdflib terms and pyoxigraph quads."""

from __future__ import annotations

import json
from collections.abc import Iterable

from pyoxigraph import BlankNode, Literal, NamedNode, Quad
from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
from rdflib.plugins.parsers.jsonld import to_rdf

from km.logging_config import get_logger

logger = get_logger("rdf.parse")

SUPPORTED_FORMATS = {"json-ld", "turtle", "ttl"}


def parse_facts(facts: str, fmt: str, graph_uri: str) -> list[Quad]:
    normalized = fmt.lower()
    if normalized == "ttl":
        normalized = "turtle"
    if normalized not in SUPPORTED_FORMATS and normalized != "turtle":
        raise ValueError(f"Unsupported format: {fmt}. Use json-ld or turtle.")

    if not facts or not facts.strip():
        raise ValueError("Empty facts payload")

    if normalized == "json-ld":
        triples = _parse_json_ld(facts)
    else:
        graph = Graph()
        graph.parse(data=facts, format="turtle")
        triples = graph

    return _triples_to_quads(triples, graph_uri)


def _parse_json_ld(facts: str) -> Graph:
    """Parse JSON-LD into an rdflib Graph without deprecated parser paths."""
    graph = Graph()
    to_rdf(json.loads(facts), graph)
    return graph


def _triples_to_quads(triples: Iterable[tuple[object, object, object]], graph_uri: str) -> list[Quad]:
    graph_node = NamedNode(graph_uri)
    return [
        Quad(
            _to_oxi_term(subject),
            _to_oxi_term(predicate),
            _to_oxi_term(obj),
            graph_node,
        )
        for subject, predicate, obj in triples
    ]


def _to_oxi_term(term: object) -> NamedNode | BlankNode | Literal:
    if isinstance(term, URIRef):
        return NamedNode(str(term))
    if isinstance(term, BNode):
        return BlankNode(str(term))
    if isinstance(term, RDFLiteral):
        if term.language:
            return Literal(term, language=term.language)
        if term.datatype:
            return Literal(term, datatype=NamedNode(str(term.datatype)))
        return Literal(term)
    raise TypeError(f"Unsupported RDF term type: {type(term)}")
