"""Persisted set of completed branch merge event ids (spec §5.3)."""

from __future__ import annotations

import json
from pathlib import Path

from km.logging_config import get_logger

logger = get_logger("processed_merge_events")


class ProcessedMergeEventStore:
    def __init__(self, workspace_root: Path) -> None:
        self.path = workspace_root / ".km" / "processed-merge-events.json"
        self._event_ids: set[str] = set()
        self._load()

    def contains(self, event_id: str) -> bool:
        return event_id in self._event_ids

    def add(self, event_id: str) -> None:
        if event_id in self._event_ids:
            return
        self._event_ids.add(event_id)
        self._save()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Ignoring corrupt processed merge events file: %s", self.path)
            return
        ids = data.get("event_ids")
        if isinstance(ids, list):
            self._event_ids = {str(item) for item in ids}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"event_ids": sorted(self._event_ids)}
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
