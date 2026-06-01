"""Sync manifest path conventions (runtime metadata under ``.km/``, Git-ignored)."""

from __future__ import annotations

from pathlib import Path

GOVERNANCE_SYNC_MANIFEST = "governance_sync-manifest.json"


def workspace_km_dir(workspace_root: Path) -> Path:
    return workspace_root / ".km"


def lo_sync_manifest_path(km_dir: Path, ontology_id: str) -> Path:
    return km_dir / f"{ontology_id}_sync-manifest.json"


def case_branch_sync_manifest_path(km_dir: Path, git_ref: str) -> Path:
    from km.infrastructure.rdf.ref_mapping import ref_to_branch_slug

    return km_dir / f"{ref_to_branch_slug(git_ref)}_sync-manifest.json"


def case_governance_sync_manifest_path(km_dir: Path) -> Path:
    return km_dir / GOVERNANCE_SYNC_MANIFEST
