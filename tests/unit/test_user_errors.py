"""Unit tests for user-facing error normalization."""

from __future__ import annotations

import errno
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from km.exceptions import (
    ConfigError,
    FeatureNotImplementedError,
    KmError,
    as_km_error,
    is_parser_syntax_error,
    is_store_lock_error,
    store_open_error,
)
from km.infrastructure.config.loader import load_workspace_config
from km.infrastructure.rdf.store import QuadStoreWrapper


def test_is_store_lock_error_detects_lock_message() -> None:
    assert is_store_lock_error(
        OSError("While lock file: /tmp/db/LOCK: Resource temporarily unavailable")
    )


def test_is_store_lock_error_detects_eagain() -> None:
    assert is_store_lock_error(
        OSError(errno.EAGAIN, "Resource temporarily unavailable")
    )


def test_store_open_error_lock() -> None:
    path = Path("/tmp/lo_quads.db")
    exc = OSError(f"While lock file: {path / 'LOCK'}: Resource temporarily unavailable")
    err = store_open_error(path, exc)
    assert isinstance(err, KmError)
    assert "locked by another process" in str(err)


def test_store_open_error_permission() -> None:
    path = Path("/tmp/lo_quads.db")
    err = store_open_error(path, OSError(errno.EACCES, "Permission denied"))
    assert "permission denied" in str(err).lower()


def test_store_open_error_no_space() -> None:
    path = Path("/tmp/lo_quads.db")
    err = store_open_error(path, OSError(errno.ENOSPC, "No space left on device"))
    assert "no space left" in str(err).lower()


def test_as_km_error_lookup() -> None:
    err = as_km_error(LookupError("Unknown learning ontology: foo"))
    assert err is not None
    assert "Unknown learning ontology" in str(err)


def test_as_km_error_file_not_found() -> None:
    err = as_km_error(FileNotFoundError("MR review document not found: /tmp/mr.md"))
    assert err is not None
    assert "MR review document not found" in str(err)


def test_as_km_error_parser_syntax() -> None:
    err = as_km_error(SyntaxError("Parser error at line 1"))
    assert err is not None
    assert "Parse error" in str(err)


def test_as_km_error_python_syntax_not_wrapped() -> None:
    err = as_km_error(SyntaxError("invalid syntax", ("file.py", 1, 0, "bad\n", 1, 0)))
    assert err is None


def test_is_parser_syntax_error() -> None:
    assert is_parser_syntax_error(SyntaxError("Parser error"))
    assert not is_parser_syntax_error(
        SyntaxError("invalid syntax", ("file.py", 1, 0, "bad\n", 1, 0))
    )


def test_as_km_error_json_decode() -> None:
    err = as_km_error(json.JSONDecodeError("Expecting value", "doc", 0))
    assert isinstance(err, ConfigError)
    assert "Invalid JSON" in str(err)


def test_as_km_error_os_lock_without_path() -> None:
    err = as_km_error(
        OSError("While lock file: /tmp/db/LOCK: Resource temporarily unavailable")
    )
    assert err is not None
    assert "locked by another process" in str(err)


def test_quad_store_wrapper_raises_km_error_on_lock(tmp_path: Path) -> None:
    store_path = tmp_path / "lo_quads.db"
    lock_error = OSError(
        f"IO error: While lock file: {store_path / 'LOCK'}: Resource temporarily unavailable"
    )
    with patch("km.infrastructure.rdf.store.Store", side_effect=lock_error):
        with pytest.raises(KmError, match="database is locked by another process"):
            QuadStoreWrapper(store_path)


def test_quad_store_wrapper_raises_km_error_on_no_space(tmp_path: Path) -> None:
    store_path = tmp_path / "lo_quads.db"
    with patch(
        "km.infrastructure.rdf.store.Store",
        side_effect=OSError(errno.ENOSPC, "No space"),
    ):
        with pytest.raises(KmError, match="no space left on device"):
            QuadStoreWrapper(store_path)


def test_quad_store_wrapper_invalid_rdf_raises_km_error(tmp_path: Path) -> None:
    wrapper = QuadStoreWrapper(tmp_path / "db")
    with pytest.raises(KmError, match="Failed to load RDF"):
        wrapper.load_turtle_bytes_into_graph(
            b"not valid turtle {{{", "http://example.org/g"
        )


def test_quad_store_wrapper_invalid_sparql_raises_km_error(tmp_path: Path) -> None:
    wrapper = QuadStoreWrapper(tmp_path / "db")
    with pytest.raises(KmError, match="Invalid SPARQL query"):
        wrapper.query("SELECT ?x WHERE { ?x ?y ")


def test_load_workspace_config_invalid_json(tmp_workspace: Path) -> None:
    config_path = tmp_workspace / ".km" / "config.json"
    config_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_workspace_config(tmp_workspace)


def test_feature_not_implemented_error_sets_feature() -> None:
    err = FeatureNotImplementedError("export_case")
    assert err.feature == "export_case"
    assert "export_case" in str(err)


def test_store_open_error_generic_os_error() -> None:
    path = Path("/tmp/lo_quads.db")
    err = store_open_error(path, OSError("disk failure"))
    assert "disk failure" in str(err)


def test_as_km_error_returns_km_error_instance() -> None:
    original = KmError("already normalized")
    assert as_km_error(original) is original


def test_as_km_error_value_error() -> None:
    err = as_km_error(ValueError("bad value"))
    assert err is not None
    assert "bad value" in str(err)


def test_as_km_error_os_permission() -> None:
    err = as_km_error(OSError(errno.EACCES, "Permission denied"))
    assert err is not None
    assert "Permission denied" in str(err)


def test_as_km_error_os_no_space() -> None:
    err = as_km_error(OSError(errno.ENOSPC, "No space"))
    assert err is not None
    assert "No space left on device" in str(err)


def test_as_km_error_os_generic() -> None:
    err = as_km_error(OSError("read-only filesystem"))
    assert err is not None
    assert "I/O error" in str(err)
