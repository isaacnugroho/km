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

HOOK_TEMPLATE = Path(__file__).resolve().parent.parent / "hooks" / "pre-commit.km.sh"


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
    init_parser.add_argument(
        "--with-hooks",
        action="store_true",
        help="Install pre-commit hook template for on_commit export policy",
    )

    sub.add_parser("status", help="Print system status JSON")
    sub.add_parser("mcp", help="Start MCP server (stdio)")
    sub.add_parser("export-case", help="Export active branch case graph to case-exports/")

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
            cmd_init(args.path, lo_source=args.lo_source, with_hooks=args.with_hooks)
        elif args.command == "status":
            cmd_status()
        elif args.command == "mcp":
            from km.adapters.mcp.server import run_mcp_server

            run_mcp_server()
        elif args.command == "export-case":
            cmd_export_case()
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


def cmd_init(path: Path, *, lo_source: str | None, with_hooks: bool = False) -> None:
    config_path = init_workspace(path, lo_source=lo_source)
    print(f"Initialized workspace config at {config_path}")
    if with_hooks:
        install_pre_commit_hook(path.resolve())


def install_pre_commit_hook(workspace_root: Path) -> Path:
    if not HOOK_TEMPLATE.is_file():
        raise KmError(f"Missing hook template: {HOOK_TEMPLATE}")
    hooks_dir = workspace_root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        raise KmError(f"No .git/hooks directory at {workspace_root}")
    hook_path = hooks_dir / "pre-commit"
    marker = "# km export-case"
    template = HOOK_TEMPLATE.read_text(encoding="utf-8")
    if hook_path.is_file():
        existing = hook_path.read_text(encoding="utf-8")
        if marker in existing:
            print(f"KM hook already present in {hook_path}")
            return hook_path
        content = existing.rstrip() + "\n\n" + template
    else:
        content = template
    hook_path.write_text(content, encoding="utf-8")
    hook_path.chmod(hook_path.stat().st_mode | 0o755)
    print(f"Installed KM pre-commit hook at {hook_path}")
    return hook_path


def cmd_status() -> None:
    app = KMApplication.bootstrap()
    try:
        status = app.get_system_status()
        print(json.dumps(status.to_dict(), indent=2))
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
