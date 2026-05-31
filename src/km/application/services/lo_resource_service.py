"""MCP resources for Learning Ontology canonical and governance graphs."""

from __future__ import annotations

from km.application.services.lo_cache_service import LOCacheService
from km.application.services.lo_source_store_service import LOSourceStoreService
from km.exceptions import KmError
from km.infrastructure.rdf.store import QuadStoreWrapper
from km.logging_config import get_logger

logger = get_logger("lo_resources")


class LOResourceService:
    def __init__(
        self,
        lo_cache: LOCacheService,
        lo_source_store: LOSourceStoreService,
    ) -> None:
        self.lo_cache = lo_cache
        self.lo_source_store = lo_source_store

    def canonical_turtle(self, ontology_id: str) -> str:
        entry = self._cache_entry(ontology_id)
        wrapper = QuadStoreWrapper(entry.cache_db)
        try:
            content = wrapper.serialize_graph(entry.lo_config.named_graphs.canonical)
            logger.debug("Serialized canonical graph for %s", ontology_id)
            return content
        finally:
            wrapper.close()

    def governance_turtle(self, ontology_id: str) -> str:
        entry = self.lo_source_store.get_entry(ontology_id)
        content = entry.wrapper.serialize_graph(entry.lo_config.named_graphs.governance)
        logger.debug("Serialized governance graph for %s from source store", ontology_id)
        return content

    def _cache_entry(self, ontology_id: str):
        for entry in self.lo_cache.entries:
            if entry.binding.ontology_id == ontology_id:
                return entry
        raise KmError(f"Unknown learning ontology: {ontology_id}")
