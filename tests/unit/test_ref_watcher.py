"""Unit tests for git ref watcher."""

from __future__ import annotations

from pathlib import Path

from watchdog.events import FileModifiedEvent
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
