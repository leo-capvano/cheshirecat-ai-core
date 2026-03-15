from abc import ABC, abstractmethod
from typing import Any, List, Iterable, Optional, Tuple

from langchain.docstore.document import Document

from cat.memory.vector_memory_point import VectorMemoryPoint


class VectorMemoryCollection(ABC):
    """Abstract base class for vector memory collections.

    All vector database backends must implement this interface.
    """

    def __init__(
        self,
        collection_name: str,
        embedder_name: str,
        embedder_size: int,
        **kwargs: Any,
    ):
        self.collection_name = collection_name
        self.embedder_name = embedder_name
        self.embedder_size = embedder_size

    @abstractmethod
    def create_db_collection_if_not_exists(self):
        """Check if collection exists in the DB, create it if not."""
        pass

    @abstractmethod
    def check_embedding_size(self):
        """Check if current embedder size matches the collection's vector size.
        If mismatched, recreate the collection."""
        pass

    @abstractmethod
    def create_collection(self):
        """Create the collection in the vector database."""
        pass

    @abstractmethod
    def add_point(
        self,
        content: str,
        vector: Iterable,
        metadata: dict = None,
        id: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[VectorMemoryPoint]:
        """Add a point (and its metadata) to the vector store.

        Args:
            content: original text.
            vector: Embedding vector.
            metadata: Optional metadata dict associated with the text.
            id: Optional id to associate with the point.

        Returns:
            VectorMemoryPoint as saved into the vector store, or None on failure.
        """
        pass

    @abstractmethod
    def add_points_batch(
        self,
        ids: List[str],
        payloads: List[dict],
        vectors: List[List[float]],
        **kwargs: Any,
    ) -> None:
        """Add multiple points in batch mode.

        Args:
            ids: List of point IDs.
            payloads: List of payload dicts (each with 'page_content' and 'metadata').
            vectors: List of embedding vectors.
        """
        pass

    @abstractmethod
    def delete_points_by_metadata_filter(self, metadata=None):
        """Delete points matching a metadata filter."""
        pass

    @abstractmethod
    def delete_points(self, points_ids):
        """Delete points by their IDs."""
        pass

    @abstractmethod
    def recall_memories_from_embedding(
        self, embedding, metadata=None, k=5, threshold=None
    ) -> List[Tuple[Document, float, List[float], str]]:
        """Retrieve similar memories from an embedding.

        Returns:
            List of tuples (Document, score, vector, id).
        """
        pass

    @abstractmethod
    def get_points(self, ids: List[str]) -> List[VectorMemoryPoint]:
        """Get points by their IDs."""
        pass

    @abstractmethod
    def get_all_points(
        self,
        limit: int = 10000,
        offset: Optional[str] = None,
    ) -> Tuple[List[VectorMemoryPoint], Optional[str]]:
        """Retrieve all points in the collection with optional pagination.

        Returns:
            Tuple of (list of VectorMemoryPoint, next_offset or None).
        """
        pass

    @abstractmethod
    def db_is_remote(self) -> bool:
        """Check if the database is remote."""
        pass

    @abstractmethod
    def save_dump(self, folder="dormouse/"):
        """Dump collection on disk before deleting (for snapshots)."""
        pass
