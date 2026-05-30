"""Case export import/export (spec §2.6)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from km.infrastructure.git.context import GitContext
from km.infrastructure.rdf.ref_mapping import ref_to_export_filename
from km.infrastructure.rdf.store import QuadStoreWrapper, remove_store, sha256_file
from km.logging_config import get_logger

logger = get_logger("case_export")


def compute_case_export_checksums(exports_root: Path) -> dict[str, Any]:
    checksums: dict[str, Any] = {}
    graphs_dir = exports_root / "graphs"
    gov_dir = exports_root / "governance"
    graph_checksums: dict[str, str] = {}
    if graphs_dir.is_dir():
        for ttl in sorted(graphs_dir.glob("*.ttl")):
            graph_checksums[ttl.name] = sha256_file(ttl)
    checksums["graphs"] = graph_checksums
    gov_checksums: dict[str, str] = {}
    if gov_dir.is_dir():
        for ttl in sorted(gov_dir.glob("*.ttl")):
            gov_checksums[ttl.name] = sha256_file(ttl)
    checksums["governance"] = gov_checksums
    return checksums


def write_case_sync_manifest(exports_root: Path, checksums: dict[str, Any]) -> None:
    manifest = {
        "synced_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "export_checksums": checksums,
    }
    path = exports_root / "sync-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def case_exports_need_rebuild(
    case_db_path: Path,
    exports_root: Path,
    current_checksums: dict[str, Any],
) -> bool:
    from km.infrastructure.rdf.store import store_exists

    if not store_exists(case_db_path):
        return True
    manifest_path = exports_root / "sync-manifest.json"
    if not manifest_path.is_file():
        return True
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data.get("export_checksums") != current_checksums


class CaseExportService:
    def __init__(self, exports_root: Path, case_wrapper: QuadStoreWrapper) -> None:
        self.exports_root = exports_root
        self.case_wrapper = case_wrapper
        self.graphs_dir = exports_root / "graphs"
        self.governance_dir = exports_root / "governance"

    @classmethod
    def rebuild_store_from_exports(cls, exports_root: Path, case_db_path: Path) -> None:
        graphs_dir = exports_root / "graphs"
        governance_dir = exports_root / "governance"
        remove_store(case_db_path)
        wrapper = QuadStoreWrapper(case_db_path)
        try:
            for ttl in sorted(graphs_dir.glob("*.ttl")):
                logger.debug("Importing case export %s", ttl.name)
                wrapper.load_turtle_into_graph(ttl, "")
            for ttl in sorted(governance_dir.glob("*.ttl")):
                logger.debug("Importing case governance export %s", ttl.name)
                wrapper.load_turtle_into_graph(ttl, "")
        finally:
            wrapper.close()

    def export_branch(self, git_context: GitContext) -> Path:
        filename = ref_to_export_filename(git_context.active_ref)
        export_path = self.graphs_dir / filename
        export_path.parent.mkdir(parents=True, exist_ok=True)
        turtle = self.case_wrapper.serialize_graph(git_context.graph_uri)
        export_path.write_text(turtle, encoding="utf-8")
        checksums = compute_case_export_checksums(self.exports_root)
        write_case_sync_manifest(self.exports_root, checksums)
        logger.info("Exported case graph to %s", export_path)
        return export_path

    def export_active(self, git_context: GitContext) -> Path:
        """Export the active branch graph and refresh the case export manifest."""
        return self.export_branch(git_context)
