"""Tests for legacy path-style Case graph URI migration."""

from __future__ import annotations

from pathlib import Path

from pyoxigraph import NamedNode, Quad

from km.application.services.case_store_service import CaseStoreService
from km.infrastructure.rdf.graph_uri_migration import (
    migrate_legacy_branch_graphs,
    rewrite_case_export_graph_uris,
    rewrite_graph_uri_literals,
)
from km.infrastructure.rdf.ref_mapping import branch_path_to_graph_uri
from km.infrastructure.rdf.store import QuadStoreWrapper


def test_rewrite_graph_uri_literals() -> None:
    text = (
        "GRAPH <http://km.local/graphs/feature/foo> {\n"
        "  <http://km.local/governance#> <http://km.local/governance#sourceGraph> "
        "<http://km.local/graphs/feature/bar> .\n"
        "}\n"
    )
    updated, count = rewrite_graph_uri_literals(text)
    assert count == 2
    assert "http://km.local/graphs/feature-foo" in updated
    assert "http://km.local/graphs/feature-bar" in updated
    assert "graphs/feature/foo" not in updated


def test_rewrite_case_export_graph_uris(tmp_path: Path) -> None:
    graphs_dir = tmp_path / "graphs"
    graphs_dir.mkdir()
    ttl = graphs_dir / "refs-heads-feature-foo.ttl"
    ttl.write_text(
        "GRAPH <http://km.local/graphs/feature/foo> {\n  <http://ex/s> <http://ex/p> <http://ex/o> .\n}\n",
        encoding="utf-8",
    )
    changed = rewrite_case_export_graph_uris(tmp_path)
    assert changed == [ttl]
    assert "http://km.local/graphs/feature-foo" in ttl.read_text(encoding="utf-8")


def test_migrate_legacy_branch_graphs(tmp_path: Path) -> None:
    db_path = tmp_path / "case_quads.db"
    wrapper = QuadStoreWrapper(db_path)
    try:
        legacy = "http://km.local/graphs/feature/legacy"
        slug_uri = branch_path_to_graph_uri("feature/legacy")
        wrapper.add_quad(
            Quad(
                NamedNode("http://ex/s"),
                NamedNode("http://ex/p"),
                NamedNode("http://ex/o"),
                NamedNode(legacy),
            )
        )
        assert migrate_legacy_branch_graphs(wrapper) == 1
        assert wrapper.quads_in_graph(legacy) == []
        assert len(wrapper.quads_in_graph(slug_uri)) == 1
        assert migrate_legacy_branch_graphs(wrapper) == 0
    finally:
        wrapper.close()


def test_case_store_bootstrap_migrates_legacy_graphs(tmp_workspace: Path) -> None:
    km_dir = tmp_workspace / ".km"
    case_db = km_dir / "case_quads.db"
    exports_root = tmp_workspace / "case-exports"

    wrapper = QuadStoreWrapper(case_db)
    try:
        legacy = "http://km.local/graphs/feature/boot"
        wrapper.add_quad(
            Quad(
                NamedNode("http://ex/s"),
                NamedNode("http://ex/p"),
                NamedNode("http://ex/o"),
                NamedNode(legacy),
            )
        )
    finally:
        wrapper.close()

    store = CaseStoreService(tmp_workspace, case_db, exports_root, km_dir)
    store.bootstrap()
    try:
        slug_uri = branch_path_to_graph_uri("feature/boot")
        assert store.wrapper is not None
        assert store.wrapper.quads_in_graph(legacy) == []
        assert len(store.wrapper.quads_in_graph(slug_uri)) == 1
    finally:
        store.close()
