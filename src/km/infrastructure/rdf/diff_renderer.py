"""Semantic diff blocks for MR review documents (spec §7.2)."""

from __future__ import annotations

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, SH

RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
SH_NODE_SHAPE = URIRef("http://www.w3.org/ns/shacl#NodeShape")


def render_semantic_diff(diff_insertions: str, diff_deletions: str = "") -> str:
    lines = ["```diff", "@@ exports/main.ttl @@"]
    for line in diff_deletions.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(f"-{stripped}")
    for line in diff_insertions.splitlines():
        stripped = line.strip()
        if stripped:
            lines.append(f"+{stripped}")
    lines.append("```")
    return "\n".join(lines)


def _parse_turtle(turtle: str) -> Graph | None:
    if not turtle or not turtle.strip():
        return None
    try:
        graph = Graph()
        graph.parse(data=turtle, format="turtle")
        return graph
    except Exception:
        return None


def _type_labels(graph: Graph, *, added: bool) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for subject, obj in graph.subject_objects(RDF.type):
        type_uri = str(obj)
        if type_uri in (
            str(RDF.Property),
            str(OWL.Class),
            str(OWL.ObjectProperty),
            str(OWL.DatatypeProperty),
        ):
            continue
        subject_label = _term_label(graph, subject)
        type_label = _term_label(graph, obj)
        entry = f"{subject_label} → {type_label}"
        if entry not in seen:
            seen.add(entry)
            prefix = "New" if added else "Removed"
            labels.append(f"- **{prefix} type:** `{entry}`")
    return labels


def _term_label(graph: Graph, term: object) -> str:
    value = str(term)
    if value.startswith("http://") or value.startswith("https://"):
        fragment = value.rsplit("#", 1)[-1]
        if fragment and fragment != value:
            return fragment
        return value.rsplit("/", 1)[-1]
    return value


def _shape_labels(graph: Graph, *, added: bool) -> list[str]:
    labels: list[str] = []
    for subject in graph.subjects(RDF.type, SH_NODE_SHAPE):
        prefix = "New" if added else "Removed"
        labels.append(f"- **{prefix} SHACL shape:** `{_term_label(graph, subject)}`")
    return labels


def _predicate_labels(graph: Graph, *, added: bool) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for subject, predicate, _obj in graph.triples((None, None, None)):
        pred = str(predicate)
        if pred in (str(RDF.type), str(SH.path)):
            continue
        if "shacl" in pred or pred.endswith("path"):
            subj_label = _term_label(graph, subject)
            pred_label = _term_label(graph, predicate)
            entry = f"{subj_label} — `{pred_label}`"
            if entry not in seen:
                seen.add(entry)
                prefix = "New" if added else "Removed"
                labels.append(f"- **{prefix} property arc:** `{entry}`")
    return labels[:10]


def summarize_semantic_changes(diff_insertions: str, diff_deletions: str = "") -> str:
    """Produce human-readable bullets from Turtle diff insertions/deletions."""
    insert_graph = _parse_turtle(diff_insertions)
    delete_graph = _parse_turtle(diff_deletions)

    if insert_graph is None and delete_graph is None:
        return "- No parseable semantic diff (empty or invalid Turtle)."

    lines: list[str] = []
    ins_count = len(insert_graph) if insert_graph else 0
    del_count = len(delete_graph) if delete_graph else 0
    lines.append(
        f"- **Triple delta:** +{ins_count} insertion(s), -{del_count} deletion(s)"
    )

    if insert_graph:
        lines.extend(_type_labels(insert_graph, added=True))
        lines.extend(_shape_labels(insert_graph, added=True))
        lines.extend(_predicate_labels(insert_graph, added=True))
    if delete_graph:
        lines.extend(_type_labels(delete_graph, added=False))
        lines.extend(_shape_labels(delete_graph, added=False))

    if len(lines) == 1:
        lines.append("- Diff parsed but no typed entities or SHACL shapes detected.")
    return "\n".join(lines)
