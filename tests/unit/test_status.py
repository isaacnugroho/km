"""Unit tests for system status."""

from __future__ import annotations

from pathlib import Path

from km.application.bootstrap import KMApplication


def test_get_system_status_fields(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        status = app.get_system_status()
        data = status.to_dict()
        assert "active_branch" in data
        assert data["active_branch"] == "main"
        assert len(data["learning_ontologies"]) == 1
        lo = data["learning_ontologies"][0]
        assert lo["ontology_id"] == "hexagonal-architecture"
        assert lo["mode"] == "read_only"
        assert lo["cache_synced_at"] is not None
        assert data["pending_exceptions_count"] == 0
        assert data["pending_mrs_count"] == 0
        assert data["branch_merge_policy"] == "auto_merge_exception"
        assert data["pending_branch_merges_count"] == 0
    finally:
        app.shutdown()


def test_pending_branch_merges_count(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        app.merge_prompts.write_prompt(
            {
                "event_id": "merge-feature-x-into-main-test",
                "source_branch": "feature/x",
                "target_branch": "main",
                "policy": "auto_merge_exception",
                "exceptions_copied": 0,
                "remaining_triples": 3,
                "options": ["MERGE", "KEEP_ISOLATED", "DELETE"],
                "warning": "test",
            }
        )
        data = app.get_system_status().to_dict()
        assert data["pending_branch_merges_count"] == 1
    finally:
        app.shutdown()
