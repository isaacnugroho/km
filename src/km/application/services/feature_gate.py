"""Feature gate — controls which surfaces are implemented."""

from __future__ import annotations

from km.exceptions import FeatureNotImplementedError

FEATURES: dict[str, bool] = {
    "setup": True,
    "status": True,
    "validate_bindings": True,
    "export_case": True,
    "ingest_case_facts": True,
    "patch_case_facts": True,
    "validate_constraints": True,
    "propose_local_exception": True,
    "approve_local_exception": True,
    "query_semantic_graph": True,
    "propose_semantic_mr": True,
    "approve_semantic_mr": True,
    "reject_semantic_mr": True,
    "sync_pending_branch_merges": True,
    "resolve_branch_merge": True,
    "resource:schemas/learning-ontologies": True,
    "resource:case/active-graph": True,
    "resource:case/active-exceptions": True,
    "resource:case/pending-merges": True,
    "resource:lo/canonical": True,
    "resource:lo/governance": True,
    "resource:mr": True,
}


def require_implemented(feature: str) -> None:
    if not FEATURES.get(feature, False):
        raise FeatureNotImplementedError(feature)


def release(feature: str) -> None:
    """Enable a feature (used when completing later phases)."""
    FEATURES[feature] = True
