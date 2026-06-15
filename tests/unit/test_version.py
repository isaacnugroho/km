"""Version metadata and release tag validation tests."""

from __future__ import annotations

import importlib
import re
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

import pytest
import semver

import km
from km import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    assert match is not None
    return match.group(1)


def test_package_version_matches_pyproject() -> None:
    assert __version__ == _pyproject_version()


def test_validate_release_tag_script_accepts_matching_tag(tmp_path: Path) -> None:
    from scripts.validate_release_tag import validate_tag

    validate_tag(f"v{_pyproject_version()}")


def test_validate_release_tag_script_rejects_mismatch() -> None:
    from scripts.validate_release_tag import validate_tag

    with pytest.raises(SystemExit, match="does not match"):
        validate_tag("v9.9.9")


def test_semver_parse_release_tag() -> None:
    project_version = _pyproject_version()
    parsed = semver.VersionInfo.parse(project_version)
    major, minor, patch = project_version.split(".")
    assert parsed.major == int(major)
    assert parsed.minor == int(minor)
    assert parsed.patch == int(patch)


def test_package_version_fallback_when_not_installed() -> None:
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError()):
        reloaded = importlib.reload(km)
        assert reloaded.__version__ == _pyproject_version()
    importlib.reload(km)
