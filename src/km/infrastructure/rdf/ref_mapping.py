"""Git ref ↔ export filename ↔ named graph URI mapping (spec §2.6)."""

from __future__ import annotations

import re

GRAPH_BASE = "http://km.local/graphs"


def branch_path_to_slug(branch_path: str) -> str:
    """Branch path with non-alphanumeric runs replaced by ``-`` (e.g. ``feature/foo`` → ``feature-foo``)."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", branch_path)
    return slug.strip("-")


def ref_to_branch_slug(git_ref: str) -> str:
    return branch_path_to_slug(ref_to_branch_path(git_ref))


def branch_path_to_graph_uri(branch_path: str) -> str:
    return f"{GRAPH_BASE}/{branch_path_to_slug(branch_path)}"


def graph_uri_to_branch_slug(graph_uri: str) -> str:
    prefix = f"{GRAPH_BASE}/"
    if not graph_uri.startswith(prefix):
        raise ValueError(f"Not a case branch graph URI: {graph_uri}")
    return graph_uri[len(prefix) :]


def ref_to_branch_path(git_ref: str) -> str:
    if git_ref.startswith("refs/heads/"):
        return git_ref[len("refs/heads/") :]
    if git_ref.startswith("refs/"):
        return git_ref[len("refs/") :]
    return git_ref


def ref_to_export_filename(git_ref: str) -> str:
    """refs/heads/feature/foo → refs-heads-feature-foo.ttl"""
    return git_ref.replace("/", "-") + ".ttl"


def export_filename_to_graph_uri(filename: str) -> str | None:
    """Best-effort parse of export filename; prefer ref_to_branch_path when ref is known."""
    if not filename.endswith(".ttl"):
        return None
    stem = filename[: -len(".ttl")]
    if not stem.startswith("refs-heads-"):
        return None
    branch_segment = stem[len("refs-heads-") :]
    return branch_path_to_graph_uri(branch_segment)


def export_filename_to_git_ref(filename: str) -> str | None:
    """Best-effort inverse of ``ref_to_export_filename``."""
    graph_uri = export_filename_to_graph_uri(filename)
    if graph_uri is not None:
        slug = graph_uri_to_branch_slug(graph_uri)
        return f"refs/heads/{slug.replace('-', '/')}"
    if not filename.endswith(".ttl"):
        return None
    stem = filename[: -len(".ttl")]
    if stem.startswith("refs-"):
        remainder = stem[len("refs-") :]
        return f"refs/{remainder.replace('-', '/')}"
    return None
