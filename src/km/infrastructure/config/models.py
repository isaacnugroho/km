"""Pydantic configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AccessMode(str, Enum):
    READ_ONLY = "read_only"
    CURATOR = "curator"


class BindingKind(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"


DependencySeverity = Literal["error", "warning"]


@dataclass
class DependencyError:
    code: str
    severity: DependencySeverity
    message: str
    ontology_id: str | None = None
    cycle_path: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.ontology_id is not None:
            payload["ontology_id"] = self.ontology_id
        if self.cycle_path is not None:
            payload["cycle_path"] = self.cycle_path
        return payload


class LOBinding(BaseModel):
    ontology_id: str
    source: str | None = None
    mode: AccessMode


class QuadStoreConfig(BaseModel):
    engine: str = "sqlite-quad"
    storage_path: str = "./.km/case_quads.db"


class LOCacheConfig(BaseModel):
    base_path: str = "./.km/lo-cache"


class ExportPolicy(str, Enum):
    ON_COMMIT = "on_commit"
    ON_WRITE = "on_write"
    MANUAL = "manual"


class CaseExportsConfig(BaseModel):
    base_path: str = "./case-exports"
    export_policy: ExportPolicy = ExportPolicy.ON_COMMIT


class BranchMergePolicy(str, Enum):
    NO_AUTO_MERGE = "no_auto_merge"
    AUTO_MERGE = "auto_merge"
    AUTO_MERGE_EXCEPTION = "auto_merge_exception"


class BranchMergeConfig(BaseModel):
    policy: BranchMergePolicy = BranchMergePolicy.AUTO_MERGE_EXCEPTION


class WorkspaceConfig(BaseModel):
    workspace_id: str = "km-default-workspace"
    rootPath: str | None = None
    learning_ontologies: list[LOBinding] = Field(default_factory=list)
    quad_store: QuadStoreConfig = Field(default_factory=QuadStoreConfig)
    lo_cache: LOCacheConfig = Field(default_factory=LOCacheConfig)
    case_exports: CaseExportsConfig = Field(default_factory=CaseExportsConfig)
    branch_merge: BranchMergeConfig = Field(default_factory=BranchMergeConfig)


class LOPackageNamedGraphs(BaseModel):
    canonical: str
    governance: str


def default_lo_prefix(ontology_id: str) -> str:
    """SPARQL/Turtle prefix derived from ontology_id when config.prefix is omitted."""
    return ontology_id.replace("-", "_")


class CatalogEntry(BaseModel):
    ontology_id: str
    path: str
    label: str | None = None


class LOCatalog(BaseModel):
    catalog_version: str
    ontologies: list[CatalogEntry] = Field(default_factory=list)


class LOPackageConfig(BaseModel):
    ontology_id: str
    base_uri: str
    prefix: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    quad_store: QuadStoreConfig = Field(
        default_factory=lambda: QuadStoreConfig(storage_path="./lo_quads.db")
    )
    named_graphs: LOPackageNamedGraphs

    @property
    def primary_prefix(self) -> str:
        return self.prefix if self.prefix else default_lo_prefix(self.ontology_id)

    @property
    def namespace_uri(self) -> str:
        return f"{self.base_uri.rstrip('#/')}#"


class SyncManifest(BaseModel):
    ontology_id: str
    source: str
    mode: str
    synced_at: str
    export_checksums: dict[str, object]
