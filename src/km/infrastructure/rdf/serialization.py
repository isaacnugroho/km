"""Deterministic RDF serialization (spec §2.6)."""

from __future__ import annotations

from pyoxigraph import BlankNode, Literal, NamedNode, Quad

from km.infrastructure.rdf.ref_mapping import branch_path_to_graph_uri


def _term_key(term: object) -> tuple:
    if isinstance(term, NamedNode):
        return ("uri", str(term))
    if isinstance(term, BlankNode):
        return ("bnode", str(term))
    if isinstance(term, Literal):
        if term.language:
            return ("literal", term.value, "lang", term.language)
        if term.datatype:
            return ("literal", term.value, "dt", str(term.datatype))
        return ("literal", term.value)
    return ("unknown", str(term))


def sort_quads(quads: list[Quad]) -> list[Quad]:
    return sorted(quads, key=lambda q: (_term_key(q.subject), _term_key(q.predicate), _term_key(q.object)))


def serialize_graph_block(graph_uri: str, quads: list[Quad]) -> str:
    """Serialize quads as a single GRAPH block in Turtle."""
    lines = [f"GRAPH <{graph_uri}> {{"]
    for quad in sort_quads(quads):
        lines.append(f"    {_format_triple(quad)} .")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _format_triple(quad: Quad) -> str:
    s = _format_term(quad.subject)
    p = _format_term(quad.predicate)
    o = _format_term(quad.object)
    return f"{s} {p} {o}"


def _format_term(term: object) -> str:
    if isinstance(term, NamedNode):
        return f"<{term}>"
    if isinstance(term, BlankNode):
        return term.n3() if hasattr(term, "n3") else f"_:{term}"
    if isinstance(term, Literal):
        if term.language:
            escaped = _escape_literal(term.value)
            return f'"{escaped}"@{term.language}'
        if term.datatype:
            escaped = _escape_literal(term.value)
            return f'"{escaped}"^^<{term.datatype}>'
        escaped = _escape_literal(term.value)
        return f'"{escaped}"'
    return str(term)


def _escape_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
