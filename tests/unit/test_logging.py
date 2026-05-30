"""Unit tests for logging configuration."""

from __future__ import annotations

import logging
import sys

from km.logging_config import configure_logging, get_logger, has_stdout_handler


def test_configure_logging_debug(monkeypatch) -> None:
    monkeypatch.delenv("KM_LOG_FILE", raising=False)
    configure_logging(level="DEBUG", mcp_mode=True)
    root = logging.getLogger("km")
    assert root.level == logging.DEBUG
    assert not has_stdout_handler()


def test_no_stdout_handlers_in_mcp_mode() -> None:
    configure_logging(mcp_mode=True)
    logger = logging.getLogger("km")
    for handler in logger.handlers:
        assert getattr(handler, "stream", None) is not sys.stdout
