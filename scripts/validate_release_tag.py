#!/usr/bin/env python3
"""Validate that a Git release tag matches pyproject.toml version."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import semver

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def read_project_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if not match:
        raise SystemExit(f"Could not find version in {PYPROJECT}")
    return match.group(1)


def normalize_tag(tag: str) -> str:
    return tag.lstrip("v")


def validate_tag(tag: str) -> None:
    project_version = read_project_version()
    tag_version = normalize_tag(tag)
    try:
        semver.VersionInfo.parse(tag_version)
    except ValueError as exc:
        raise SystemExit(f"Tag {tag!r} is not valid semver: {exc}") from exc
    if tag_version != project_version:
        raise SystemExit(
            f"Tag version {tag_version!r} does not match pyproject.toml version {project_version!r}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Git tag to validate (e.g. v0.5.1)")
    args = parser.parse_args(argv)
    validate_tag(args.tag)
    print(f"Tag {args.tag} matches project version {read_project_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
