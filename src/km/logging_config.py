"""Central logging configuration (stderr-safe for MCP stdio)."""

from __future__ import annotations

import logging
import os
import sys
from typing import Literal

DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(
    *,
    level: str | None = None,
    log_file: str | None = None,
    mcp_mode: bool = True,
) -> None:
    """Configure root logging for KM.

    All handlers write to stderr (or file) — never stdout — so MCP JSON-RPC is safe.
    In MCP mode the default stderr level is WARNING so IDE clients do not treat
    INFO lines as server errors (they monitor stderr).
    """
    if level is None and mcp_mode and "KM_LOG_LEVEL" not in os.environ:
        log_level = "WARNING"
    else:
        log_level = (level or os.environ.get("KM_LOG_LEVEL", "INFO")).upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    root = logging.getLogger("km")
    root.handlers.clear()
    root.setLevel(numeric_level)
    root.propagate = False

    formatter = logging.Formatter(DEFAULT_FORMAT)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(numeric_level)
    root.addHandler(stderr_handler)

    file_path = log_file or os.environ.get("KM_LOG_FILE")
    if file_path:
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        root.addHandler(file_handler)

    if mcp_mode:
        _ensure_no_stdout_handlers(root)
        if has_stdout_handler():
            raise RuntimeError("KM logging must not attach handlers to stdout in MCP mode")


def _ensure_no_stdout_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        stream = getattr(handler, "stream", None)
        if stream is sys.stdout:
            raise RuntimeError("KM logging must not attach handlers to stdout in MCP mode")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"km.{name}")


def has_stdout_handler() -> bool:
    """Return True if any km logger handler writes to stdout."""
    logger = logging.getLogger("km")
    for handler in logger.handlers:
        if getattr(handler, "stream", None) is sys.stdout:
            return True
    return False
