"""Case graph state hash for Phase 3 validation dirty-flag."""

from __future__ import annotations

import hashlib

from pyoxigraph import NamedNode, Quad, Store


def hash_graph_quads(store: Store, graph_uri: str) -> str:
    graph = NamedNode(graph_uri)
    quads = sort_quad_bytes(store, graph)
    return hashlib.sha256(b"".join(quads)).hexdigest()


def sort_quad_bytes(store: Store, graph: NamedNode) -> list[bytes]:
    items: list[bytes] = []
    for quad in store.quads_for_pattern(None, None, None, graph):
        items.append(_quad_digest(quad))
    items.sort()
    return items


def _quad_digest(quad: Quad) -> bytes:
    parts = (str(quad.subject), str(quad.predicate), str(quad.object))
    return "|".join(parts).encode("utf-8")
