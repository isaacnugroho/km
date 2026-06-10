"""Unit tests for git ref watcher."""

from __future__ import annotations

import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent
from watchdog.observers.api import BaseObserver

from km.infrastructure.git.ref_watcher import RefWatcher, _GitRefHandler


def test_git_ref_handler_inherits_dispatch() -> None:
    fired: list[str] = []

    handler = _GitRefHandler(lambda: fired.append("ok"))
    assert hasattr(handler, "dispatch")

    handler.dispatch(FileModifiedEvent("/tmp/.git/HEAD"))
    assert fired == ["ok"]


def test_ref_watcher_starts_and_stops(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "refs" / "heads").mkdir(parents=True)

    fired: list[str] = []
    watcher = RefWatcher(tmp_path, lambda: fired.append("ok"))
    watcher.start()

    assert watcher._observer is not None
    assert isinstance(watcher._observer, BaseObserver)

    watcher.stop()
    assert watcher._observer is None


def test_ref_watcher_skips_when_no_git_dir(tmp_path: Path) -> None:
    watcher = RefWatcher(tmp_path, lambda: None)
    watcher.start()
    assert watcher._observer is None


def test_ref_watcher_debounce_fires_callback(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "refs" / "heads").mkdir(parents=True)

    fired: list[str] = []
    watcher = RefWatcher(tmp_path, lambda: fired.append("ok"), debounce_ms=20)
    watcher.start()
    watcher._schedule_change()
    time.sleep(0.05)
    watcher.stop()
    assert fired == ["ok"]


def test_ref_watcher_stop_cancels_pending_timer(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    fired: list[str] = []
    watcher = RefWatcher(tmp_path, lambda: fired.append("ok"), debounce_ms=500)
    watcher.start()
    watcher._schedule_change()
    watcher.stop()
    time.sleep(0.05)
    assert fired == []


def test_ref_watcher_handler_failure_does_not_propagate(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    def fail() -> None:
        raise ValueError("handler failed")

    watcher = RefWatcher(tmp_path, fail, debounce_ms=10)
    watcher.start()
    watcher._fire()  # logs and swallows handler errors
    watcher.stop()


def test_git_ref_handler_created_and_moved_events() -> None:
    fired: list[str] = []
    handler = _GitRefHandler(lambda: fired.append("ok"))
    handler.on_created(FileCreatedEvent("/tmp/.git/refs/heads/main"))
    handler.on_moved(
        FileMovedEvent("/tmp/.git/refs/heads/old", "/tmp/.git/refs/heads/new")
    )
    assert fired == ["ok", "ok"]
