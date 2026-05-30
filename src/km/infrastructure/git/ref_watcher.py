"""Watchdog adapter for Git ref changes (spec §5.1)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from km.logging_config import get_logger

logger = get_logger("git.ref_watcher")


class RefWatcher:
    def __init__(
        self,
        workspace_root: Path,
        on_change: Callable[[], None],
        *,
        debounce_ms: float = 100.0,
    ) -> None:
        self.workspace_root = workspace_root
        self.on_change = on_change
        self.debounce_ms = debounce_ms
        self._timer: threading.Timer | None = None
        self._observer = None

    def start(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        git_dir = self.workspace_root / ".git"
        if not git_dir.is_dir():
            logger.warning("No .git directory; git watcher not started")
            return

        handler = _GitRefHandler(self._schedule_change)
        self._observer = Observer()
        self._observer.schedule(handler, str(git_dir / "HEAD"), recursive=False)
        heads_dir = git_dir / "refs" / "heads"
        if heads_dir.is_dir():
            self._observer.schedule(handler, str(heads_dir), recursive=True)
        self._observer.start()
        logger.info("Git ref watcher started for %s", self.workspace_root)

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def _schedule_change(self) -> None:
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self.debounce_ms / 1000.0, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self) -> None:
        self._timer = None
        try:
            self.on_change()
        except Exception:
            logger.exception("Git ref watcher handler failed")


class _GitRefHandler:
    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback

    def on_modified(self, _event: object) -> None:
        self.callback()

    def on_created(self, _event: object) -> None:
        self.callback()

    def on_moved(self, _event: object) -> None:
        self.callback()
