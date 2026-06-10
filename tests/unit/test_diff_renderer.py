"""Unit tests for semantic MR diff rendering."""

from __future__ import annotations

from km.infrastructure.rdf.diff_renderer import (
    render_semantic_diff,
    summarize_semantic_changes,
)

SAMPLE_INSERTIONS = """
@prefix hex: <http://architecture.org/hexagonal#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

hex:PromotionShape a sh:NodeShape ;
    sh:path hex:promotedField .

hex:PromotionClass a hex:ArchitectureConcept ;
    rdfs:label "Promotion" .
"""

SAMPLE_DELETIONS = """
@prefix hex: <http://architecture.org/hexagonal#> .
hex:LegacyClass a hex:ArchitectureConcept .
"""


def test_render_semantic_diff_includes_insertions_and_deletions() -> None:
    diff = render_semantic_diff(SAMPLE_INSERTIONS, SAMPLE_DELETIONS)
    assert "```diff" in diff
    assert "+@prefix hex:" in diff
    assert "-hex:LegacyClass" in diff
    assert "hex:PromotionClass" in diff


def test_render_semantic_diff_skips_blank_lines() -> None:
    diff = render_semantic_diff("\n\n@prefix x: <http://x#> .\n\n", "")
    assert "+@prefix x:" in diff
    assert "\n+\n" not in diff


def test_summarize_invalid_turtle() -> None:
    summary = summarize_semantic_changes("not valid turtle {{{", "also bad")
    assert "No parseable semantic diff" in summary


def test_summarize_semantic_changes_detects_types_and_shapes() -> None:
    summary = summarize_semantic_changes(SAMPLE_INSERTIONS, SAMPLE_DELETIONS)
    assert "Triple delta" in summary
    assert "SHACL shape" in summary
    assert "type" in summary.lower()


def test_summarize_deletions_only() -> None:
    summary = summarize_semantic_changes("", SAMPLE_DELETIONS)
    assert "Removed type" in summary


def test_summarize_parsed_without_entities() -> None:
    turtle = "@prefix hex: <http://architecture.org/hexagonal#> .\nhex:lonely hex:marker \"x\" .\n"
    summary = summarize_semantic_changes(turtle, "")
    assert "no typed entities or SHACL shapes detected" in summary


def test_term_label_without_fragment() -> None:
    summary = summarize_semantic_changes(
        "@prefix ex: <http://example.com/ontology/> .\nex:Item a ex:Type .\n",
        "",
    )
    assert "Item" in summary
    assert "Type" in summary
