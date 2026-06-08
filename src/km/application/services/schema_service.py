"""Aggregate LO canonical schema metadata for agents."""

from __future__ import annotations

import json
from typing import Any

from km.application.services.lo_cache_service import LOCacheEntry
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("schema")

OWL_CLASS = "http://www.w3.org/2002/07/owl#Class"
OWL_OBJECT_PROPERTY = "http://www.w3.org/2002/07/owl#ObjectProperty"
OWL_DATATYPE_PROPERTY = "http://www.w3.org/2002/07/owl#DatatypeProperty"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


class SchemaService:
    def __init__(self, lo_cache_entries: list[LOCacheEntry]) -> None:
        self.lo_cache_entries = lo_cache_entries

    def learning_ontologies_document(self) -> dict[str, Any]:
        ontologies: list[dict[str, Any]] = []
        for entry in self.lo_cache_entries:
            wrapper = QuadStoreWrapper(entry.cache_db)
            try:
                canonical_uri = entry.lo_config.named_graphs.canonical
                ontologies.append(
                    {
                        "ontology_id": entry.binding.ontology_id,
                        "base_uri": entry.lo_config.base_uri,
                        "prefix": entry.lo_config.primary_prefix,
                        "namespace_uri": entry.lo_config.namespace_uri,
                        "canonical_graph": canonical_uri,
                        "classes": self._collect_terms(
                            wrapper, canonical_uri, OWL_CLASS
                        ),
                        "object_properties": self._collect_terms(
                            wrapper, canonical_uri, OWL_OBJECT_PROPERTY
                        ),
                        "datatype_properties": self._collect_terms(
                            wrapper, canonical_uri, OWL_DATATYPE_PROPERTY
                        ),
                    }
                )
            finally:
                wrapper.close()

        doc = {
            "@context": {
                "@vocab": "http://km.local/schema#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "owl": "http://www.w3.org/2002/07/owl#",
            },
            "@type": "LearningOntologySchemaBundle",
            "learning_ontologies": ontologies,
        }
        logger.debug("Built schema document for %d ontologies", len(ontologies))
        return doc

    def to_json(self) -> str:
        return json.dumps(self.learning_ontologies_document(), indent=2)

    def _collect_terms(
        self, wrapper: QuadStoreWrapper, graph_uri: str, term_type: str
    ) -> list[dict[str, str]]:
        query = f"""
            SELECT ?term ?label ?comment
            WHERE {{
                GRAPH <{graph_uri}> {{
                    ?term a <{term_type}> .
                    OPTIONAL {{ ?term <{RDFS_LABEL}> ?label }}
                    OPTIONAL {{ ?term <{RDFS_COMMENT}> ?comment }}
                }}
            }}
        """
        terms: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in wrapper.query(query):
            uri = row["term"]
            if uri is None or uri in seen:
                continue
            seen.add(uri)
            item: dict[str, str] = {"uri": uri}
            if row.get("label"):
                item["label"] = row["label"]
            if row.get("comment"):
                item["comment"] = row["comment"]
            terms.append(item)
        terms.sort(key=lambda t: t["uri"])
        return terms
