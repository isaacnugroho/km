"""KM command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from km.application.bootstrap import KMApplication
from km.application.services.feature_gate import require_implemented
from km.application.services.workspace_service import init_workspace
from km.exceptions import FeatureNotImplementedError, KmError, as_km_error
from km.logging_config import configure_logging, get_logger

logger = get_logger("cli")


def main() -> None:
    raise SystemExit(run_cli(sys.argv[1:]))


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="km", description="Knowledge Management MCP CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Initialize .km/ workspace configuration")
    init_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Workspace root directory (default: current directory)",
    )
    init_parser.add_argument(
        "--lo-source",
        default=None,
        help="Relative path to LO package for default binding",
    )

    sub.add_parser("status", help="Print system status JSON")
    sub.add_parser("mcp", help="Start MCP server (stdio)")
    sub.add_parser("export-case", help="Export active branch case graph to case-exports/")
    sub.add_parser(
        "migrate-graph-uris",
        help="Rewrite legacy path-style graph URIs in case-exports/ to slug form",
    )

    merge_parser = sub.add_parser("merge-resolve", help="Resolve a pending branch merge prompt")
    merge_parser.add_argument("event_id", help="Pending merge event id")
    merge_parser.add_argument(
        "resolution",
        choices=["MERGE", "KEEP_ISOLATED", "DELETE"],
        help="Developer resolution choice",
    )

    args = parser.parse_args(argv)
    configure_logging(mcp_mode=False)

    try:
        if args.command == "init":
            cmd_init(args.path, lo_source=args.lo_source)
        elif args.command == "status":
            cmd_status()
        elif args.command == "mcp":
            from km.adapters.mcp.server import run_mcp_server

            run_mcp_server()
        elif args.command == "export-case":
            cmd_export_case()
        elif args.command == "migrate-graph-uris":
            cmd_migrate_graph_uris()
        elif args.command == "merge-resolve":
            cmd_merge_resolve(args.event_id, args.resolution)
    except FeatureNotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        km_exc = as_km_error(exc)
        if km_exc is not None:
            print(str(km_exc), file=sys.stderr)
            return 1
        raise
    except KeyboardInterrupt:
        return 130
    return 0


def cmd_init(path: Path, *, lo_source: str | None) -> None:
    config_path = init_workspace(path, lo_source=lo_source)
    print(f"Initialized workspace config at {config_path}")


def cmd_status() -> None:
    app = KMApplication.bootstrap()
    try:
        status = app.get_system_status()
        print(json.dumps(status.to_dict(), indent=2))
    finally:
        app.shutdown()


def cmd_migrate_graph_uris() -> None:
    app = KMApplication.bootstrap()
    try:
        from km.infrastructure.rdf.graph_uri_migration import (
            migrate_legacy_branch_graphs,
            rewrite_case_export_graph_uris,
        )

        exports_root = app.workspace.resolve_config_path(
            app.workspace.config.case_exports.base_path
        )
        changed_exports = rewrite_case_export_graph_uris(exports_root)
        migrated_graphs = migrate_legacy_branch_graphs(app.case_store.wrapper)
        print(
            json.dumps(
                {
                    "status": "success",
                    "exports_rewritten": [str(p) for p in changed_exports],
                    "graphs_migrated": migrated_graphs,
                },
                indent=2,
            )
        )
    finally:
        app.shutdown()


def cmd_export_case() -> None:
    require_implemented("cli:export-case")
    app = KMApplication.bootstrap()
    try:
        export_path = app.case_export.export_active(app.git_context)
        print(json.dumps({"status": "success", "export_path": str(export_path)}))
    finally:
        app.shutdown()


def cmd_merge_resolve(event_id: str, resolution: str) -> None:
    app = KMApplication.bootstrap()
    try:
        result = app.merge_resolver.resolve_prompt(event_id, resolution)
        print(json.dumps(result, indent=2))
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
