"""Case export import/export (spec §2.6)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from km.infrastructure.git.context import GitContext
from km.infrastructure.rdf.ref_mapping import (
    export_filename_to_git_ref,
    export_filename_to_graph_uri,
    graph_uri_to_branch_slug,
    ref_to_branch_slug,
    ref_to_export_filename,
)
from km.infrastructure.rdf.store import QuadStoreWrapper, remove_store, sha256_file
from km.infrastructure.sync_manifest import (
    case_branch_sync_manifest_path,
    case_governance_sync_manifest_path,
)
from km.logging_config import get_logger

logger = get_logger("case_export")


def ensure_case_exports_dirs(exports_root: Path) -> None:
    """Create ``graphs/`` and ``governance/`` under the case export root when absent."""
    (exports_root / "graphs").mkdir(parents=True, exist_ok=True)
    (exports_root / "governance").mkdir(parents=True, exist_ok=True)


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


def _write_json_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_case_branch_sync_manifest(
    km_dir: Path,
    git_ref: str,
    graph_path: Path,
) -> None:
    slug = ref_to_branch_slug(git_ref)
    manifest = {
        "synced_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_ref": git_ref,
        "branch_slug": slug,
        "graph_file": graph_path.name,
        "export_checksums": {"graph": sha256_file(graph_path)},
    }
    _write_json_manifest(case_branch_sync_manifest_path(km_dir, git_ref), manifest)


def write_case_governance_sync_manifest(km_dir: Path, exports_root: Path) -> None:
    gov_dir = exports_root / "governance"
    gov_checksums: dict[str, str] = {}
    if gov_dir.is_dir():
        for ttl in sorted(gov_dir.glob("*.ttl")):
            gov_checksums[ttl.name] = sha256_file(ttl)
    manifest = {
        "synced_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "export_checksums": {"governance": gov_checksums},
    }
    _write_json_manifest(case_governance_sync_manifest_path(km_dir), manifest)


def _branch_manifest_matches(graph_path: Path, manifest_path: Path) -> bool:
    if not manifest_path.is_file():
        return False
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored = data.get("export_checksums", {})
    return stored.get("graph") == sha256_file(graph_path)


def _governance_manifest_matches(exports_root: Path, manifest_path: Path) -> bool:
    gov_dir = exports_root / "governance"
    if not gov_dir.is_dir() or not any(gov_dir.glob("*.ttl")):
        return True
    if not manifest_path.is_file():
        return False
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored = data.get("export_checksums", {}).get("governance", {})
    current: dict[str, str] = {}
    for ttl in sorted(gov_dir.glob("*.ttl")):
        current[ttl.name] = sha256_file(ttl)
    return stored == current


def case_exports_need_rebuild(
    case_db_path: Path,
    exports_root: Path,
    km_dir: Path,
) -> bool:
    from km.infrastructure.rdf.store import store_exists

    if not store_exists(case_db_path):
        return True

    graphs_dir = exports_root / "graphs"
    if not graphs_dir.is_dir() or not any(graphs_dir.glob("*.ttl")):
        return False

    for graph_path in sorted(graphs_dir.glob("*.ttl")):
        git_ref = export_filename_to_git_ref(graph_path.name)
        if git_ref is None:
            return True
        manifest_path = case_branch_sync_manifest_path(km_dir, git_ref)
        if not _branch_manifest_matches(graph_path, manifest_path):
            return True

    return not _governance_manifest_matches(
        exports_root, case_governance_sync_manifest_path(km_dir)
    )


class CaseExportService:
    def __init__(
        self,
        exports_root: Path,
        case_wrapper: QuadStoreWrapper,
        km_dir: Path,
    ) -> None:
        self.exports_root = exports_root
        self.case_wrapper = case_wrapper
        self.km_dir = km_dir
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
                content = ttl.read_bytes()
                graph_uri = export_filename_to_graph_uri(ttl.name) or ""
                if graph_uri:
                    logger.debug(
                        "Importing case export %s → graph %s (slug %s)",
                        ttl.name,
                        graph_uri,
                        graph_uri_to_branch_slug(graph_uri),
                    )
                else:
                    logger.debug("Importing case export %s", ttl.name)
                wrapper.load_turtle_bytes_into_graph(content, graph_uri)
            for ttl in sorted(governance_dir.glob("*.ttl")):
                logger.debug("Importing case governance export %s", ttl.name)
                wrapper.load_turtle_bytes_into_graph(ttl.read_bytes(), "")
        finally:
            wrapper.close()

    def export_branch(self, git_context: GitContext) -> Path:
        filename = ref_to_export_filename(git_context.active_ref)
        export_path = self.graphs_dir / filename
        export_path.parent.mkdir(parents=True, exist_ok=True)
        turtle = self.case_wrapper.serialize_graph(git_context.graph_uri)
        export_path.write_text(turtle, encoding="utf-8")
        write_case_branch_sync_manifest(
            self.km_dir, git_context.active_ref, export_path
        )
        write_case_governance_sync_manifest(self.km_dir, self.exports_root)
        logger.info("Exported case graph to %s", export_path)
        return export_path

    def export_active(self, git_context: GitContext) -> Path:
        """Export the active branch graph and refresh branch sync manifests in ``.km/``."""
        return self.export_branch(git_context)
