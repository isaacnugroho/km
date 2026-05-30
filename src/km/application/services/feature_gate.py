"""Feature gate — controls which surfaces are implemented."""

from __future__ import annotations

from km.exceptions import FeatureNotImplementedError

# Phase 3: SHACL validation, exceptions, and schema resources enabled.
FEATURES: dict[str, bool] = {
    "get_system_status": True,
    "ingest_case_facts": True,
    "validate_constraints": True,
    "propose_local_exception": True,
    "approve_local_exception": True,
    "query_semantic_graph": True,
    "propose_semantic_mr": False,
    "approve_semantic_mr": False,
    "resource:schemas/learning-ontologies": True,
    "resource:case/active-graph": True,
    "resource:case/active-exceptions": True,
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
