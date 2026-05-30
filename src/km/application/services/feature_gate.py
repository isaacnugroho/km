"""Feature gate — controls which surfaces are implemented."""

from __future__ import annotations

from km.exceptions import FeatureNotImplementedError

# Phase 2: case ingest, query, and active-graph resource enabled.
FEATURES: dict[str, bool] = {
    "get_system_status": True,
    "ingest_case_facts": True,
    "validate_constraints": False,
    "propose_local_exception": False,
    "approve_local_exception": False,
    "query_semantic_graph": True,
    "propose_semantic_mr": False,
    "approve_semantic_mr": False,
    "resource:schemas/learning-ontologies": False,
    "resource:case/active-graph": True,
    "resource:case/active-exceptions": False,
    "resource:lo/canonical": False,
    "resource:lo/governance": False,
    "resource:mr": False,
    "cli:export-case": False,
}


def require_implemented(feature: str) -> None:
    if not FEATURES.get(feature, False):
        raise FeatureNotImplementedError(feature)


def release(feature: str) -> None:
    """Enable a feature (used when completing later phases)."""
    FEATURES[feature] = True
