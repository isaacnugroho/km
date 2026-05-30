"""Feature gate — controls which surfaces are implemented."""

from __future__ import annotations

from km.exceptions import FeatureNotImplementedError

# Phase 1: only get_system_status and startup pipeline are live.
FEATURES: dict[str, bool] = {
    "get_system_status": True,
    "ingest_case_facts": False,
    "validate_constraints": False,
    "propose_local_exception": False,
    "approve_local_exception": False,
    "query_semantic_graph": False,
    "propose_semantic_mr": False,
    "approve_semantic_mr": False,
    "resource:schemas/learning-ontologies": False,
    "resource:case/active-graph": False,
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
