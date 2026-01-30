"""Semantic search for memory files using embeddings."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryEmbeddings:
    """Manages semantic search over memory files using ChromaDB."""

    def __init__(self, memory_system: Any) -> None:
        """Initialize memory embeddings.
        
        Args:
            memory_system: MemorySystem instance for file access
        """
        self.memory_system = memory_system
        self._chroma: Any | None = None
        self._embedder: Any | None = None
        self._collection_name = "bark_memory"

    def _get_chroma(self) -> Any:
        """Get or create ChromaDB client."""
        if self._chroma is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            # Use persistent storage in memory directory
            persist_dir = self.memory_system.base_dir / "chroma_index"
            persist_dir.mkdir(exist_ok=True)
            
            self._chroma = chromadb.Client(
                ChromaSettings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=str(persist_dir),
                    anonymized_telemetry=False,
                )
            )
        return self._chroma

    def _get_embedder(self) -> Any:
        """Get or create embedding generator."""
        if self._embedder is None:
            from bark.context.embeddings import EmbeddingGenerator
            self._embedder = EmbeddingGenerator()
        return self._embedder

    def _get_collection(self) -> Any:
        """Get or create the memory collection."""
        chroma = self._get_chroma()
        return chroma.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_file(self, file_path: str, content: str | None = None) -> None:
        """Add or update a file in the semantic index.
        
        Args:
            file_path: Relative path within memory directory
            content: Optional content (will read from file if not provided)
        """
        if content is None:
            content = self.memory_system.read_file(file_path)
        
        if not content.strip():
            logger.warning(f"Skipping empty file: {file_path}")
            return
        
        embedder = self._get_embedder()
        collection = self._get_collection()
        
        # Generate embedding
        embedding = embedder.generate(content)
        
        # Use file path as document ID
        doc_id = file_path.replace("/", "__")
        
        # Upsert to collection
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content[:5000]],  # Truncate for storage
            metadatas=[{
                "path": file_path,
                "protected": self.memory_system.is_protected(file_path),
            }],
        )
        
        logger.info(f"Indexed memory file: {file_path}")

    def remove_file(self, file_path: str) -> None:
        """Remove a file from the semantic index.
        
        Args:
            file_path: Relative path within memory directory
        """
        collection = self._get_collection()
        doc_id = file_path.replace("/", "__")
        
        try:
            collection.delete(ids=[doc_id])
            logger.info(f"Removed from index: {file_path}")
        except Exception as e:
            logger.warning(f"Could not remove {file_path} from index: {e}")

    def semantic_search(
        self,
        query: str,
        folder: str | None = None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search memory files by semantic similarity.
        
        Args:
            query: Search query
            folder: Optional folder to limit search
            k: Number of results to return
            
        Returns:
            List of search results with path, content preview, and score
        """
        embedder = self._get_embedder()
        collection = self._get_collection()
        
        # Generate query embedding
        query_embedding = embedder.generate(query)
        
        # Build where clause for folder filter
        where_clause = None
        if folder:
            # Match paths starting with folder
            where_clause = {"path": {"$contains": folder}}
        
        # Query collection
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=where_clause,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
        
        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                document = results["documents"][0][i] if results["documents"] else ""
                distance = results["distances"][0][i] if results["distances"] else 0.0
                
                # Calculate similarity score (1 - cosine distance)
                score = 1 - distance
                
                formatted.append({
                    "path": metadata.get("path", doc_id.replace("__", "/")),
                    "protected": metadata.get("protected", False),
                    "score": round(score, 3),
                    "preview": document[:300] + "..." if len(document) > 300 else document,
                })
        
        return formatted

    def reindex_all(self) -> int:
        """Rebuild the entire memory index.
        
        Returns:
            Number of files indexed
        """
        self.memory_system.initialize()
        
        # Clear existing collection
        chroma = self._get_chroma()
        try:
            chroma.delete_collection(self._collection_name)
        except Exception:
            pass
        
        count = 0
        
        # Index all .md files
        for md_file in self.memory_system.base_dir.rglob("*.md"):
            # Skip hidden files
            if any(part.startswith(".") for part in md_file.parts):
                continue
            
            try:
                rel_path = str(md_file.relative_to(self.memory_system.base_dir))
                content = md_file.read_text(encoding="utf-8")
                self.index_file(rel_path, content)
                count += 1
            except Exception as e:
                logger.warning(f"Error indexing {md_file}: {e}")
        
        logger.info(f"Reindexed {count} memory files")
        return count


# Global instance
_memory_embeddings: MemoryEmbeddings | None = None


def get_memory_embeddings() -> MemoryEmbeddings:
    """Get the global memory embeddings instance."""
    global _memory_embeddings
    if _memory_embeddings is None:
        from bark.memory.memory_system import get_memory_system
        _memory_embeddings = MemoryEmbeddings(get_memory_system())
    return _memory_embeddings
