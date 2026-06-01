"""Unit tests for sync manifest path conventions."""

from __future__ import annotations

from pathlib import Path

from km.infrastructure.rdf.ref_mapping import (
    branch_path_to_graph_uri,
    branch_path_to_slug,
    export_filename_to_graph_uri,
    graph_uri_to_branch_slug,
    ref_to_branch_path,
    ref_to_branch_slug,
    ref_to_export_filename,
)
from km.infrastructure.sync_manifest import (
    case_branch_sync_manifest_path,
    case_governance_sync_manifest_path,
    lo_sync_manifest_path,
)


def test_branch_path_to_slug() -> None:
    assert branch_path_to_slug("main") == "main"
    assert branch_path_to_slug("feature/foo") == "feature-foo"
    assert branch_path_to_slug("feature/collaborative-canvas") == "feature-collaborative-canvas"


def test_ref_to_branch_slug() -> None:
    assert ref_to_branch_slug("refs/heads/main") == "main"
    assert ref_to_branch_slug("refs/heads/feature/foo") == "feature-foo"


def test_branch_path_to_graph_uri_uses_slug() -> None:
    branch = "feature/collaborative-canvas"
    uri = branch_path_to_graph_uri(branch)
    assert uri == "http://km.local/graphs/feature-collaborative-canvas"
    assert graph_uri_to_branch_slug(uri) == "feature-collaborative-canvas"


def test_export_filename_to_graph_uri_aligns_with_branch_path() -> None:
    ref = "refs/heads/feature/collaborative-canvas"
    branch = ref_to_branch_path(ref)
    from_filename = export_filename_to_graph_uri(ref_to_export_filename(ref))
    assert from_filename == branch_path_to_graph_uri(branch)


def test_sync_manifest_paths() -> None:
    km_dir = Path("/workspace/.km")
    assert lo_sync_manifest_path(km_dir, "hexagonal-architecture") == (
        km_dir / "hexagonal-architecture_sync-manifest.json"
    )
    assert case_branch_sync_manifest_path(km_dir, "refs/heads/main") == (
        km_dir / "main_sync-manifest.json"
    )
    assert case_branch_sync_manifest_path(km_dir, "refs/heads/feature/foo") == (
        km_dir / "feature-foo_sync-manifest.json"
    )
    assert case_governance_sync_manifest_path(km_dir) == (
        km_dir / "governance_sync-manifest.json"
    )
