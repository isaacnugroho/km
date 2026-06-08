"""KM domain exceptions."""

from __future__ import annotations

import errno
import json
from pathlib import Path


class KmError(Exception):
    """Base error for Knowledge Management operations."""


class ConfigError(KmError):
    """Invalid or missing workspace / LO configuration."""


class WorkspaceNotFoundError(KmError):
    """No .km/ directory found while searching for workspace root."""


class FeatureNotImplementedError(KmError):
    """Raised when a wired surface is not yet implemented."""

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(f"feature not yet implemented: {feature}")


class PermissionError(KmError):
    """Raised when an operation requires curator mode on the target binding."""


def is_store_lock_error(exc: OSError) -> bool:
    message = str(exc).lower()
    return "lock" in message or exc.errno in (errno.EAGAIN, errno.EDEADLK)


def store_open_error(path: Path, exc: OSError) -> KmError:
    if is_store_lock_error(exc):
        return KmError(
            f"Cannot open RDF store at {path}: database is locked by another "
            "process. Stop other KM instances (e.g. `km mcp` or a concurrent "
            "CLI command) and try again."
        )
    if exc.errno in (errno.EPERM, errno.EACCES):
        return KmError(f"Cannot open RDF store at {path}: permission denied.")
    if exc.errno == errno.ENOSPC:
        return KmError(f"Cannot open RDF store at {path}: no space left on device.")
    return KmError(f"Cannot open RDF store at {path}: {exc}")


def is_parser_syntax_error(exc: SyntaxError) -> bool:
    """True for pyoxigraph RDF/SPARQL parse errors (not Python source syntax)."""
    return exc.filename is None


def as_km_error(exc: BaseException) -> KmError | None:
    """Return a user-facing KmError for known infrastructure failures, or None."""
    if isinstance(exc, KmError):
        return exc
    if isinstance(exc, LookupError):
        return KmError(str(exc))
    if isinstance(exc, FileNotFoundError):
        return KmError(str(exc))
    if isinstance(exc, json.JSONDecodeError):
        return ConfigError(
            f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"
        )
    if isinstance(exc, SyntaxError) and is_parser_syntax_error(exc):
        return KmError(f"Parse error: {exc.msg or exc}")
    if isinstance(exc, ValueError):
        return KmError(str(exc))
    if type(exc).__name__ == "ValidationError":
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            return ConfigError(f"Invalid configuration: {exc}")
    if isinstance(exc, OSError):
        if is_store_lock_error(exc):
            return KmError(
                "RDF store is locked by another process. Stop other KM instances "
                "(e.g. `km mcp` or a concurrent CLI command) and try again."
            )
        if exc.errno in (errno.EPERM, errno.EACCES):
            return KmError(f"Permission denied: {exc}")
        if exc.errno == errno.ENOSPC:
            return KmError("No space left on device.")
        return KmError(f"I/O error: {exc}")
    return None
