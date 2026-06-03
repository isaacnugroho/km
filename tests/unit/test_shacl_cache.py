"""SHACL cache prefix binding tests."""

from __future__ import annotations

from pathlib import Path

from rdflib.namespace import SH

from km.infrastructure.rdf.shacl_cache import (
    collect_export_prefixes,
    inject_lo_sparql_prefixes,
    lo_ontology_uri,
    lo_prefix_name,
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
        str(graph.value(dec, SH.prefix))
        for dec in graph.objects(ont, SH.declare)
    }
    assert declared == {"hex", "hexagonal_bloc", "hbloc"}
