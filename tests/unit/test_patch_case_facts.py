"""Tests for patch_case_facts (spec addendum A1)."""

from __future__ import annotations

from pathlib import Path

from km.adapters.mcp import tools as mcp_tools
from km.application.bootstrap import KMApplication
from tests.fixtures_data import SAMPLE_CASE_TURTLE

HEX = "http://architecture.org/hexagonal#"
CASE = "http://km.local/cases/"

EXTRA_FACTS = f"""\
@prefix hex: <{HEX}> .
@prefix case: <{CASE}> .

case:my_core hex:defines case:orphan_port .
case:phantom a hex:ApplicationCore .
"""

PATCH_RETYPE = {
    "diff_deletions": f"""\
@prefix hex: <{HEX}> .
@prefix case: <{CASE}> .

case:my_core a <{HEX}ApplicationCore> .
""",
    "diff_insertions": f"""\
@prefix hex: <{HEX}> .
@prefix case: <{CASE}> .

case:my_core a hex:DomainEntity .
""",
}

DELETE_PHANTOM = f"""\
@prefix km: <http://km.local/governance#> .
@prefix case: <{CASE}> .

case:phantom km:deleteSubject true .
"""


def _seed_graph(app: KMApplication) -> None:
    mcp_tools.handle_ingest_case_facts(app, SAMPLE_CASE_TURTLE, "turtle")
    mcp_tools.handle_ingest_case_facts(app, EXTRA_FACTS, "turtle")


def _ask(app: KMApplication, query: str) -> bool:
    result = mcp_tools.handle_query_semantic_graph(app, query)
    return bool(result["results"]["boolean"])


def test_patch_exact_delete_and_insert(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        _seed_graph(app)
        result = mcp_tools.handle_patch_case_facts(app, **PATCH_RETYPE)
        assert result == {"status": "success", "triples_removed": 1, "triples_added": 1}
        assert _ask(
            app,
            f"ASK {{ <{CASE}my_core> a <{HEX}DomainEntity> }}",
        )
        assert not _ask(
            app,
            f"ASK {{ <{CASE}my_core> a <{HEX}ApplicationCore> }}",
        )
    finally:
        app.shutdown()


def test_patch_delete_subject(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        _seed_graph(app)
        result = mcp_tools.handle_patch_case_facts(app, diff_deletions=DELETE_PHANTOM)
        assert result["status"] == "success"
        assert result["triples_removed"] == 1
        assert not _ask(app, f"ASK {{ <{CASE}phantom> ?p ?o }}")
        assert _ask(app, f"ASK {{ <{CASE}my_core> ?p ?o }}")
    finally:
        app.shutdown()


def test_patch_empty_diffs_error(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        result = mcp_tools.handle_patch_case_facts(app)
        assert result["status"] == "error"
        assert result["triples_removed"] == 0
        assert result["triples_added"] == 0
        assert result["errors"][0]["phase"] == "parse"
    finally:
        app.shutdown()


def test_patch_non_matching_delete_is_noop(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        _seed_graph(app)
        result = mcp_tools.handle_patch_case_facts(
            app,
            diff_deletions=f"@prefix case: <{CASE}> .\ncase:missing a <{HEX}ApplicationCore> .\n",
        )
        assert result == {"status": "success", "triples_removed": 0, "triples_added": 0}
    finally:
        app.shutdown()


def test_patch_rolls_back_on_protected_exception(tmp_workspace: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace)
    try:
        _seed_graph(app)
        proposed = mcp_tools.handle_propose_local_exception(
            app,
            bypasses_shape=f"{HEX}DrivingAdapterInvocationShape",
            target_node=f"{CASE}api",
            rationale="test",
        )
        exc_id = proposed["exception_id"].removeprefix("http://km.local/exceptions/")
        mcp_tools.handle_approve_local_exception(
            app, exc_id, "dev", "sig-test"
        )
        before = mcp_tools.handle_query_semantic_graph(
            app,
            f"SELECT (COUNT(*) AS ?c) WHERE {{ GRAPH <http://km.local/graphs/main> {{ ?s ?p ?o }} }}",
        )
        before_count = int(before["results"]["bindings"][0]["c"]["value"])

        result = mcp_tools.handle_patch_case_facts(
            app,
            diff_deletions=(
                "@prefix km: <http://km.local/governance#> .\n"
                f"<{proposed['exception_id']}> km:deleteSubject true .\n"
            ),
        )
        assert result["status"] == "error"
        assert result["errors"][0]["phase"] == "delete"

        after = mcp_tools.handle_query_semantic_graph(
            app,
            f"SELECT (COUNT(*) AS ?c) WHERE {{ GRAPH <http://km.local/graphs/main> {{ ?s ?p ?o }} }}",
        )
        after_count = int(after["results"]["bindings"][0]["c"]["value"])
        assert after_count == before_count
    finally:
        app.shutdown()


def test_patch_on_write_exports(tmp_workspace_on_write: Path) -> None:
    app = KMApplication.bootstrap(tmp_workspace_on_write)
    try:
        _seed_graph(app)
        mcp_tools.handle_patch_case_facts(app, diff_deletions=DELETE_PHANTOM)
        export_file = (
            tmp_workspace_on_write / "case-exports" / "graphs" / "refs-heads-main.ttl"
        )
        content = export_file.read_text()
        assert f"{CASE}phantom" not in content
        assert f"{CASE}my_core" in content
    finally:
        app.shutdown()
