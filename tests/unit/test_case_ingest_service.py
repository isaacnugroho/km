"""Unit tests for CaseIngestService error paths and edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from km.application.bootstrap import KMApplication
from km.application.services.case_ingest_service import CaseIngestService
from km.exceptions import KmError
from km.infrastructure.git.context import GitContext


def _git_context() -> GitContext:
    return GitContext(
        active_ref="refs/heads/main",
        branch_path="main",
        graph_uri="http://km.local/graphs/main",
    )


def test_ingest_requires_branch_path(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        empty_ctx = GitContext(
            active_ref="",
            branch_path="",
            graph_uri="http://km.local/graphs/main",
        )
        with pytest.raises(KmError, match="No active git branch"):
            app.case_ingest.ingest("@prefix ex: <http://ex#> .", "turtle", empty_ctx)
    finally:
        app.shutdown()


def test_ingest_malformed_rdf_returns_error(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with patch(
            "km.application.services.case_ingest_service.parse_facts",
            side_effect=RuntimeError("parser exploded"),
        ):
            result = app.case_ingest.ingest("bad", "turtle", app.git_context)
        assert result == {"status": "error", "triples_added": 0}
    finally:
        app.shutdown()


def test_patch_requires_branch_path(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        empty_ctx = GitContext(
            active_ref="",
            branch_path="",
            graph_uri="http://km.local/graphs/main",
        )
        with pytest.raises(KmError, match="No active git branch"):
            app.case_ingest.patch("", "", "turtle", empty_ctx)
    finally:
        app.shutdown()


def test_patch_unsupported_format(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = app.case_ingest.patch("", "data", "json-ld", app.git_context)
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "parse"
        assert "Unsupported format" in result["errors"][0]["message"]
    finally:
        app.shutdown()


def test_patch_ttl_alias_normalized(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = app.case_ingest.patch(
            "",
            "@prefix ex: <http://ex#> .\nex:Thing a ex:Thing .",
            "ttl",
            app.git_context,
        )
        assert result["status"] == "success"
    finally:
        app.shutdown()


def test_patch_malformed_deletions(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with patch(
            "km.application.services.case_ingest_service.parse_deletion_plan",
            side_effect=RuntimeError("delete parse failed"),
        ):
            result = app.case_ingest.patch(
                "broken", "", "turtle", app.git_context
            )
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "parse"
    finally:
        app.shutdown()


def test_patch_malformed_insertions(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with patch(
            "km.application.services.case_ingest_service.parse_facts_optional",
            side_effect=RuntimeError("insert parse failed"),
        ):
            result = app.case_ingest.patch(
                "", "broken", "turtle", app.git_context
            )
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "parse"
    finally:
        app.shutdown()


def test_patch_apply_failure(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with patch(
            "km.application.services.case_ingest_service.apply_patch",
            side_effect=RuntimeError("apply failed"),
        ):
            result = app.case_ingest.patch(
                "@prefix ex: <http://ex#> .\nex:Old a ex:Thing .",
                "",
                "turtle",
                app.git_context,
            )
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "insert"
    finally:
        app.shutdown()


def test_ingest_value_error_returns_error(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = app.case_ingest.ingest("not valid turtle @@@", "turtle", app.git_context)
        assert result == {"status": "error", "triples_added": 0}
    finally:
        app.shutdown()


def test_patch_empty_diffs_returns_error(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = app.case_ingest.patch("  ", "  ", "turtle", app.git_context)
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "parse"
    finally:
        app.shutdown()


def test_patch_deletion_value_error(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with patch(
            "km.application.services.case_ingest_service.parse_deletion_plan",
            side_effect=ValueError("bad deletion"),
        ):
            result = app.case_ingest.patch("bad", "", "turtle", app.git_context)
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "parse"
    finally:
        app.shutdown()


def test_patch_insertion_value_error(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        with patch(
            "km.application.services.case_ingest_service.parse_facts_optional",
            side_effect=ValueError("bad insertion"),
        ):
            result = app.case_ingest.patch("", "bad", "turtle", app.git_context)
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "parse"
    finally:
        app.shutdown()


def test_patch_on_write_exports(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        result = app.case_ingest.patch(
            "",
            "@prefix ex: <http://ex#> .\nex:Thing a ex:Thing .",
            "turtle",
            app.git_context,
        )
        assert result["status"] == "success"
        export_file = (
            tmp_workspace_on_write / "case-exports" / "graphs" / "refs-heads-main.ttl"
        )
        assert export_file.is_file()
    finally:
        app.shutdown()


def test_patch_delete_phase_error() -> None:
    service = CaseIngestService(
        case_wrapper=MagicMock(),
        export_service=MagicMock(),
        config=MagicMock(),
    )
    with patch(
        "km.application.services.case_ingest_service.apply_patch",
        side_effect=ValueError("protected triple"),
    ):
        result = service.patch(
            "@prefix ex: <http://ex#> .\nex:Old a ex:Thing .",
            "",
            "turtle",
            _git_context(),
        )
    assert result["status"] == "error"
    assert result["errors"][0]["phase"] == "delete"
