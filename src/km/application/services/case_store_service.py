"""Case ontology store bootstrap (spec §2.6, minimal Phase 1)."""

from __future__ import annotations

from pathlib import Path

from km.infrastructure.rdf.store import (
    QuadStoreWrapper,
    needs_cache_rebuild,
    remove_store,
    sha256_file,
    store_exists,
)
from km.logging_config import get_logger

logger = get_logger("case_store")


def _compute_case_export_checksums(exports_root: Path) -> dict[str, object]:
    checksums: dict[str, object] = {}
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


class CaseStoreService:
    def __init__(self, workspace_root: Path, case_db_path: Path, exports_root: Path) -> None:
        self.workspace_root = workspace_root
        self.case_db_path = case_db_path
        self.exports_root = exports_root
        self.wrapper: QuadStoreWrapper | None = None

    def bootstrap(self) -> QuadStoreWrapper:
        manifest_path = self.exports_root / "sync-manifest.json"
        current_checksums = _compute_case_export_checksums(self.exports_root)
        has_exports = bool(current_checksums.get("graphs")) or bool(
            current_checksums.get("governance")
        )

        rebuild = needs_cache_rebuild(self.case_db_path, manifest_path, current_checksums)

        if rebuild and has_exports:
            logger.info("Bootstrapping case store from case-exports")
            remove_store(self.case_db_path)
            wrapper = QuadStoreWrapper(self.case_db_path)
            self._import_exports(wrapper)
            wrapper.close()
        elif not store_exists(self.case_db_path):
            logger.info("Creating empty case store at %s", self.case_db_path)

        self.wrapper = QuadStoreWrapper(self.case_db_path)
        return self.wrapper

    def _import_exports(self, wrapper: QuadStoreWrapper) -> None:
        graphs_dir = self.exports_root / "graphs"
        if graphs_dir.is_dir():
            for ttl in sorted(graphs_dir.glob("*.ttl")):
                logger.debug("Importing case graph export %s", ttl.name)
                wrapper.load_turtle_into_graph(ttl, "")

        gov_dir = self.exports_root / "governance"
        if gov_dir.is_dir():
            for ttl in sorted(gov_dir.glob("*.ttl")):
                logger.debug("Importing case governance export %s", ttl.name)
                wrapper.load_turtle_into_graph(ttl, "")

    def close(self) -> None:
        if self.wrapper:
            self.wrapper.close()
            self.wrapper = None
