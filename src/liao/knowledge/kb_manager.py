"""Knowledge base manager -- high-level interface for KB operations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from liao.knowledge.kb_config import KBConfig

logger = logging.getLogger(__name__)


class KBManager:
    """High-level knowledge base management.

    Provides a unified interface for:
    - Listing available KBs (including GangDan-compatible collections)
    - Searching across multiple KBs with synthesis
    - Managing strict KB mode

    This class is designed to be compatible with GangDan's ChromaDB format,
    allowing Liao to read GangDan's exported knowledge bases directly.

    Example:
        config = KBConfig()
        # Point to GangDan's ChromaDB directory for compatibility
        config.chroma_dir = str(Path.home() / "GangDan" / "data" / "chroma")

        manager = KBManager(config)

        # List all available KBs
        kbs = manager.list_kbs()

        # Search with multi-KB synthesis
        context, sources = manager.search_and_synthesize("How to use NumPy arrays?")

        # Check if strict mode is enabled
        if manager.is_strict_mode():
            print("Will refuse to answer without KB results")
    """

    def __init__(self, config: KBConfig):
        """Initialize KB manager.

        Args:
            config: KB configuration
        """
        self.config = config
        from liao.knowledge.retriever import KBRetriever
        self.retriever = KBRetriever(config)

    def list_kbs(self) -> list[dict]:
        """List all available knowledge bases.

        Returns:
            List of dicts with keys: name, collection_id, doc_count
        """
        if not self.retriever.is_available:
            return []

        collections = self.retriever.list_collections()
        kbs = []

        for coll_name in collections:
            try:
                # Try to get document count
                coll = self.retriever.client.get_collection(coll_name)
                count = coll.count() if hasattr(coll, "count") else "unknown"

                kbs.append({
                    "name": coll_name,
                    "collection_id": coll_name,
                    "doc_count": count,
                })
            except Exception as e:
                logger.debug(f"Error accessing collection {coll_name}: {e}")
                kbs.append({
                    "name": coll_name,
                    "collection_id": coll_name,
                    "doc_count": "unknown",
                })

        return kbs

    def search_and_synthesize(
        self,
        query: str,
        collections: list[str] | None = None,
        max_chars: int = 6000,
    ) -> tuple[str, list[str]]:
        """Search KBs and synthesize results from multiple sources.

        This method performs cross-lingual retrieval and synthesizes
        information from multiple knowledge bases, similar to GangDan's
        multi-KB synthesis feature.

        Args:
            query: Search query
            collections: Specific KBs to search (None = all available)
            max_chars: Maximum context length

        Returns:
            Tuple of (synthesized_context, list_of_sources)
        """
        if not self.retriever.is_available:
            logger.warning("KB retriever not available")
            return "", []

        # Use retriever to build context
        context, sources = self.retriever.build_context(
            query,
            collections=collections,
            max_chars=max_chars,
        )

        if sources:
            logger.info(f"Synthesized from {len(sources)} sources: {', '.join(sources)}")

        return context, sources

    def is_strict_mode(self) -> bool:
        """Check if strict KB mode is enabled.

        In strict mode, the system will refuse to answer questions
        when no relevant KB content is found.

        Returns:
            True if strict mode is enabled
        """
        return self.config.strict_kb_mode

    def set_strict_mode(self, enabled: bool) -> None:
        """Enable or disable strict KB mode.

        Args:
            enabled: Whether to enable strict mode
        """
        self.config.strict_kb_mode = enabled
        from liao.knowledge.kb_config import save_kb_config
        save_kb_config(self.config)
        logger.info(f"Strict KB mode {'enabled' if enabled else 'disabled'}")

    def set_kb_scope(self, collections: list[str]) -> None:
        """Set which KBs to search by default.

        Args:
            collections: List of collection names to search
        """
        self.config.kb_scope = collections
        from liao.knowledge.kb_config import save_kb_config
        save_kb_config(self.config)
        logger.info(f"KB scope set to: {', '.join(collections) if collections else 'all'}")

    def clear_kb_scope(self) -> None:
        """Clear KB scope to search all available KBs."""
        self.config.kb_scope = []
        from liao.knowledge.kb_config import save_kb_config
        save_kb_config(self.config)
        logger.info("KB scope cleared (will search all KBs)")
