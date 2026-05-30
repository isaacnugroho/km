"""Feature gate — controls which surfaces are implemented."""

from __future__ import annotations

from km.exceptions import FeatureNotImplementedError

# Phase 4c: approve_semantic_mr with canonical merge and LO cache/SHACL refresh enabled.
FEATURES: dict[str, bool] = {
    "get_system_status": True,
    "ingest_case_facts": True,
    "validate_constraints": True,
    "propose_local_exception": True,
    "approve_local_exception": True,
    "query_semantic_graph": True,
    "propose_semantic_mr": True,
    "approve_semantic_mr": True,
    "resource:schemas/learning-ontologies": True,
    "resource:case/active-graph": True,
    "resource:case/active-exceptions": True,
    "resource:lo/canonical": True,
    "resource:lo/governance": True,
    "resource:mr": True,
    "cli:export-case": False,
}


def require_implemented(feature: str) -> None:
    if not FEATURES.get(feature, False):
        raise FeatureNotImplementedError(feature)


def release(feature: str) -> None:
    """Enable a feature (used when completing later phases)."""
    FEATURES[feature] = True
