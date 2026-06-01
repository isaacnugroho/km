"""Migrate legacy path-style Case graph URIs to branch slugs (spec §2.6)."""

from __future__ import annotations

import re
from pathlib import Path

from pyoxigraph import NamedNode, Quad

from km.infrastructure.rdf.ref_mapping import (
    GRAPH_BASE,
    branch_path_to_graph_uri,
    branch_path_to_slug,
)
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("graph_uri_migration")

_LEGACY_GRAPH_URI_RE = re.compile(
    r"http://km\.local/graphs/([^>\s\"]+)"
)


def _legacy_branch_graph_uris(wrapper: QuadStoreWrapper) -> list[str]:
    prefix = f"{GRAPH_BASE}/"
    uris: set[str] = set()
    for row in wrapper.query(
        f"""
        SELECT DISTINCT ?g WHERE {{
            GRAPH ?g {{ ?s ?p ?o }}
            FILTER(STRSTARTS(STR(?g), "{prefix}"))
        }}
        """
    ):
        graph = row.get("g")
        if graph and graph.startswith(prefix):
            suffix = graph[len(prefix) :]
            if "/" in suffix:
                uris.add(graph)
    return sorted(uris)


def _clone_graph(wrapper: QuadStoreWrapper, source_uri: str, target_uri: str) -> int:
    target = NamedNode(target_uri)
    copied = 0
    for quad in wrapper.quads_in_graph(source_uri):
        if wrapper.add_quad(Quad(quad.subject, quad.predicate, quad.object, target)):
            copied += 1
    return copied


def _clear_graph(wrapper: QuadStoreWrapper, graph_uri: str) -> None:
    for quad in list(wrapper.quads_in_graph(graph_uri)):
        wrapper.remove_quad(quad)


def migrate_legacy_branch_graphs(wrapper: QuadStoreWrapper) -> int:
    """Copy quads from path-style graph URIs to slug URIs; remove legacy graphs."""
    migrated = 0
    for old_uri in _legacy_branch_graph_uris(wrapper):
        branch_path = old_uri[len(f"{GRAPH_BASE}/") :]
        new_uri = branch_path_to_graph_uri(branch_path)
        if new_uri == old_uri:
            continue
        if wrapper.quads_in_graph(new_uri):
            logger.warning(
                "Skipping graph URI migration %s → %s: target graph already has triples",
                old_uri,
                new_uri,
            )
            continue
        copied = _clone_graph(wrapper, old_uri, new_uri)
        if copied:
            _clear_graph(wrapper, old_uri)
            logger.info(
                "Migrated %d quad(s) from %s to %s",
                copied,
                old_uri,
                new_uri,
            )
            migrated += 1
    return migrated


def _slug_graph_uri(uri: str) -> str:
    prefix = f"{GRAPH_BASE}/"
    if not uri.startswith(prefix):
        return uri
    suffix = uri[len(prefix) :]
    if "/" not in suffix:
        return uri
    return f"{prefix}{branch_path_to_slug(suffix)}"


def rewrite_graph_uri_literals(text: str) -> tuple[str, int]:
    """Replace legacy path-style ``http://km.local/graphs/…`` URIs with slug URIs."""

    replacements = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal replacements
        old = match.group(0)
        new = _slug_graph_uri(old)
        if new != old:
            replacements += 1
        return new

    return _LEGACY_GRAPH_URI_RE.sub(repl, text), replacements


def rewrite_case_export_graph_uris(exports_root: Path) -> list[Path]:
    """Rewrite ``GRAPH`` headers and governance graph literals under ``case-exports/``."""
    changed: list[Path] = []
    for subdir in ("graphs", "governance"):
        directory = exports_root / subdir
        if not directory.is_dir():
            continue
        for ttl_file in sorted(directory.glob("*.ttl")):
            original = ttl_file.read_text(encoding="utf-8")
            updated, count = rewrite_graph_uri_literals(original)
            if count and updated != original:
                ttl_file.write_text(updated, encoding="utf-8")
                logger.info("Rewrote %d graph URI(s) in %s", count, ttl_file)
                changed.append(ttl_file)
    return changed
