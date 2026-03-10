"""Knowledge base retriever -- searches ChromaDB compatible with GangDan format."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from liao.knowledge.kb_config import KBConfig

logger = logging.getLogger(__name__)


class KBRetriever:
    """Vector similarity search over ChromaDB knowledge bases.

    This class is designed to read ChromaDB databases in GangDan's format,
    allowing Liao to access the same knowledge bases without duplication.

    Example:
        config = KBConfig()
        retriever = KBRetriever(config)

        # Search across all KBs
        results = retriever.search("NumPy arrays", top_k=5)

        # Search specific KBs
        results = retriever.search("pandas DataFrame", collections=["numpy", "pandas"], top_k=3)

        # Build context for LLM
        context = retriever.build_context("How to use PyTorch?", collections=["pytorch"])
    """

    def __init__(self, config: KBConfig):
        """Initialize retriever.

        Args:
            config: KB configuration
        """
        self.config = config
        self.client = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        """Initialize ChromaDB client."""
        try:
            import chromadb
            chroma_path = Path(self.config.chroma_dir)
            if not chroma_path.exists():
                logger.warning(f"ChromaDB directory not found: {chroma_path}")
                return

            self.client = chromadb.PersistentClient(path=str(chroma_path))
            logger.info(f"ChromaDB initialized: {chroma_path}")
        except ImportError:
            logger.error("ChromaDB not installed. Install with: pip install chromadb")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")

    @property
    def is_available(self) -> bool:
        """Check if ChromaDB is available."""
        return self.client is not None

    def list_collections(self) -> list[str]:
        """List all available KB collections.

        Returns:
            List of collection names
        """
        if not self.client:
            return []
        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def search(
        self,
        query: str,
        collections: list[str] | None = None,
        top_k: int = 10,
        distance_threshold: float = 0.5,
    ) -> list[dict]:
        """Search for relevant documents using vector similarity.

        Args:
            query: Search query text
            collections: List of KB collection names to search (None = all)
            top_k: Maximum results per collection
            distance_threshold: Maximum cosine distance for relevance

        Returns:
            List of dicts with keys: text, metadata, distance, source
        """
        if not self.client:
            logger.warning("ChromaDB not initialized")
            return []

        try:
            # Get embedding for query
            embedding = self._embed_query(query)
            if not embedding:
                logger.error("Failed to generate query embedding")
                return []

            # Determine which collections to search
            if collections is None:
                collections = self.list_collections()
            elif isinstance(collections, str):
                collections = [collections]

            # Filter by kb_scope if configured
            if self.config.kb_scope:
                collections = [c for c in collections if c in self.config.kb_scope]

            if not collections:
                logger.warning("No collections to search")
                return []

            # Search each collection
            all_results = []
            for coll_name in collections:
                try:
                    results = self._search_collection(coll_name, embedding, top_k)
                    # Filter by distance threshold
                    filtered = [r for r in results if r.get("distance", 1.0) < distance_threshold]
                    all_results.extend(filtered)
                except Exception as e:
                    logger.error(f"Error searching collection {coll_name}: {e}")

            # Sort by distance and return
            all_results.sort(key=lambda x: x.get("distance", 1.0))
            return all_results[:top_k * len(collections)]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _search_collection(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict]:
        """Search a single ChromaDB collection.

        Args:
            collection_name: Collection name
            query_embedding: Query embedding vector
            top_k: Number of results

        Returns:
            List of result dicts
        """
        try:
            collection = self.client.get_collection(collection_name)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            formatted = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 0.0

                    formatted.append({
                        "text": doc,
                        "metadata": metadata,
                        "distance": distance,
                        "source": metadata.get("file", metadata.get("source", collection_name)),
                    })

            return formatted
        except Exception as e:
            logger.error(f"Collection search error: {e}")
            return []

    def _embed_query(self, query: str) -> list[float] | None:
        """Generate embedding for a query using Ollama.

        Args:
            query: Query text

        Returns:
            Embedding vector or None
        """
        try:
            import requests

            resp = requests.post(
                f"{self.config.ollama_url}/api/embeddings",
                json={
                    "model": self.config.embedding_model,
                    "prompt": query,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embedding")
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def build_context(
        self,
        query: str,
        collections: list[str] | None = None,
        max_chars: int = 6000,
    ) -> tuple[str, list[str]]:
        """Build RAG context string for LLM injection.

        Args:
            query: Search query
            collections: KB collections to search
            max_chars: Maximum context length

        Returns:
            Tuple of (context_string, list_of_sources)
        """
        results = self.search(query, collections=collections, top_k=self.config.top_k)

        if not results:
            return "", []

        # Build context with source attribution
        context_parts = []
        sources_used = set()
        current_length = 0

        for result in results:
            source = result.get("source", "unknown")
            sources_used.add(source)

            snippet = f"[Source: {source}]\n{result['text']}"
            if current_length + len(snippet) + 2 > max_chars:
                break

            context_parts.append(snippet)
            current_length += len(snippet) + 2

        context = "\n\n".join(context_parts)
        sorted_sources = sorted(sources_used)

        logger.info(f"Built context from {len(sorted_sources)} sources ({current_length} chars)")
        return context, sorted_sources
