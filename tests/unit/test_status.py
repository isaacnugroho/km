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
    finally:
        app.shutdown()
