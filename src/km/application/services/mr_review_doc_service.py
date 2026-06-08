"""Derived MR review markdown (spec §7.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from km.exceptions import KmError
from km.infrastructure.rdf.diff_renderer import (
    render_semantic_diff,
    summarize_semantic_changes,
)
from km.logging_config import get_logger

logger = get_logger("mr_review_doc")


class MRReviewDocService:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.mrs_dir = workspace_root / ".km" / "mrs"

    def review_doc_relative_path(self, ontology_id: str, mr_id: str) -> str:
        suffix = mr_id.removeprefix("MR-")
        return f".km/mrs/mr-{ontology_id}-{suffix}.md"

    def review_doc_path(self, ontology_id: str, mr_id: str) -> Path:
        return self.workspace_root / self.review_doc_relative_path(ontology_id, mr_id)

    def write_review_doc(
        self,
        *,
        ontology_id: str,
        mr_id: str,
        target_ontology_uri: str,
        proposal_graph_uri: str,
        rationale: str,
        author: str,
        diff_insertions: str,
        diff_deletions: str = "",
        created_at: str | None = None,
    ) -> Path:
        created = created_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        rel_path = self.review_doc_relative_path(ontology_id, mr_id)
        path = self.review_doc_path(ontology_id, mr_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        diff_block = render_semantic_diff(diff_insertions, diff_deletions)
        impact_block = summarize_semantic_changes(diff_insertions, diff_deletions)
        content = f"""# Semantic Merge Request: {mr_id}
**Status:** PENDING_APPROVAL
**Approval Command:** `approve {rel_path}`
**Reject Command:** `reject {mr_id}`
**Target Ontology:** `{target_ontology_uri}`
**Proposal Graph:** `{proposal_graph_uri}`
**Created At:** {created}
**Author:** {author}

## 1. Summary of Changes
{rationale}

### High-Level Impact
{impact_block}

---

## 2. Detailed Changes
{diff_block}
"""
        path.write_text(content, encoding="utf-8")
        logger.info("Wrote MR review doc %s", path)
        return path

    def update_review_doc_status(
        self,
        ontology_id: str,
        mr_id: str,
        status: str,
        *,
        timestamp: str | None = None,
    ) -> None:
        path = self.review_doc_path(ontology_id, mr_id)
        if not path.is_file():
            return
        text = path.read_text(encoding="utf-8")
        for pending in ("PENDING_APPROVAL", "APPROVED", "REJECTED"):
            if f"**Status:** {pending}" in text:
                text = text.replace(
                    f"**Status:** {pending}", f"**Status:** {status}", 1
                )
                break
        if timestamp and "**Resolved At:**" not in text:
            text = text.replace(
                "**Author:**", f"**Resolved At:** {timestamp}\n**Author:**", 1
            )
        path.write_text(text, encoding="utf-8")
        logger.info("Updated MR review doc %s status to %s", path, status)

    def read_review_doc(self, ontology_id: str, mr_id: str) -> str:
        path = self.review_doc_path(ontology_id, mr_id)
        if not path.is_file():
            raise KmError(f"MR review document not found: {path}")
        return path.read_text(encoding="utf-8")
