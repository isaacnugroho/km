"""Unit tests for feature gate and stub behavior."""

from __future__ import annotations


from km.application.services import feature_gate
from km.application.services.feature_gate import require_implemented


def test_all_features_enabled() -> None:
    assert all(feature_gate.FEATURES.values())
    require_implemented("status")


def test_phase2_features_implemented() -> None:
    require_implemented("ingest_case_facts")
    require_implemented("patch_case_facts")
    require_implemented("query_semantic_graph")
    require_implemented("resource:case/active-graph")


def test_phase3_features_implemented() -> None:
    require_implemented("validate_constraints")
    require_implemented("propose_local_exception")
    require_implemented("approve_local_exception")
    require_implemented("resource:schemas/learning-ontologies")
    require_implemented("resource:case/active-exceptions")


def test_phase4a_lo_resources_implemented() -> None:
    require_implemented("resource:lo/canonical")
    require_implemented("resource:lo/governance")


def test_phase4b_mr_propose_implemented() -> None:
    require_implemented("propose_semantic_mr")
    require_implemented("resource:mr")


def test_phase4c_mr_approve_implemented() -> None:
    require_implemented("approve_semantic_mr")
    require_implemented("reject_semantic_mr")
    require_implemented("validate_bindings")


def test_phase5_features_implemented() -> None:
    require_implemented("export_case")
    require_implemented("sync_pending_branch_merges")
    require_implemented("resolve_branch_merge")


def test_release_enables_feature() -> None:
    key = "ingest_case_facts"
    original = feature_gate.FEATURES[key]
    try:
        feature_gate.release(key)
        require_implemented(key)
    finally:
        feature_gate.FEATURES[key] = original
