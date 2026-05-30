"""Pending merge resolution prompts (spec §5.3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from km.exceptions import KmError
from km.logging_config import get_logger

logger = get_logger("merge_prompt")


class MergePromptStore:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.km_dir = workspace_root / ".km"

    def write_prompt(self, payload: dict[str, Any]) -> Path:
        event_id = payload["event_id"]
        path = self.prompt_path(event_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        logger.warning(
            "Merge resolution required for %s → %s; see %s",
            payload["source_branch"],
            payload["target_branch"],
            path,
        )
        return path

    def read_prompt(self, event_id: str) -> dict[str, Any]:
        path = self.prompt_path(event_id)
        if not path.is_file():
            raise KmError(f"Pending merge prompt not found: {event_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_prompt(self, event_id: str) -> None:
        path = self.prompt_path(event_id)
        if path.is_file():
            path.unlink()

    def list_pending(self) -> list[dict[str, Any]]:
        prompts: list[dict[str, Any]] = []
        if not self.km_dir.is_dir():
            return prompts
        for path in sorted(self.km_dir.glob("pending-merge-*.json")):
            prompts.append(json.loads(path.read_text(encoding="utf-8")))
        return prompts

    def prompt_path(self, event_id: str) -> Path:
        return self.km_dir / f"pending-merge-{event_id}.json"
