"""SHACL cache prefix binding tests."""

from __future__ import annotations

from pathlib import Path

from rdflib.namespace import SH

from km.infrastructure.rdf.shacl_cache import (
    collect_export_prefixes,
    filter_prefix_bindings,
    inject_lo_sparql_prefixes,
    is_usable_sparql_prefix,
    lo_ontology_uri,
    lo_prefix_name,
    reconcile_graph_prefix_bindings,
)


def test_lo_prefix_name_uses_ontology_id() -> None:
    assert lo_prefix_name("hexagonal-architecture") == "hexagonal_architecture"
    assert lo_prefix_name("hexagonal-bloc") == "hexagonal_bloc"


def test_lo_ontology_uri() -> None:
    assert lo_ontology_uri("hexagonal-bloc") == (
        "http://km.local/learning-ontologies/hexagonal-bloc"
    )


def test_collect_export_prefixes_hexagonal_architecture(lo_package: Path) -> None:
    prefixes = collect_export_prefixes(lo_package)
    assert prefixes["hex"] == "http://architecture.org/hexagonal#"
    assert "brick" not in prefixes


def test_reconcile_graph_prefix_bindings_prefers_export_label() -> None:
    export = {"hex": "http://architecture.org/hexagonal#"}
    resolved = reconcile_graph_prefix_bindings(
        export,
        "hexagonal_architecture",
        "http://architecture.org/hexagonal#",
    )
    assert resolved == {"hex": "http://architecture.org/hexagonal#"}
    assert "hexagonal_architecture" not in resolved


def test_reconcile_graph_prefix_bindings_keeps_config_only_prefix(tmp_path: Path) -> None:
    export: dict[str, str] = {}
    resolved = reconcile_graph_prefix_bindings(
        export,
        "custom_lo",
        "http://example.org/custom#",
    )
    assert resolved == {"custom_lo": "http://example.org/custom#"}


def test_collect_export_prefixes_reads_author_prefixes(tmp_path: Path) -> None:
    lo_root = tmp_path / "hexagonal-bloc"
    exports = lo_root / "exports"
    exports.mkdir(parents=True)
    (exports / "main.ttl").write_text(
        "@prefix hbloc: <http://architecture.org/hexagonal-bloc#> .\n"
        "@prefix hex: <http://architecture.org/hexagonal#> .\n"
        "hbloc:Bloc a <http://www.w3.org/2002/07/owl#Class> .\n",
        encoding="utf-8",
    )
    prefixes = collect_export_prefixes(lo_root)
    assert prefixes["hbloc"] == "http://architecture.org/hexagonal-bloc#"
    assert prefixes["hex"] == "http://architecture.org/hexagonal#"


def test_inject_lo_sparql_prefixes_declares_all_bindings() -> None:
    from rdflib import Graph, Literal, URIRef

    graph = Graph()
    graph.add(
        (
            URIRef("http://example.org/shape"),
            SH.select,
            Literal("SELECT $this WHERE { $this hbloc:dependsOn ?dep }"),
        )
    )
    inject_lo_sparql_prefixes(
        graph,
        lo_ontology_uri("hexagonal-bloc"),
        {
            "hexagonal_bloc": "http://architecture.org/hexagonal-bloc#",
            "hbloc": "http://architecture.org/hexagonal-bloc#",
            "hex": "http://architecture.org/hexagonal#",
        },
    )
    ont = URIRef(lo_ontology_uri("hexagonal-bloc"))
    declared = {
        str(graph.value(dec, SH.prefix)) for dec in graph.objects(ont, SH.declare)
    }
    assert declared == {"hex", "hexagonal_bloc", "hbloc"}


def test_is_usable_sparql_prefix_rejects_empty_and_colon() -> None:
    assert is_usable_sparql_prefix("hex") is True
    assert is_usable_sparql_prefix("") is False
    assert is_usable_sparql_prefix(":") is False
    assert is_usable_sparql_prefix("   ") is False


def test_filter_prefix_bindings_skips_invalid_and_keeps_valid() -> None:
    result = filter_prefix_bindings(
        {
            "": "http://example.org/default#",
            ":": "http://example.org/colon#",
            "hex": "http://architecture.org/hexagonal#",
        }
    )
    assert result == {"hex": "http://architecture.org/hexagonal#"}
    assert "" not in result


def test_collect_export_prefixes_skips_base_default_prefix(
    tmp_path: Path, caplog
) -> None:
    import logging

    caplog.set_level(logging.WARNING, logger="km.shacl_cache")
    lo_root = tmp_path / "base-lo"
    exports = lo_root / "exports"
    exports.mkdir(parents=True)
    (exports / "main.ttl").write_text(
        "@base <http://example.org/> .\n"
        "@prefix ex: <http://example.org/ex#> .\n"
        "ex:Thing a <http://www.w3.org/2002/07/owl#Class> .\n",
        encoding="utf-8",
    )
    prefixes = collect_export_prefixes(lo_root)
    assert "" not in prefixes
    assert prefixes["ex"] == "http://example.org/ex#"


def test_hexagonal_lo_fixture_path_exists() -> None:
    from tests.conftest import HEXAGONAL_LO

    assert HEXAGONAL_LO.is_dir()
    assert (HEXAGONAL_LO / "exports" / "main.ttl").is_file()
    assert "tests/fixtures/lo-packages" in str(HEXAGONAL_LO)
