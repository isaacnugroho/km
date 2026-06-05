"""KM command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from km import __version__
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"km {__version__}",
    )
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


def cmd_export_case() -> None:
    require_implemented("export_case")
    app = KMApplication.bootstrap()
    try:
        export_path = app.case_export.export_active(app.git_context)
        print(json.dumps({"status": "success", "export_path": str(export_path)}))
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
