"""Unit tests for feature gate and stub behavior."""

from __future__ import annotations

import pytest

from km.application.services import feature_gate
from km.application.services.feature_gate import require_implemented
from km.exceptions import FeatureNotImplementedError


@pytest.mark.parametrize(
    "feature",
    [
        "validate_constraints",
        "propose_local_exception",
        "approve_local_exception",
        "propose_semantic_mr",
        "approve_semantic_mr",
        "resource:schemas/learning-ontologies",
        "resource:case/active-exceptions",
        "cli:export-case",
    ],
)
def test_stub_features_raise(feature: str) -> None:
    with pytest.raises(FeatureNotImplementedError, match=f"feature not yet implemented: {feature}"):
        require_implemented(feature)


def test_get_system_status_is_implemented() -> None:
    require_implemented("get_system_status")


def test_phase2_features_implemented() -> None:
    require_implemented("ingest_case_facts")
    require_implemented("query_semantic_graph")
    require_implemented("resource:case/active-graph")


def test_release_enables_feature() -> None:
    key = "ingest_case_facts"
    original = feature_gate.FEATURES[key]
    try:
        feature_gate.release(key)
        require_implemented(key)
    finally:
        feature_gate.FEATURES[key] = original
