"""Phase 4b tests: propose semantic MR, review docs, pending_mrs_count."""

from __future__ import annotations

from pathlib import Path

import pytest

from km.adapters.mcp import resources as resource_handlers
from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.exceptions import PermissionError
from km.infrastructure.rdf.store import load_sync_manifest

SAMPLE_MR_INSERTIONS = """
@prefix hex: <http://architecture.org/hexagonal#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

hex:TestPromotionClass a hex:ArchitectureConcept ;
    rdfs:label "Test promotion class" .
"""


def test_propose_rejects_read_only_binding(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with pytest.raises(PermissionError, match="curator mode"):
            mcp_tools.handle_propose_semantic_mr(
                app,
                "hexagonal-architecture",
                "Promote test class",
                SAMPLE_MR_INSERTIONS,
            )
    finally:
        app.shutdown()


def test_propose_creates_governance_export_and_review_doc(
    tmp_curator_workspace: Path,
) -> None:
    app = KMApplication.bootstrap(tmp_curator_workspace)
    try:
        cache_manifest_before = load_sync_manifest(
            tmp_curator_workspace / ".km" / "hexagonal-architecture_sync-manifest.json"
        )
        assert cache_manifest_before is not None
        checksums_before = cache_manifest_before.export_checksums

        result = mcp_tools.handle_propose_semantic_mr(
            app,
            "http://architecture.org/hexagonal",
            "Add test promotion class for Phase 4b coverage",
            SAMPLE_MR_INSERTIONS,
        )
        assert result["status"] == "PENDING_APPROVAL"
        mr_id = result["mr_id"]
        assert mr_id.startswith("MR-")

        gov_export = (
            app.lo_source_store.get_entry("hexagonal-architecture").source_path
            / "exports"
            / "governance"
            / f"{mr_id}.ttl"
        )
        assert gov_export.is_file()
        assert "PENDING_APPROVAL" in gov_export.read_text(encoding="utf-8")

        review_path = (
            tmp_curator_workspace
            / ".km"
            / "mrs"
            / f"mr-hexagonal-architecture-{mr_id.removeprefix('MR-')}.md"
        )
        assert review_path.is_file()
        review_text = review_path.read_text(encoding="utf-8")
        assert "Approval Command:" in review_text
        assert (
            f"approve .km/mrs/mr-hexagonal-architecture-{mr_id.removeprefix('MR-')}.md"
            in review_text
        )
        assert "Add test promotion class" in review_text
        assert "High-Level Impact" in review_text
        assert "TestPromotionClass" in review_text
        assert "Reject Command:" in review_text
        assert f"reject {mr_id}" in review_text
        assert "+hex:TestPromotionClass" in review_text

        cache_manifest_after = load_sync_manifest(
            tmp_curator_workspace / ".km" / "hexagonal-architecture_sync-manifest.json"
        )
        assert cache_manifest_after is not None
        assert cache_manifest_after.export_checksums == checksums_before

        status = mcp_tools.handle_status(app)
        assert status["pending_mrs_count"] == 1
    finally:
        app.shutdown()


def test_mr_resource_returns_review_markdown(tmp_curator_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_curator_workspace)
    try:
        result = mcp_tools.handle_propose_semantic_mr(
            app,
            "hexagonal-architecture",
            "Resource read test",
            SAMPLE_MR_INSERTIONS,
        )
        mr_id = result["mr_id"]
        content, mime = resource_handlers.read_resource(
            app, f"km://mr/hexagonal-architecture/{mr_id}"
        )
        assert mime == "text/markdown"
        assert mr_id in content
        assert "Resource read test" in content
    finally:
        app.shutdown()


def test_proposal_graph_not_in_default_query_union(tmp_curator_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_curator_workspace)
    try:
        mcp_tools.handle_propose_semantic_mr(
            app,
            "hexagonal-architecture",
            "Isolation test",
            SAMPLE_MR_INSERTIONS,
        )
        query_result = mcp_tools.handle_query_semantic_graph(
            app,
            "SELECT ?c WHERE { ?c a <http://architecture.org/hexagonal#ArchitectureConcept> }",
        )
        classes = {row["c"] for row in query_result["results"]["bindings"]}
        assert "http://architecture.org/hexagonal#TestPromotionClass" not in classes
    finally:
        app.shutdown()


def test_approve_merges_into_canonical_and_refreshes_cache(
    tmp_curator_workspace: Path,
) -> None:
    app = KMApplication.bootstrap(tmp_curator_workspace)
    try:
        propose = mcp_tools.handle_propose_semantic_mr(
            app,
            "hexagonal-architecture",
            "Approve test promotion",
            SAMPLE_MR_INSERTIONS,
        )
        mr_id = propose["mr_id"]
        rel_doc = f".km/mrs/mr-hexagonal-architecture-{mr_id.removeprefix('MR-')}.md"

        cache_manifest_before = load_sync_manifest(
            tmp_curator_workspace / ".km" / "hexagonal-architecture_sync-manifest.json"
        )
        assert cache_manifest_before is not None

        result = mcp_tools.handle_approve_semantic_mr(app, rel_doc)
        assert result["status"] == "APPROVED"
        assert result["mr_id"] == mr_id
        assert result["target_ontology"] == "http://architecture.org/hexagonal"
        assert result["timestamp"]

        main_ttl = (
            app.lo_source_store.get_entry("hexagonal-architecture").source_path
            / "exports"
            / "main.ttl"
        )
        assert "TestPromotionClass" in main_ttl.read_text(encoding="utf-8")

        gov_export = (
            app.lo_source_store.get_entry("hexagonal-architecture").source_path
            / "exports"
            / "governance"
            / f"{mr_id}.ttl"
        )
        assert "APPROVED" in gov_export.read_text(encoding="utf-8")

        cache_manifest_after = load_sync_manifest(
            tmp_curator_workspace / ".km" / "hexagonal-architecture_sync-manifest.json"
        )
        assert cache_manifest_after is not None
        assert (
            cache_manifest_after.export_checksums
            != cache_manifest_before.export_checksums
        )

        status = mcp_tools.handle_status(app)
        assert status["pending_mrs_count"] == 0

        query_result = mcp_tools.handle_query_semantic_graph(
            app,
            "ASK { <http://architecture.org/hexagonal#TestPromotionClass> a <http://architecture.org/hexagonal#ArchitectureConcept> }",
        )
        assert query_result["results"]["boolean"] is True
    finally:
        app.shutdown()


def test_approve_by_km_uri(tmp_curator_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_curator_workspace)
    try:
        propose = mcp_tools.handle_propose_semantic_mr(
            app,
            "hexagonal-architecture",
            "URI approve test",
            SAMPLE_MR_INSERTIONS,
        )
        mr_id = propose["mr_id"]
        result = mcp_tools.handle_approve_semantic_mr(
            app, f"km://mr/hexagonal-architecture/{mr_id}"
        )
        assert result["status"] == "APPROVED"
    finally:
        app.shutdown()


def test_reject_by_mr_id_minimal_path(tmp_curator_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_curator_workspace)
    try:
        propose = mcp_tools.handle_propose_semantic_mr(
            app,
            "hexagonal-architecture",
            "Reject test promotion",
            SAMPLE_MR_INSERTIONS,
        )
        mr_id = propose["mr_id"]

        cache_manifest_before = load_sync_manifest(
            tmp_curator_workspace / ".km" / "hexagonal-architecture_sync-manifest.json"
        )
        assert cache_manifest_before is not None

        result = mcp_tools.handle_reject_semantic_mr(app, mr_id)
        assert result["status"] == "REJECTED"
        assert result["mr_id"] == mr_id
        assert result["timestamp"]

        main_ttl = (
            app.lo_source_store.get_entry("hexagonal-architecture").source_path
            / "exports"
            / "main.ttl"
        )
        assert "TestPromotionClass" not in main_ttl.read_text(encoding="utf-8")

        gov_export = (
            app.lo_source_store.get_entry("hexagonal-architecture").source_path
            / "exports"
            / "governance"
            / f"{mr_id}.ttl"
        )
        assert "REJECTED" in gov_export.read_text(encoding="utf-8")

        cache_manifest_after = load_sync_manifest(
            tmp_curator_workspace / ".km" / "hexagonal-architecture_sync-manifest.json"
        )
        assert cache_manifest_after is not None
        assert (
            cache_manifest_after.export_checksums
            == cache_manifest_before.export_checksums
        )

        review_path = (
            tmp_curator_workspace
            / ".km"
            / "mrs"
            / f"mr-hexagonal-architecture-{mr_id.removeprefix('MR-')}.md"
        )
        assert "**Status:** REJECTED" in review_path.read_text(encoding="utf-8")

        query_result = mcp_tools.handle_query_semantic_graph(
            app,
            "ASK { <http://architecture.org/hexagonal#TestPromotionClass> a <http://architecture.org/hexagonal#ArchitectureConcept> }",
        )
        assert query_result["results"]["boolean"] is False

        status = mcp_tools.handle_status(app)
        assert status["pending_mrs_count"] == 0
    finally:
        app.shutdown()


def test_approve_rejects_read_only_binding(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with pytest.raises(PermissionError, match="curator mode"):
            mcp_tools.handle_approve_semantic_mr(
                app, "km://mr/hexagonal-architecture/MR-001"
            )
    finally:
        app.shutdown()
