"""Phase 3 tests: SHACL validation, exceptions, schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from km.adapters.mcp import resources as resource_handlers
from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from km.exceptions import KmError
HEX = "http://architecture.org/hexagonal#"
CASE = "http://km.local/cases/"

VIOLATING_ADAPTER_TURTLE = f"""\
@prefix hex: <{HEX}> .
@prefix case: <{CASE}> .

case:api a hex:DrivingAdapter .
"""

DRIVING_ADAPTER_SHAPE = f"{HEX}DrivingAdapterInvocationShape"


def test_conforming_case_passes_validation(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_validate_constraints(app)
        assert result["conforms"] is True
        assert result["violations"] == []
    finally:
        app.shutdown()


def test_violating_case_fails_validation(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        result = mcp_tools.handle_validate_constraints(app)
        assert result["conforms"] is False
        assert len(result["violations"]) >= 1
        violation = result["violations"][0]
        assert violation["focus_node"] == f"{CASE}api"
        assert DRIVING_ADAPTER_SHAPE in violation["source_shape"]
        assert violation["message"]
    finally:
        app.shutdown()


def test_validation_cache_hit(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        first = mcp_tools.handle_validate_constraints(app)
        second = app.validation.validate_constraints(app.git_context)
        third = app.validation.validate_constraints(app.git_context)
        assert first["conforms"] is True
        assert second == third
    finally:
        app.shutdown()


def test_propose_exception(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        result = mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}api",
            "Test adapter stub for validation",
        )
        assert result["status"] == "PENDING_APPROVAL"
        assert result["exception_id"].startswith("http://km.local/exceptions/")
    finally:
        app.shutdown()


def test_unapproved_exception_does_not_bypass(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}api",
            "Pending only",
        )
        result = mcp_tools.handle_validate_constraints(app)
        assert result["conforms"] is False
    finally:
        app.shutdown()


def test_approved_exception_bypasses_violation(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        proposed = mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}api",
            "Approved test bypass",
        )
        mcp_tools.handle_approve_local_exception(
            app,
            proposed["exception_id"],
            "test-dev",
            "sig_test",
        )
        result = mcp_tools.handle_validate_constraints(app)
        assert result["conforms"] is True
        assert result["violations"] == []
    finally:
        app.shutdown()


def test_wrong_exception_target_still_fails(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        proposed = mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}wrong-node",
            "Wrong target",
        )
        mcp_tools.handle_approve_local_exception(
            app,
            proposed["exception_id"],
            "test-dev",
            "sig_test",
        )
        result = mcp_tools.handle_validate_constraints(app)
        assert result["conforms"] is False
    finally:
        app.shutdown()


def test_pending_exceptions_count(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}api",
            "Pending",
        )
        status = mcp_tools.handle_get_system_status(app)
        assert status["pending_exceptions_count"] == 1
    finally:
        app.shutdown()


def test_schemas_resource_lists_hex_classes(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        content, mime = resource_handlers.read_resource(app, "km://schemas/learning-ontologies")
        assert mime == "application/ld+json"
        doc = json.loads(content)
        lo = doc["learning_ontologies"][0]
        class_uris = {c["uri"] for c in lo["classes"]}
        assert f"{HEX}ApplicationCore" in class_uris
        assert f"{HEX}DrivingAdapter" in class_uris
    finally:
        app.shutdown()


def test_active_exceptions_resource(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        proposed = mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}api",
            "Listed exception",
        )
        content, mime = resource_handlers.read_resource(app, "km://case/active-exceptions")
        assert mime == "application/json"
        items = json.loads(content)
        assert len(items) == 1
        assert items[0]["status"] == "PENDING_APPROVAL"

        single, _ = resource_handlers.read_resource(
            app, f"km://case/active-exceptions/{proposed['exception_id'].split('/')[-1]}"
        )
        record = json.loads(single)
        assert record["exception_id"] == proposed["exception_id"]
    finally:
        app.shutdown()


def test_approve_non_pending_raises(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        mcp_tools.handle_ingest_case_facts(app, VIOLATING_ADAPTER_TURTLE, "turtle")
        proposed = mcp_tools.handle_propose_local_exception(
            app,
            DRIVING_ADAPTER_SHAPE,
            f"{CASE}api",
            "Once",
        )
        mcp_tools.handle_approve_local_exception(
            app, proposed["exception_id"], "dev", "sig"
        )
        with pytest.raises(KmError, match="not PENDING_APPROVAL"):
            app.exceptions.approve(proposed["exception_id"], "dev", "sig2", app.git_context)
    finally:
        app.shutdown()
