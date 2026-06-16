"""Bidirectional case graph patches (spec addendum A1)."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyoxigraph import Literal, NamedNode, Quad

from km.domain.governance import KM_DELETE_SUBJECT, KM_LOCAL_EXCEPTION, KM_STATUS, STATUS_APPROVED
from km.infrastructure.rdf.parse import parse_facts_optional
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("case_patch")

XSD_BOOLEAN = "http://www.w3.org/2001/XMLSchema#boolean"


@dataclass
class DeletionPlan:
    exact_quads: list[Quad] = field(default_factory=list)
    subject_scoped: list[NamedNode] = field(default_factory=list)


def _is_delete_subject_true(obj: object) -> bool:
    if not isinstance(obj, Literal):
        return False
    if obj.datatype == NamedNode(XSD_BOOLEAN):
        return obj.value.lower() in {"true", "1"}
    return obj.value.lower() == "true"


def parse_deletion_plan(deletions: str, fmt: str, graph_uri: str) -> DeletionPlan:
    quads = parse_facts_optional(deletions, fmt, graph_uri)
    plan = DeletionPlan()
    seen_subjects: set[str] = set()

    for quad in quads:
        if quad.predicate == NamedNode(KM_DELETE_SUBJECT) and _is_delete_subject_true(
            quad.object
        ):
            subject_key = quad.subject.value
            if subject_key in seen_subjects:
                raise ValueError(
                    f"Duplicate km:deleteSubject directive for subject <{subject_key}>"
                )
            seen_subjects.add(subject_key)
            if not isinstance(quad.subject, NamedNode):
                raise ValueError("km:deleteSubject requires a named subject URI")
            plan.subject_scoped.append(quad.subject)
            continue
        plan.exact_quads.append(quad)

    return plan


def is_protected_exception_subject(
    wrapper: QuadStoreWrapper, graph_uri: str, subject: NamedNode
) -> bool:
    query = f"""
        ASK {{
            GRAPH <{graph_uri}> {{
                <{subject.value}> a <{KM_LOCAL_EXCEPTION}> ;
                                <{KM_STATUS}> "{STATUS_APPROVED}" .
            }}
        }}
    """
    return wrapper.ask(query)


def apply_patch(
    wrapper: QuadStoreWrapper,
    graph_uri: str,
    deletion_plan: DeletionPlan,
    insertion_quads: list[Quad],
) -> tuple[int, int]:
    """Apply deletions then insertions atomically. Returns (removed, added)."""
    snapshot = list(wrapper.quads_in_graph(graph_uri))
    removed = 0
    added = 0

    try:
        for quad in deletion_plan.exact_quads:
            if wrapper.remove_quad(quad):
                removed += 1

        for subject in deletion_plan.subject_scoped:
            if is_protected_exception_subject(wrapper, graph_uri, subject):
                raise ValueError(
                    f"Cannot delete approved local exception subject <{subject.value}>"
                )
            removed += wrapper.remove_quads_for_subject(graph_uri, subject)

        for quad in insertion_quads:
            if wrapper.add_quad(quad):
                added += 1
    except Exception:
        wrapper.restore_graph_quads(graph_uri, snapshot)
        raise

    return removed, added
