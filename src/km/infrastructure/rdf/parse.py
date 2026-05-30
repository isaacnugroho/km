"""Convert between rdflib terms and pyoxigraph quads."""

from __future__ import annotations

from pyoxigraph import BlankNode, Literal, NamedNode, Quad
from rdflib import BNode, Graph, Literal as RDFLiteral, URIRef
from rdflib.namespace import RDF

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

    rdflib_format = "json-ld" if normalized == "json-ld" else "turtle"
    graph = Graph()
    graph.parse(data=facts, format=rdflib_format)

    graph_node = NamedNode(graph_uri)
    quads: list[Quad] = []
    for subject, predicate, obj in graph:
        quads.append(
            Quad(
                _to_oxi_term(subject),
                _to_oxi_term(predicate),
                _to_oxi_term(obj),
                graph_node,
            )
        )
    return quads


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
