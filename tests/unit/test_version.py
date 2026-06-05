"""Version metadata and release tag validation tests."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import semver

from km import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def test_package_version_matches_pyproject() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    assert match is not None
    assert __version__ == match.group(1)


def test_validate_release_tag_script_accepts_matching_tag(tmp_path: Path) -> None:
    from scripts.validate_release_tag import validate_tag

    validate_tag("v0.5.1")


def test_validate_release_tag_script_rejects_mismatch() -> None:
    from scripts.validate_release_tag import validate_tag

    with pytest.raises(SystemExit, match="does not match"):
        validate_tag("v9.9.9")


def test_semver_parse_release_tag() -> None:
    parsed = semver.VersionInfo.parse("0.5.1")
    assert parsed.major == 0
    assert parsed.minor == 5
    assert parsed.patch == 1
