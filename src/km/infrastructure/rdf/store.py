"""pyoxigraph store wrapper and RDF import utilities."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyoxigraph import Literal, NamedNode, Quad, RdfFormat, Store

from km.infrastructure.config.models import SyncManifest
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
        if GRAPH_URI_PATTERN.search(content.decode("utf-8", errors="replace")):
            self.store.load(
                input=content,
                format=TURTLE,
                lenient=True,
            )
        else:
            self.store.load(
                input=content,
                format=TURTLE,
                to_graph=NamedNode(graph_uri),
                lenient=True,
            )

    def load_turtle_bytes_into_graph(self, content: bytes, graph_uri: str) -> None:
        if GRAPH_URI_PATTERN.search(content.decode("utf-8", errors="replace")):
            self.store.load(input=content, format=TURTLE, lenient=True)
        else:
            self.store.load(
                input=content,
                format=TURTLE,
                to_graph=NamedNode(graph_uri),
                lenient=True,
            )

    def query(self, sparql: str) -> list[dict[str, str | None]]:
        results: list[dict[str, str | None]] = []
        for row in self.store.query(sparql):
            if hasattr(row, "items"):
                results.append({k: _term_to_str(v) for k, v in row.items()})
        return results

    def close(self) -> None:
        del self.store


def _term_to_str(term: object) -> str | None:
    if term is None:
        return None
    if isinstance(term, Literal):
        return str(term)
    if isinstance(term, NamedNode):
        return str(term)
    return str(term)
