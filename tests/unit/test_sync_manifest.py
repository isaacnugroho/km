"""Unit tests for sync manifest path conventions."""

from __future__ import annotations

from pathlib import Path

import pytest

from km.infrastructure.rdf.ref_mapping import (
    branch_path_to_graph_uri,
    branch_path_to_slug,
    export_filename_to_git_ref,
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
    assert (
        branch_path_to_slug("feature/collaborative-canvas")
        == "feature-collaborative-canvas"
    )


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


def test_graph_uri_to_branch_slug_rejects_non_case_uri() -> None:
    with pytest.raises(ValueError, match="Not a case branch graph URI"):
        graph_uri_to_branch_slug("http://example.org/other")


def test_ref_to_branch_path_strips_refs_prefixes() -> None:
    assert ref_to_branch_path("refs/heads/feature/foo") == "feature/foo"
    assert ref_to_branch_path("refs/tags/v1.0.0") == "tags/v1.0.0"
    assert ref_to_branch_path("main") == "main"


def test_export_filename_to_graph_uri_rejects_invalid_names() -> None:
    assert export_filename_to_graph_uri("not-a-ttl-file.json") is None
    assert export_filename_to_graph_uri("refs-tags-v1.ttl") is None


def test_export_filename_to_git_ref_fallback_paths() -> None:
    assert (
        export_filename_to_git_ref("refs-heads-feature-foo.ttl")
        == "refs/heads/feature/foo"
    )
    assert (
        export_filename_to_git_ref("refs-tags-v1-0-0.ttl") == "refs/tags/v1/0/0"
    )
    assert export_filename_to_git_ref("random.ttl") is None


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
