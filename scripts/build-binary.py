#!/usr/bin/env python3
"""Build a standalone ``km`` binary with PyInstaller."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRY = REPO_ROOT / "src" / "km" / "adapters" / "cli" / "main.py"
HOOK_TEMPLATE = REPO_ROOT / "src" / "km" / "adapters" / "hooks" / "pre-commit.km.sh"
DEFAULT_DIST = REPO_ROOT / "dist"
DEFAULT_BUILD = REPO_ROOT / "build"
DEFAULT_SPEC = REPO_ROOT / "scripts" / "pyinstaller"


def platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    arch = arch_map.get(machine, machine.replace("-", "_"))
    if system == "darwin":
        return f"macos-{arch}"
    if system == "windows":
        return f"windows-{arch}"
    return f"linux-{arch}"


def add_data_separator() -> str:
    return ";" if platform.system() == "Windows" else ":"


def expected_platforms() -> set[str]:
    current = platform.system().lower()
    if current == "darwin":
        return {"darwin", "macos"}
    if current == "windows":
        return {"windows"}
    return {"linux"}


def check_platform(requested: str | None) -> None:
    if requested is None:
        return
    normalized = requested.lower()
    if normalized not in expected_platforms():
        current = platform_tag()
        raise SystemExit(
            f"Refusing to build for '{requested}' on {current}. "
            "PyInstaller builds must run on the target OS."
        )


def ensure_prerequisites() -> None:
    missing: list[str] = []
    if not ENTRY.is_file():
        missing.append(str(ENTRY))
    if not HOOK_TEMPLATE.is_file():
        missing.append(str(HOOK_TEMPLATE))
    if missing:
        raise SystemExit("Missing required files:\n  " + "\n  ".join(missing))

    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller is not installed. Run:\n"
            "  pip install -e \".[build]\""
        ) from exc


def build(
    *,
    onefile: bool,
    distpath: Path,
    workpath: Path,
    specpath: Path,
    tagged_name: bool,
) -> Path:
    ensure_prerequisites()

    distpath.mkdir(parents=True, exist_ok=True)
    workpath.mkdir(parents=True, exist_ok=True)
    specpath.mkdir(parents=True, exist_ok=True)

    hook_data = f"{HOOK_TEMPLATE}{add_data_separator()}km/adapters/hooks"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "km",
        "--console",
        "--clean",
        "--noconfirm",
        f"--{'onefile' if onefile else 'onedir'}",
        "--paths",
        str(REPO_ROOT / "src"),
        "--distpath",
        str(distpath),
        "--workpath",
        str(workpath),
        "--specpath",
        str(specpath),
        "--hidden-import=km.adapters.mcp.server",
        "--hidden-import=km.adapters.mcp.tools",
        "--hidden-import=km.adapters.mcp.resources",
        "--hidden-import=mcp.server.fastmcp",
        "--collect-submodules=km",
        "--collect-data=km",
        "--collect-all=pyoxigraph",
        "--collect-all=pyshacl",
        "--copy-metadata=km",
        "--copy-metadata=mcp",
        "--copy-metadata=pyoxigraph",
        "--copy-metadata=pyshacl",
        "--copy-metadata=rdflib",
        "--add-data",
        hook_data,
        str(ENTRY),
    ]

    print("Running:", " ".join(f'"{part}"' if " " in part else part for part in cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)

    if onefile:
        artifact = distpath / ("km.exe" if platform.system() == "Windows" else "km")
    else:
        artifact = distpath / "km" / ("km.exe" if platform.system() == "Windows" else "km")

    if not artifact.is_file():
        raise SystemExit(f"Expected build artifact not found: {artifact}")

    if tagged_name:
        suffix = platform_tag()
        tagged = distpath / f"km-{suffix}{artifact.suffix}"
        shutil.copy2(artifact, tagged)
        print(f"Tagged release binary: {tagged}")
        return tagged

    print(f"Build complete: {artifact}")
    return artifact


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        choices=("linux", "macos", "windows"),
        help="Expected target platform (must match the host OS).",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build a directory bundle instead of a single file.",
    )
    parser.add_argument(
        "--distpath",
        type=Path,
        default=DEFAULT_DIST,
        help=f"PyInstaller dist output directory (default: {DEFAULT_DIST})",
    )
    parser.add_argument(
        "--workpath",
        type=Path,
        default=DEFAULT_BUILD,
        help=f"PyInstaller work directory (default: {DEFAULT_BUILD})",
    )
    parser.add_argument(
        "--specpath",
        type=Path,
        default=DEFAULT_SPEC,
        help=f"PyInstaller spec directory (default: {DEFAULT_SPEC})",
    )
    parser.add_argument(
        "--no-tag",
        action="store_true",
        help="Do not copy the binary to dist/km-<platform>-<arch>.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    check_platform(args.platform)
    build(
        onefile=not args.onedir,
        distpath=args.distpath.resolve(),
        workpath=args.workpath.resolve(),
        specpath=args.specpath.resolve(),
        tagged_name=not args.no_tag,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
