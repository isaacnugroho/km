"""Shared test data constants."""

SAMPLE_CASE_TURTLE = """\
@prefix hex: <http://architecture.org/hexagonal#> .
@prefix case: <http://km.local/cases/> .

case:my_core a hex:ApplicationCore .
"""

SAMPLE_CASE_JSONLD = """\
{
  "@context": {
    "hex": "http://architecture.org/hexagonal#",
    "case": "http://km.local/cases/",
    "type": "@type"
  },
  "@id": "case:my_core",
  "@type": "hex:ApplicationCore"
}
"""
