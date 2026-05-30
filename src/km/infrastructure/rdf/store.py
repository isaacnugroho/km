"""pyoxigraph store wrapper and RDF import utilities."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyoxigraph import BlankNode, Literal, NamedNode, Quad, RdfFormat, Store

from km.infrastructure.config.models import LOPackageConfig, SyncManifest
from km.infrastructure.rdf.serialization import serialize_graph_block
from km.logging_config import get_logger

logger = get_logger("rdf.store")

GRAPH_URI_PATTERN = re.compile(r"GRAPH\s*<([^>]+)>\s*\{", re.IGNORECASE)
TURTLE = RdfFormat.TURTLE


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def store_exists(path: Path) -> bool:
    """Return True if a pyoxigraph store exists at path (file or directory backend)."""
    return path.exists()


def remove_store(path: Path) -> None:
    """Remove an existing pyoxigraph store path."""
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def compute_export_checksums(source_path: Path) -> dict[str, Any]:
    main_path = source_path / "exports" / "main.ttl"
    checksums: dict[str, Any] = {"main.ttl": sha256_file(main_path)}
    governance_dir = source_path / "exports" / "governance"
    gov_checksums: dict[str, str] = {}
    if governance_dir.is_dir():
        for ttl_file in sorted(governance_dir.glob("*.ttl")):
            gov_checksums[ttl_file.name] = sha256_file(ttl_file)
    checksums["governance"] = gov_checksums
    return checksums


def load_sync_manifest(manifest_path: Path) -> SyncManifest | None:
    if not manifest_path.is_file():
        return None
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return SyncManifest.model_validate(data)


def write_sync_manifest(
    manifest_path: Path,
    *,
    ontology_id: str,
    source: str,
    mode: str,
    export_checksums: dict[str, Any],
) -> SyncManifest:
    manifest = SyncManifest(
        ontology_id=ontology_id,
        source=source,
        mode=mode,
        synced_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        export_checksums=export_checksums,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.model_dump(), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def checksums_match(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    return stored == current


def needs_cache_rebuild(
    cache_db: Path,
    manifest_path: Path,
    current_checksums: dict[str, Any],
) -> bool:
    if not store_exists(cache_db):
        return True
    manifest = load_sync_manifest(manifest_path)
    if manifest is None:
        return True
    return not checksums_match(manifest.export_checksums, current_checksums)


def import_lo_exports_to_store(
    source_path: Path,
    lo_config: LOPackageConfig,
    wrapper: QuadStoreWrapper,
) -> None:
    """Import Git-tracked LO exports into a quad store (spec §2.3 / §2.5)."""
    main_ttl = source_path / "exports" / "main.ttl"
    logger.debug("Importing %s → %s", main_ttl, lo_config.named_graphs.canonical)
    wrapper.load_turtle_into_graph(main_ttl, lo_config.named_graphs.canonical)

    governance_dir = source_path / "exports" / "governance"
    if governance_dir.is_dir():
        for ttl_file in sorted(governance_dir.glob("*.ttl")):
            logger.debug("Importing governance shard %s", ttl_file.name)
            wrapper.load_turtle_into_graph(ttl_file, lo_config.named_graphs.governance)


class QuadStoreWrapper:
    """Thin wrapper around pyoxigraph Store."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.store = Store(str(path))

    def clear(self) -> None:
        self.store.clear()

    def load_turtle_into_graph(self, turtle_path: Path, graph_uri: str) -> None:
        content = turtle_path.read_bytes()
        self._load_rdf_bytes(content, graph_uri)

    def load_turtle_bytes_into_graph(self, content: bytes, graph_uri: str) -> None:
        self._load_rdf_bytes(content, graph_uri)

    def _load_rdf_bytes(self, content: bytes, graph_uri: str) -> None:
        text = content.decode("utf-8", errors="replace")
        if GRAPH_URI_PATTERN.search(text):
            self.store.load(
                input=content,
                format=RdfFormat.TRIG,
                lenient=True,
            )
        elif graph_uri:
            self.store.load(
                input=content,
                format=TURTLE,
                to_graph=NamedNode(graph_uri),
                lenient=True,
            )
        else:
            self.store.load(input=content, format=TURTLE, lenient=True)

    def query(self, sparql: str) -> list[dict[str, str | None]]:
        results: list[dict[str, str | None]] = []
        solution = self.store.query(sparql)
        if isinstance(solution, bool):
            return results
        variables = [
            var.value if hasattr(var, "value") else str(var).removeprefix("?")
            for var in solution.variables
        ]
        for row in solution:
            results.append({var: _term_to_str(row[var]) for var in variables})
        return results

    def ask(self, sparql: str) -> bool:
        result = self.store.query(sparql)
        if isinstance(result, bool):
            return result
        return bool(result)

    def quads_in_graph(self, graph_uri: str) -> list[Quad]:
        graph = NamedNode(graph_uri)
        return list(self.store.quads_for_pattern(None, None, None, graph))

    def has_quad(self, quad: Quad) -> bool:
        return bool(
            list(
                self.store.quads_for_pattern(
                    quad.subject, quad.predicate, quad.object, quad.graph_name
                )
            )
        )

    def add_quad(self, quad: Quad) -> bool:
        """Add quad if not present. Returns True if a new quad was added."""
        if self.has_quad(quad):
            return False
        self.store.add(quad)
        return True

    def add_quads(self, quads: list[Quad]) -> int:
        added = 0
        for quad in quads:
            if self.add_quad(quad):
                added += 1
        return added

    def serialize_graph(self, graph_uri: str) -> str:
        quads = self.quads_in_graph(graph_uri)
        if not quads:
            return f"GRAPH <{graph_uri}> {{\n}}\n"
        return serialize_graph_block(graph_uri, quads)

    def close(self) -> None:
        del self.store


def _term_to_str(term: object) -> str | None:
    if term is None:
        return None
    if isinstance(term, (Literal, NamedNode, BlankNode)):
        return term.value
    return str(term)
