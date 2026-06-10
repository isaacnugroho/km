"""Unit tests for MCP server tool/resource wrappers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import mcp.types as types
import pytest

from km.adapters.mcp import server as mcp_server
from km.application.bootstrap import KMApplication
from km.exceptions import KmError
from tests.fixtures_data import SAMPLE_CASE_TURTLE

SAMPLE_MR_INSERTIONS = """
@prefix hex: <http://architecture.org/hexagonal#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

hex:ServerPromotionClass a hex:ArchitectureConcept ;
    rdfs:label "Server promotion class" .
"""


def _reset_mcp_app() -> None:
    if hasattr(mcp_server._get_app, "_app"):
        delattr(mcp_server._get_app, "_app")


@pytest.fixture
def mcp_app(tmp_workspace: Path) -> KMApplication:
    _reset_mcp_app()
    app = KMApplication.bootstrap(tmp_workspace)
    mcp_server._get_app._app = app  # type: ignore[attr-defined]
    yield app
    app.shutdown()
    _reset_mcp_app()


@pytest.fixture
def mcp_curator_app(tmp_curator_workspace: Path) -> KMApplication:
    _reset_mcp_app()
    app = KMApplication.bootstrap(tmp_curator_workspace)
    mcp_server._get_app._app = app  # type: ignore[attr-defined]
    yield app
    app.shutdown()
    _reset_mcp_app()


def test_get_app_bootstrap_failure_normalizes_km_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if hasattr(mcp_server._get_app, "_app"):
        delattr(mcp_server._get_app, "_app")

    def fail_bootstrap(**_kwargs):
        raise FileNotFoundError("missing workspace")

    monkeypatch.setattr(mcp_server.KMApplication, "bootstrap", fail_bootstrap)
    with pytest.raises(KmError, match="missing workspace"):
        mcp_server._get_app()


def test_run_tool_reraises_non_km_errors() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        mcp_server._run_tool(lambda: (_ for _ in ()).throw(RuntimeError("boom")))


def test_run_tool_wraps_km_errors() -> None:
    with pytest.raises(RuntimeError, match="parse error"):
        mcp_server._run_tool(lambda: (_ for _ in ()).throw(KmError("parse error")))


def test_mcp_tool_wrappers(mcp_app: KMApplication, tmp_workspace: Path) -> None:
    status_payload = json.loads(mcp_server.status())
    assert status_payload["active_branch"] == "main"

    ingest_payload = json.loads(
        mcp_server.ingest_case_facts(SAMPLE_CASE_TURTLE, format="turtle")
    )
    assert ingest_payload["status"] == "success"

    bindings_payload = json.loads(mcp_server.validate_bindings())
    assert bindings_payload["valid"] is True

    constraints_payload = json.loads(mcp_server.validate_constraints())
    assert constraints_payload["conforms"] is True

    propose_payload = json.loads(
        mcp_server.propose_local_exception(
            "http://architecture.org/hexagonal#AdapterDependencyShape",
            "http://app.local/test#node",
            "test rationale",
        )
    )
    assert "exception_id" in propose_payload

    approve_payload = json.loads(
        mcp_server.approve_local_exception(
            propose_payload["exception_id"], "dev", "signed"
        )
    )
    assert approve_payload["status"] == "APPROVED"

    query_payload = json.loads(
        mcp_server.query_semantic_graph(
            "PREFIX case: <http://km.local/cases/> "
            "ASK { case:my_core a <http://architecture.org/hexagonal#ApplicationCore> }"
        )
    )
    assert query_payload["results"]["boolean"] is True

    export_payload = json.loads(mcp_server.export_case())
    assert export_payload["status"] == "success"

    sync_payload = json.loads(
        mcp_server.sync_pending_branch_merges("feature/unmerged", "main")
    )
    assert sync_payload["status"] in {
        "ALREADY_SYNCED",
        "PENDING_RESOLUTION",
        "AUTO_MERGED",
        "NO_ACTION",
    }


def test_mcp_resource_wrappers(mcp_app: KMApplication) -> None:
    schemas = mcp_server.schemas_learning_ontologies()
    assert "learning_ontologies" in schemas

    mcp_server.ingest_case_facts(SAMPLE_CASE_TURTLE, format="turtle")
    active_graph = mcp_server.case_active_graph()
    assert "my_core" in active_graph

    exceptions = mcp_server.case_active_exceptions()
    assert exceptions

    pending = mcp_server.case_pending_merges()
    assert pending

    canonical = mcp_server.lo_canonical("hexagonal-architecture")
    assert "hex:ApplicationCore" in canonical

    governance = mcp_server.lo_governance("hexagonal-architecture")
    assert governance


def test_mcp_parameterized_resource_wrappers(
    mcp_app: KMApplication, tmp_workspace: Path
) -> None:
    propose = json.loads(
        mcp_server.propose_local_exception(
            "http://architecture.org/hexagonal#AdapterDependencyShape",
            "http://app.local/test#node",
            "rationale",
        )
    )
    exception_id = propose["exception_id"]
    item = mcp_server.case_active_exception_item(exception_id)
    assert exception_id in item

    mcp_server.ingest_case_facts(SAMPLE_CASE_TURTLE, format="turtle")
    subprocess.run(
        ["git", "checkout", "-b", "feature/server-res"],
        cwd=tmp_workspace,
        check=True,
        capture_output=True,
    )
    mcp_app.git.refresh()
    mcp_app.branch_inheritance.ensure_inherited(mcp_app.git, tmp_workspace)
    sync_payload = json.loads(
        mcp_server.sync_pending_branch_merges(
            "feature/server-res", "main", event_fingerprint="server-res"
        )
    )
    merge_item = mcp_server.case_pending_merge_item(sync_payload["event_id"])
    assert sync_payload["source_branch"] in merge_item


def test_mcp_semantic_mr_tools(mcp_curator_app: KMApplication) -> None:
    propose_payload = json.loads(
        mcp_server.propose_semantic_mr(
            "hexagonal-architecture",
            "Promote server test class",
            SAMPLE_MR_INSERTIONS,
        )
    )
    mr_id = propose_payload["mr_id"]
    doc_path = (
        f".km/mrs/mr-hexagonal-architecture-{mr_id.removeprefix('MR-')}.md"
    )

    review_doc = mcp_server.mr_review_doc("hexagonal-architecture", mr_id)
    assert "Server promotion class" in review_doc

    reject_payload = json.loads(mcp_server.reject_semantic_mr(doc_path))
    assert reject_payload["status"] == "REJECTED"

    repropose_payload = json.loads(
        mcp_server.propose_semantic_mr(
            "hexagonal-architecture",
            "Promote server test class again",
            SAMPLE_MR_INSERTIONS,
        )
    )
    repropose_doc = (
        f".km/mrs/mr-hexagonal-architecture-"
        f"{repropose_payload['mr_id'].removeprefix('MR-')}.md"
    )
    approve_payload = json.loads(mcp_server.approve_semantic_mr(repropose_doc))
    assert approve_payload["status"] == "APPROVED"


def test_mcp_resolve_branch_merge(
    mcp_app: KMApplication, tmp_workspace: Path
) -> None:
    mcp_server.ingest_case_facts(SAMPLE_CASE_TURTLE, format="turtle")
    subprocess.run(
        ["git", "checkout", "-b", "feature/resolve"],
        cwd=tmp_workspace,
        check=True,
        capture_output=True,
    )
    mcp_app.git.refresh()
    mcp_app.branch_inheritance.ensure_inherited(mcp_app.git, tmp_workspace)
    sync_payload = json.loads(
        mcp_server.sync_pending_branch_merges(
            "feature/resolve", "main", event_fingerprint="resolve-test"
        )
    )
    resolve_payload = json.loads(
        mcp_server.resolve_branch_merge(sync_payload["event_id"], "MERGE")
    )
    assert resolve_payload["status"] == "success"
    assert resolve_payload["resolution"] == "MERGE"


def test_run_mcp_server(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        mcp_server.mcp,
        "run",
        lambda transport: calls.append(transport),
    )
    mcp_server.run_mcp_server()
    assert calls == ["stdio"]


@pytest.mark.asyncio
async def test_resource_subscribe_unsubscribe_handlers() -> None:
    handlers = mcp_server.mcp._mcp_server.request_handlers
    subscribe = handlers[types.SubscribeRequest]
    unsubscribe = handlers[types.UnsubscribeRequest]
    uri = "km://case/active-graph"
    await subscribe(
        types.SubscribeRequest(params=types.SubscribeRequestParams(uri=uri))
    )
    await unsubscribe(
        types.UnsubscribeRequest(params=types.UnsubscribeRequestParams(uri=uri))
    )
